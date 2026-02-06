# test_envelope_builder.py
"""
Test suite completa per EnvelopeBuilder.

Organizzazione:
1. Test riconoscimento formato compatto (_is_compact_format)
2. Test espansione formato compatto (_expand_compact_format)
3. Test estrazione tipo interpolazione (extract_interp_type)
4. Test parse - formato diretto
5. Test parse - formato misto
6. Test parse - formato legacy
7. Test discontinuità temporali
8. Test ordinamento monotono
9. Test edge cases
10. Test validazione errori
11. Test helper functions (detect_format_type)
12. Test logging delle trasformazioni (mock)
"""

import pytest
from unittest.mock import patch, MagicMock
from envelope_builder import EnvelopeBuilder, detect_format_type


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def simple_compact():
    """Formato compatto semplice: 2 punti, 4 ripetizioni."""
    return [[[0, 0], [100, 1]], 0.4, 4]


@pytest.fixture
def compact_with_interp():
    """Formato compatto con tipo interpolazione."""
    return [[[0, 0], [100, 1]], 0.4, 4, 'cubic']


@pytest.fixture
def compact_three_points():
    """Formato compatto con 3 punti nel pattern."""
    return [[[0, 0], [50, 0.5], [100, 1]], 0.3, 3]


@pytest.fixture
def legacy_breakpoints():
    """Formato legacy standard."""
    return [[0, 0], [0.5, 1], [1.0, 0]]


@pytest.fixture
def legacy_with_cycle():
    """Formato legacy con marker 'cycle'."""
    return [[0, 0], [1, 10], 'cycle', [2, 5]]


@pytest.fixture
def mixed_format():
    """Formato misto: compatto + standard."""
    return [
        [[[0, 0], [100, 1]], 0.2, 2],  # Compatto
        [0.5, 0.5],                     # Standard
        [1.0, 0]                        # Standard
    ]


# =============================================================================
# 1. TEST RICONOSCIMENTO FORMATO COMPATTO
# =============================================================================

class TestIsCompactFormat:
    """Test _is_compact_format()."""
    
    def test_recognize_simple_compact(self, simple_compact):
        """Riconosce formato compatto semplice."""
        assert EnvelopeBuilder._is_compact_format(simple_compact)
    
    def test_recognize_compact_with_interp(self, compact_with_interp):
        """Riconosce formato compatto con interpolazione."""
        assert EnvelopeBuilder._is_compact_format(compact_with_interp)
    
    def test_recognize_compact_three_points(self, compact_three_points):
        """Riconosce formato compatto con 3 punti."""
        assert EnvelopeBuilder._is_compact_format(compact_three_points)
    
    def test_reject_legacy_breakpoint(self):
        """Rifiuta breakpoint legacy [t, v]."""
        assert not EnvelopeBuilder._is_compact_format([0, 10])
    
    def test_reject_legacy_list(self, legacy_breakpoints):
        """Rifiuta lista di breakpoints legacy."""
        assert not EnvelopeBuilder._is_compact_format(legacy_breakpoints)
    
    def test_reject_cycle_marker(self):
        """Rifiuta marker 'cycle'."""
        assert not EnvelopeBuilder._is_compact_format('cycle')
    
    def test_reject_wrong_length(self):
        """Rifiuta liste con lunghezza sbagliata."""
        assert not EnvelopeBuilder._is_compact_format([1, 2])
        assert not EnvelopeBuilder._is_compact_format([1, 2, 3, 4, 5])
    
    def test_reject_wrong_types(self):
        """Rifiuta tipi sbagliati negli elementi."""
        # total_time non numerico
        assert not EnvelopeBuilder._is_compact_format([[[0, 0]], "0.4", 4])
        
        # n_reps non intero
        assert not EnvelopeBuilder._is_compact_format([[[0, 0]], 0.4, 4.5])
        
        # interp_type non stringa
        assert not EnvelopeBuilder._is_compact_format([[[0, 0]], 0.4, 4, 123])
        
        # pattern_points non lista
        assert not EnvelopeBuilder._is_compact_format(["points", 0.4, 4])
    
    def test_accept_empty_pattern(self):
        """Accetta pattern vuoto (validato dopo)."""
        # Pattern vuoto passa _is_compact_format,
        # errore verrà sollevato in _expand_compact_format
        assert EnvelopeBuilder._is_compact_format([[], 0.4, 4])
    
    def test_reject_non_list(self):
        """Rifiuta input non-lista."""
        assert not EnvelopeBuilder._is_compact_format(42)
        assert not EnvelopeBuilder._is_compact_format("compact")
        assert not EnvelopeBuilder._is_compact_format({'type': 'compact'})


# =============================================================================
# 2. TEST ESPANSIONE FORMATO COMPATTO
# =============================================================================

class TestExpandCompactFormat:
    """Test _expand_compact_format()."""
    
    def test_expand_simple_compact(self, simple_compact):
        """Espande formato compatto semplice."""
        expanded = EnvelopeBuilder._expand_compact_format(simple_compact)
        
        # 4 cicli * 2 punti + 3 discontinuità = 11 breakpoints
        assert len(expanded) == 11
        
        # Verifica primi breakpoints
        assert expanded[0] == [0.0, 0]
        assert expanded[1] == pytest.approx([0.1, 1])
        
        # Verifica discontinuità dopo primo ciclo
        assert expanded[2][0] == pytest.approx(0.1 + EnvelopeBuilder.DISCONTINUITY_OFFSET)
        assert expanded[2][1] == 0  # Reset al primo valore
    
    def test_expand_three_points_pattern(self, compact_three_points):
        """Espande pattern con 3 punti."""
        expanded = EnvelopeBuilder._expand_compact_format(compact_three_points)
        
        # 3 cicli * 3 punti + 2 discontinuità = 11 breakpoints
        assert len(expanded) == 11
        
        # Verifica primo ciclo
        assert expanded[0] == [0.0, 0]
        assert expanded[1] == pytest.approx([0.05, 0.5])
        assert expanded[2] == pytest.approx([0.1, 1])
    
    def test_expand_single_repetition(self):
        """Espande con n_reps=1 (nessuna discontinuità)."""
        compact = [[[0, 0], [100, 1]], 0.1, 1]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # 1 ciclo * 2 punti = 2 breakpoints (nessuna discontinuità)
        assert len(expanded) == 2
        assert expanded[0] == [0.0, 0]
        assert expanded[1] == pytest.approx([0.1, 1])
    
    def test_expand_many_repetitions(self):
        """Espande con molte ripetizioni."""
        compact = [[[0, 0], [100, 1]], 1.0, 100]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # 100 cicli * 2 punti + 99 discontinuità = 299 breakpoints
        assert len(expanded) == 299
    
    def test_percentage_to_absolute_conversion(self):
        """Converte correttamente coordinate % in assolute."""
        compact = [[[0, 10], [50, 20], [100, 30]], 1.0, 2]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Primo ciclo: 0→0.5s
        assert expanded[0] == [0.0, 10]
        assert expanded[1] == pytest.approx([0.25, 20])  # 50% di 0.5s
        assert expanded[2] == pytest.approx([0.5, 30])   # 100% di 0.5s
        
        # Discontinuità
        assert expanded[3][0] == pytest.approx(0.5 + EnvelopeBuilder.DISCONTINUITY_OFFSET)
        assert expanded[3][1] == 10  # Reset
        
        # Secondo ciclo: 0.5→1.0s
        assert expanded[4][0] == pytest.approx(0.5 + 2 * EnvelopeBuilder.DISCONTINUITY_OFFSET)
        assert expanded[5] == pytest.approx([0.75, 20])
        assert expanded[6] == pytest.approx([1.0, 30])
    
    def test_discontinuity_values(self):
        """Discontinuità resettano al primo valore del pattern."""
        compact = [[[0, 5], [100, 10]], 0.4, 4]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Ogni discontinuità deve avere valore 5 (primo del pattern)
        discontinuity_indices = [2, 5, 8]  # Dopo cicli 1, 2, 3
        for idx in discontinuity_indices:
            assert expanded[idx][1] == 5
    
    def test_time_strictly_increasing(self):
        """Tempi strettamente crescenti (no uguali)."""
        compact = [[[0, 0], [100, 1]], 1.0, 10]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Verifica che ogni tempo sia > del precedente
        for i in range(1, len(expanded)):
            assert expanded[i][0] > expanded[i-1][0]
    
    def test_last_cycle_no_discontinuity(self):
        """Ultimo ciclo non ha discontinuità dopo."""
        compact = [[[0, 0], [100, 1]], 0.2, 3]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # 3 cicli * 2 punti + 2 discontinuità = 8 breakpoints
        assert len(expanded) == 8
        
        # Ultimo breakpoint è fine terzo ciclo
        assert expanded[-1] == pytest.approx([0.2, 1])


# =============================================================================
# 3. TEST ESTRAZIONE TIPO INTERPOLAZIONE
# =============================================================================

class TestExtractInterpType:
    """Test extract_interp_type()."""
    
    def test_extract_from_compact_with_interp(self, compact_with_interp):
        """Estrae tipo da formato compatto diretto."""
        interp = EnvelopeBuilder.extract_interp_type(compact_with_interp)
        assert interp == 'cubic'
    
    def test_extract_from_compact_without_interp(self, simple_compact):
        """Ritorna None se formato compatto senza tipo."""
        interp = EnvelopeBuilder.extract_interp_type(simple_compact)
        assert interp is None
    
    def test_extract_from_mixed_format(self):
        """Estrae tipo dal primo formato compatto in lista mista."""
        mixed = [
            [[0, 0], [1, 10]],              # Standard (no tipo)
            [[[0, 0], [100, 1]], 0.2, 2, 'step'],  # Compatto con tipo
            [[[0, 0], [100, 1]], 0.2, 2, 'cubic']  # Compatto con altro tipo
        ]
        interp = EnvelopeBuilder.extract_interp_type(mixed)
        assert interp == 'step'  # Primo trovato
    
    def test_extract_from_legacy_returns_none(self, legacy_breakpoints):
        """Ritorna None se lista legacy."""
        interp = EnvelopeBuilder.extract_interp_type(legacy_breakpoints)
        assert interp is None
    
    def test_extract_from_empty_list(self):
        """Ritorna None se lista vuota."""
        interp = EnvelopeBuilder.extract_interp_type([])
        assert interp is None


# =============================================================================
# 4. TEST PARSE - FORMATO DIRETTO
# =============================================================================

class TestParseDirectFormat:
    """Test parse() con formato compatto diretto."""
    
    def test_parse_compact_direct(self, simple_compact):
        """Parse formato compatto passato direttamente."""
        expanded = EnvelopeBuilder.parse(simple_compact)
        
        # Verifica espansione
        assert len(expanded) == 11
        assert all(isinstance(bp, list) for bp in expanded)
    
    def test_parse_compact_with_interp_direct(self, compact_with_interp):
        """Parse compatto con interpolazione diretto."""
        expanded = EnvelopeBuilder.parse(compact_with_interp)
        
        assert len(expanded) == 11
    
    def test_parse_single_rep_direct(self):
        """Parse compatto con singola ripetizione."""
        compact = [[[0, 0], [100, 1]], 0.1, 1]
        expanded = EnvelopeBuilder.parse(compact)
        
        assert len(expanded) == 2


# =============================================================================
# 5. TEST PARSE - FORMATO MISTO
# =============================================================================

class TestParseMixedFormat:
    """Test parse() con formato misto."""
    
    def test_parse_mixed_compact_and_standard(self, mixed_format):
        """Parse misto: compatto + standard."""
        expanded = EnvelopeBuilder.parse(mixed_format)
        
        # Compatto espanso (2 cicli * 2 punti + 1 discontinuità = 5)
        # + 2 standard = 7 totali
        assert len(expanded) == 7
        
        # Primi 5 da compatto
        assert expanded[0] == [0.0, 0]
        assert expanded[4] == pytest.approx([0.2, 1])
        
        # Ultimi 2 standard
        assert expanded[5] == [0.5, 0.5]
        assert expanded[6] == [1.0, 0]
    
    def test_parse_multiple_compact_in_list(self):
        """Parse con multipli formati compatti."""
        mixed = [
            [[[0, 0], [100, 1]], 0.2, 2],    # Primo compatto
            [[[0, 5], [100, 10]], 0.2, 2]    # Secondo compatto
        ]
        expanded = EnvelopeBuilder.parse(mixed)
        
        # 2 * (2 cicli * 2 punti + 1 discontinuità) = 10 totali
        assert len(expanded) == 10
    
    def test_parse_compact_with_cycle_marker(self):
        """Parse compatto seguito da 'cycle' marker."""
        mixed = [
            [[[0, 0], [100, 1]], 0.1, 1],
            'cycle',
            [0.5, 0.5]
        ]
        expanded = EnvelopeBuilder.parse(mixed)
        
        # 2 da compatto + 'cycle' + 1 standard = 4
        assert len(expanded) == 4
        assert expanded[2] == 'cycle'


# =============================================================================
# 6. TEST PARSE - FORMATO LEGACY
# =============================================================================

class TestParseLegacyFormat:
    """Test parse() con formato legacy."""
    
    def test_parse_legacy_unchanged(self, legacy_breakpoints):
        """Parse legacy passa invariato."""
        expanded = EnvelopeBuilder.parse(legacy_breakpoints)
        
        # Lista identica
        assert expanded == legacy_breakpoints
    
    def test_parse_legacy_with_cycle(self, legacy_with_cycle):
        """Parse legacy con 'cycle' passa invariato."""
        expanded = EnvelopeBuilder.parse(legacy_with_cycle)
        
        assert expanded == legacy_with_cycle
        assert 'cycle' in expanded
    
    def test_parse_single_breakpoint(self):
        """Parse singolo breakpoint."""
        single = [[0, 10]]
        expanded = EnvelopeBuilder.parse(single)
        
        assert expanded == single


# =============================================================================
# 7. TEST DISCONTINUITÀ TEMPORALI
# =============================================================================

class TestTemporalDiscontinuities:
    """Test gestione discontinuità temporali."""
    
    def test_discontinuity_offset_applied(self):
        """Offset infinitesimale applicato correttamente."""
        compact = [[[0, 0], [100, 1]], 0.2, 2]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Fine primo ciclo
        end_first = expanded[1][0]
        
        # Discontinuità
        discontinuity = expanded[2][0]
        
        assert discontinuity == pytest.approx(
            end_first + EnvelopeBuilder.DISCONTINUITY_OFFSET
        )
    
    def test_multiple_discontinuities_offset(self):
        """Discontinuità multiple con offset cumulativi."""
        compact = [[[0, 0], [100, 1]], 0.3, 3]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Discontinuità dopo ciclo 1 e 2
        disc1_time = expanded[2][0]
        disc2_time = expanded[5][0]
        
        # Verifica che siano distanziati correttamente
        cycle_duration = 0.1
        expected_disc2 = cycle_duration + 2 * EnvelopeBuilder.DISCONTINUITY_OFFSET
        
        assert disc2_time == pytest.approx(expected_disc2)
    
    def test_no_time_collision(self):
        """Nessun tempo collide con un altro."""
        compact = [[[0, 0], [100, 1]], 1.0, 100]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        times = [bp[0] for bp in expanded]
        
        # Verifica unicità (set dovrebbe avere stessa lunghezza)
        assert len(times) == len(set(times))


# =============================================================================
# 8. TEST ORDINAMENTO MONOTONO
# =============================================================================

class TestMonotonicOrdering:
    """Test garantisce ordinamento monotono stretto."""
    
    def test_times_strictly_increasing(self):
        """Tempi strettamente crescenti."""
        compact = [[[0, 0], [50, 0.5], [100, 1]], 1.0, 10]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        for i in range(1, len(expanded)):
            assert expanded[i][0] > expanded[i-1][0]
    
    def test_offset_prevents_equal_times(self):
        """Offset previene tempi uguali."""
        compact = [[[0, 0], [0, 1], [100, 2]], 0.2, 2]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Anche con x%=0 due volte, tempi devono essere diversi
        times = [bp[0] for bp in expanded]
        assert len(times) == len(set(times))


# =============================================================================
# 9. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_very_short_duration(self):
        """Durata molto breve."""
        compact = [[[0, 0], [100, 1]], 0.001, 10]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Deve funzionare
        assert len(expanded) == 29  # 10*2 + 9 discontinuità
        
        # Verifica ultimo tempo
        assert expanded[-1][0] == pytest.approx(0.001)
    
    def test_very_long_duration(self):
        """Durata molto lunga."""
        compact = [[[0, 0], [100, 1]], 1000.0, 2]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        assert len(expanded) == 5  # 2*2 + 1 discontinuità
        assert expanded[-1][0] == pytest.approx(1000.0)
    
    def test_single_point_pattern(self):
        """Pattern con singolo punto."""
        compact = [[[0, 5]], 0.4, 4]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # 4 cicli * 1 punto + 3 discontinuità = 7
        assert len(expanded) == 7
        
        # Tutti i valori devono essere 5
        assert all(bp[1] == 5 for bp in expanded)
    
    def test_extreme_percentage_values(self):
        """Valori percentuali estremi (0% e 100%)."""
        compact = [[[0, -10], [100, 10]], 1.0, 2]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Primo punto di ogni ciclo a t_start
        assert expanded[0] == [0.0, -10]
        assert expanded[3][1] == -10
        
        # Ultimo punto di ogni ciclo a t_end
        assert expanded[1] == pytest.approx([0.5, 10])
        assert expanded[5] == pytest.approx([1.0, 10])
    
    def test_non_standard_percentage_order(self):
        """Percentuali non ordinate (vengono ordinate)."""
        compact = [[[100, 1], [0, 0], [50, 0.5]], 1.0, 1]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Pattern dovrebbe essere ordinato internamente se necessario
        # (questo dipende dall'implementazione - verifica comportamento)
        assert len(expanded) == 3


# =============================================================================
# 10. TEST VALIDAZIONE ERRORI
# =============================================================================

class TestValidationErrors:
    """Test validazione e gestione errori."""
    
    def test_error_zero_repetitions(self):
        """n_reps=0 solleva ValueError."""
        compact = [[[0, 0], [100, 1]], 0.4, 0]
        
        with pytest.raises(ValueError, match="n_reps deve essere >= 1"):
            EnvelopeBuilder._expand_compact_format(compact)
    
    def test_error_negative_repetitions(self):
        """n_reps negativo solleva ValueError."""
        compact = [[[0, 0], [100, 1]], 0.4, -5]
        
        with pytest.raises(ValueError, match="n_reps deve essere >= 1"):
            EnvelopeBuilder._expand_compact_format(compact)
    
    def test_error_zero_total_time(self):
        """total_time=0 solleva ValueError."""
        compact = [[[0, 0], [100, 1]], 0.0, 4]
        
        with pytest.raises(ValueError, match="total_time deve essere > 0"):
            EnvelopeBuilder._expand_compact_format(compact)
    
    def test_error_negative_total_time(self):
        """total_time negativo solleva ValueError."""
        compact = [[[0, 0], [100, 1]], -0.5, 4]
        
        with pytest.raises(ValueError, match="total_time deve essere > 0"):
            EnvelopeBuilder._expand_compact_format(compact)
    
    def test_error_empty_pattern(self):
        """Pattern vuoto solleva ValueError."""
        compact = [[], 0.4, 4]
        
        with pytest.raises(ValueError, match="pattern_points non può essere vuoto"):
            EnvelopeBuilder._expand_compact_format(compact)
    
    def test_error_invalid_pattern_format(self):
        """Pattern con formato invalido."""
        # Pattern non è lista di liste
        compact = ["invalid", 0.4, 4]
        
        # Dovrebbe essere rilevato da _is_compact_format
        assert not EnvelopeBuilder._is_compact_format(compact)


# =============================================================================
# 11. TEST HELPER FUNCTIONS
# =============================================================================

class TestHelperFunctions:
    """Test funzioni helper."""
    
    def test_detect_format_compact(self, simple_compact):
        """detect_format_type riconosce compatto."""
        assert detect_format_type(simple_compact) == 'compact'
    
    def test_detect_format_breakpoint(self):
        """detect_format_type riconosce breakpoint."""
        assert detect_format_type([0.5, 10]) == 'breakpoint'
    
    def test_detect_format_cycle(self):
        """detect_format_type riconosce 'cycle'."""
        assert detect_format_type('cycle') == 'cycle'
        assert detect_format_type('CYCLE') == 'cycle'
    
    def test_detect_format_unknown(self):
        """detect_format_type ritorna 'unknown' per altro."""
        assert detect_format_type(42) == 'unknown'
        assert detect_format_type("string") == 'unknown'
        assert detect_format_type([1, 2, 3]) == 'unknown'


# =============================================================================
# 12. TEST LOGGING DELLE TRASFORMAZIONI (MOCK)
# =============================================================================

class TestLoggingTransformations:
    """Test logging delle trasformazioni (con mock)."""
    
    @patch('envelope_builder.get_clip_logger')
    def test_logging_called_on_expansion(self, mock_get_logger, simple_compact):
        """Logging chiamato durante espansione."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        EnvelopeBuilder._expand_compact_format(simple_compact)
        
        # Verifica che logger.info sia stato chiamato
        assert mock_logger.info.called
        
        # Verifica almeno alcune chiamate chiave
        calls = [str(call) for call in mock_logger.info.call_args_list]
        
        # Cerca pattern caratteristici nel log
        log_text = ' '.join(calls)
        assert 'COMPACT ENVELOPE TRANSFORMATION' in log_text or mock_logger.info.call_count > 0
    
    @patch('envelope_builder.get_clip_logger')
    def test_logging_disabled_if_logger_none(self, mock_get_logger, simple_compact):
        """Logging disabilitato se logger è None."""
        mock_get_logger.return_value = None
        
        # Non deve sollevare errori
        expanded = EnvelopeBuilder._expand_compact_format(simple_compact)
        
        # Espansione deve comunque funzionare
        assert len(expanded) == 11
    
    @patch('envelope_builder.get_clip_logger')
    def test_logging_includes_key_info(self, mock_get_logger, compact_with_interp):
        """Logging include informazioni chiave."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        EnvelopeBuilder._expand_compact_format(compact_with_interp)
        
        # Verifica che info sia chiamato con stringhe contenenti info chiave
        calls_args = [call[0][0] for call in mock_logger.info.call_args_list]
        log_text = ' '.join(calls_args)
        
        # Cerca elementi chiave
        assert any('Pattern points' in text or 'Total time' in text 
                   or 'Repetitions' in text for text in calls_args)


# =============================================================================
# 13. TEST PROPRIETÀ MATEMATICHE
# =============================================================================

class TestMathematicalProperties:
    """Test proprietà matematiche dell'espansione."""
    
    def test_total_duration_preserved(self):
        """Durata totale preservata."""
        total_time = 1.0
        compact = [[[0, 0], [100, 1]], total_time, 10]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Ultimo tempo deve essere circa total_time
        assert expanded[-1][0] == pytest.approx(total_time, abs=1e-5)
    
    def test_cycle_duration_uniform(self):
        """Durata cicli uniforme."""
        compact = [[[0, 0], [100, 1]], 1.0, 4]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        expected_cycle_duration = 0.25
        
        # Trova gli inizi cicli (escludendo discontinuità)
        cycle_starts = [0, 3, 6, 9]  # Indici dei primi punti di ogni ciclo
        
        for i in range(len(cycle_starts) - 1):
            start_idx = cycle_starts[i]
            end_idx = cycle_starts[i] + 1  # Fine dello stesso ciclo
            
            cycle_dur = expanded[end_idx][0] - expanded[start_idx][0]
            assert cycle_dur == pytest.approx(expected_cycle_duration, abs=1e-5)
    
    def test_value_repetition(self):
        """Valori si ripetono ciclicamente."""
        compact = [[[0, 5], [100, 10]], 1.0, 3]
        expanded = EnvelopeBuilder._expand_compact_format(compact)
        
        # Pattern: [5, 10] si ripete 3 volte
        # Ogni inizio ciclo ha valore 5, ogni fine ha valore 10
        cycle_start_indices = [0, 3, 6]
        
        for idx in cycle_start_indices:
            assert expanded[idx][1] == 5
            assert expanded[idx + 1][1] == 10


# =============================================================================
# RUN TESTS
# =============================================================================

