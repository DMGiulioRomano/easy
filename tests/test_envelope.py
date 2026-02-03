"""
Test suite completa per Envelope con supporto cicli multipli.
VERSIONE CORRETTA: L'ultimo breakpoint del ciclo è raggiungibile.

Organizzazione:
1. Test inizializzazione e parsing
2. Test ciclo singolo (linear/step/cubic)
3. Test cicli multipli
4. Test mix ciclico + non ciclico
5. Test edge cases temporali
6. Test ultimo breakpoint raggiungibile
7. Test gestione errori
"""

import pytest
from envelope import Envelope


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def env_single_cycle_linear():
    """Ciclo singolo lineare: [0,0] → [0.1,1] → cycle."""
    return Envelope([[0, 0], [0.1, 1], 'cycle'])

@pytest.fixture
def env_single_cycle_step():
    """Ciclo singolo step."""
    return Envelope({
        'type': 'step',
        'points': [[0, 10], [0.05, 50], [0.1, 100], 'cycle']
    })

@pytest.fixture
def env_single_cycle_cubic():
    """Ciclo singolo cubic."""
    return Envelope({
        'type': 'cubic',
        'points': [[0, 0], [0.05, 1], [0.1, 0], 'cycle']
    })

@pytest.fixture
def env_two_cycles():
    """Due cicli indipendenti."""
    return Envelope([
        [0, 0], [0.05, 1], 'cycle',      # Ciclo 1: 0.05s
        [0.3, 0], [0.39, 1], 'cycle'     # Ciclo 2: 0.09s
    ])

@pytest.fixture
def env_cycle_then_normal():
    """Ciclo seguito da segmento non ciclico."""
    return Envelope([
        [0, 0], [0.05, 1], 'cycle',      # Ciclico
        [0.5, 0.5], [1.0, 0]             # Non ciclico (fade out)
    ])

@pytest.fixture
def env_normal_only():
    """Envelope tradizionale senza cicli."""
    return Envelope([[0, 0], [0.5, 1], [1.0, 0]])


# =============================================================================
# 1. TEST INIZIALIZZAZIONE E PARSING
# =============================================================================

class TestInitializationAndParsing:
    """Test parsing e validazione dell'input."""
    
    def test_parse_single_cycle_list(self):
        """Parsing lista con singolo ciclo."""
        env = Envelope([[0, 0], [0.1, 1], 'cycle'])
        
        assert len(env.segments) == 1
        assert env.segments[0]['cycle'] is True
        assert env.segments[0]['cycle_duration'] == pytest.approx(0.1)
        assert env.segments[0]['start_time'] == pytest.approx(0.0)
        assert len(env.segments[0]['breakpoints']) == 2
    
    def test_parse_two_cycles(self):
        """Parsing lista con due cicli."""
        env = Envelope([
            [0, 0], [0.1, 1], 'cycle',
            [0.5, 0], [0.6, 1], 'cycle'
        ])
        
        assert len(env.segments) == 2
        assert env.segments[0]['cycle'] is True
        assert env.segments[1]['cycle'] is True
        assert env.segments[0]['cycle_duration'] == pytest.approx(0.1)
        assert env.segments[1]['cycle_duration'] == pytest.approx(0.1)
    
    def test_parse_cycle_then_normal(self):
        """Parsing ciclo seguito da segmento normale."""
        env = Envelope([
            [0, 0], [0.1, 1], 'cycle',
            [0.5, 0.5], [1.0, 0]
        ])
        
        assert len(env.segments) == 2
        assert env.segments[0]['cycle'] is True
        assert env.segments[1]['cycle'] is False
        assert env.segments[1]['cycle_duration'] is None
    
    def test_parse_dict_with_cycle(self):
        """Parsing dict con type e cycle."""
        env = Envelope({
            'type': 'cubic',
            'points': [[0, 0], [0.1, 1], 'cycle']
        })
        
        assert env.type == 'cubic'
        assert len(env.segments) == 1
        assert env.segments[0]['cycle'] is True
    
    def test_parse_normal_envelope_no_cycle(self):
        """Envelope tradizionale senza 'cycle' rimane non ciclico."""
        env = Envelope([[0, 0], [0.5, 1], [1.0, 0]])
        
        assert len(env.segments) == 1
        assert env.segments[0]['cycle'] is False
    
    def test_breakpoints_are_sorted(self):
        """Breakpoints vengono ordinati per tempo."""
        env = Envelope([[0.1, 1], [0, 0], [0.05, 0.5], 'cycle'])
        
        points = env.segments[0]['breakpoints']
        assert points[0] == [0, 0]
        assert points[1] == [0.05, 0.5]
        assert points[2] == [0.1, 1]
    
    def test_case_insensitive_cycle(self):
        """'cycle', 'Cycle', 'CYCLE' sono equivalenti."""
        for marker in ['cycle', 'Cycle', 'CYCLE', 'CyCLe']:
            env = Envelope([[0, 0], [0.1, 1], marker])
            assert env.segments[0]['cycle'] is True


# =============================================================================
# 2. TEST CICLO SINGOLO - LINEAR
# =============================================================================

class TestSingleCycleLinear:
    """Test ciclo singolo con interpolazione lineare."""
    
    def test_first_cycle_start(self, env_single_cycle_linear):
        """Inizio primo ciclo."""
        assert env_single_cycle_linear.evaluate(0.0) == pytest.approx(0.0)
    
    def test_first_cycle_middle(self, env_single_cycle_linear):
        """Metà primo ciclo."""
        assert env_single_cycle_linear.evaluate(0.05) == pytest.approx(0.5)
    
    def test_first_cycle_almost_end(self, env_single_cycle_linear):
        """Quasi fine primo ciclo."""
        assert env_single_cycle_linear.evaluate(0.09) == pytest.approx(0.9)
    
    def test_first_cycle_end(self, env_single_cycle_linear):
        """
        Fine primo ciclo: ultimo breakpoint è raggiungibile.
        
        IMPORTANTE: L'ultimo breakpoint [0.1, 1] deve essere raggiungibile
        e restituire il valore 1.0.
        """
        assert env_single_cycle_linear.evaluate(0.1) == pytest.approx(1.0)
    
    def test_wrap_after_last_breakpoint(self, env_single_cycle_linear):
        """
        Wrap-around avviene DOPO l'ultimo breakpoint.
        
        t=0.10001 è già nel secondo ciclo, quindi wrappa.
        """
        result = env_single_cycle_linear.evaluate(0.10001)
        # 0.10001 - 0 = 0.10001, 0.10001 % 0.1 = 0.00001 ≈ 0
        assert result == pytest.approx(0.0001, abs=0.001)
    
    def test_second_cycle_middle(self, env_single_cycle_linear):
        """Metà secondo ciclo."""
        assert env_single_cycle_linear.evaluate(0.15) == pytest.approx(0.5)
    
    def test_second_cycle_end(self, env_single_cycle_linear):
        """Fine secondo ciclo: ultimo breakpoint raggiungibile."""
        assert env_single_cycle_linear.evaluate(0.2) == pytest.approx(1.0)
    
    def test_third_cycle(self, env_single_cycle_linear):
        """Terzo ciclo."""
        assert env_single_cycle_linear.evaluate(0.25) == pytest.approx(0.5)
    
    def test_many_cycles(self, env_single_cycle_linear):
        """Verifica che il ciclo continui indefinitamente."""
        # t=1.0 = 10 cicli completi → ultimo breakpoint
        assert env_single_cycle_linear.evaluate(1.0) == pytest.approx(1.0)
        # t=1.05 = 10.5 cicli → metà ciclo
        assert env_single_cycle_linear.evaluate(1.05) == pytest.approx(0.5)
    
    def test_partial_cycle_wrap(self, env_single_cycle_linear):
        """Test wrap-around parziale."""
        # t=0.07 = 0.7 cicli → 70% del primo ciclo
        result = env_single_cycle_linear.evaluate(0.07)
        assert result == pytest.approx(0.7)
        
        # t=0.17 = 1.7 cicli → 70% del secondo ciclo
        result = env_single_cycle_linear.evaluate(0.17)
        assert result == pytest.approx(0.7)
    
    def test_before_first_breakpoint(self, env_single_cycle_linear):
        """Prima del primo breakpoint: hold primo valore."""
        assert env_single_cycle_linear.evaluate(-0.1) == pytest.approx(0.0)


# =============================================================================
# 3. TEST CICLO SINGOLO - STEP
# =============================================================================

class TestSingleCycleStep:
    """Test ciclo singolo con interpolazione step."""
    
    def test_step_holds_left_value(self, env_single_cycle_step):
        """Step tiene valore sinistro (left-continuous)."""
        # [0,10] → [0.05,50] → [0.1,100] → cycle
        
        # Prima zona: [0, 0.05)
        assert env_single_cycle_step.evaluate(0.0) == pytest.approx(10)
        assert env_single_cycle_step.evaluate(0.02) == pytest.approx(10)
        assert env_single_cycle_step.evaluate(0.049) == pytest.approx(10)
        
        # Seconda zona: [0.05, 0.1)
        assert env_single_cycle_step.evaluate(0.05) == pytest.approx(50)
        assert env_single_cycle_step.evaluate(0.08) == pytest.approx(50)
        assert env_single_cycle_step.evaluate(0.099) == pytest.approx(50)
    
    def test_step_last_breakpoint_reachable(self, env_single_cycle_step):
        """
        Step: l'ultimo breakpoint è raggiungibile.
        
        A t=0.1 (esattamente), deve restituire 100, non 10.
        """
        assert env_single_cycle_step.evaluate(0.1) == pytest.approx(100)
    
    def test_step_wrap_after_last(self, env_single_cycle_step):
        """Step: wrap-around dopo l'ultimo breakpoint."""
        # Appena dopo 0.1, wrappa a 10
        assert env_single_cycle_step.evaluate(0.10001) == pytest.approx(10)
    
    def test_step_cycle_repeats(self, env_single_cycle_step):
        """Step cycle si ripete correttamente."""
        # Secondo ciclo
        assert env_single_cycle_step.evaluate(0.12) == pytest.approx(10)
        assert env_single_cycle_step.evaluate(0.15) == pytest.approx(50)
        assert env_single_cycle_step.evaluate(0.2) == pytest.approx(100)  # Ultimo breakpoint
        
        # Terzo ciclo
        assert env_single_cycle_step.evaluate(0.22) == pytest.approx(10)


# =============================================================================
# 4. TEST CICLO SINGOLO - CUBIC
# =============================================================================

class TestSingleCycleCubic:
    """Test ciclo singolo con interpolazione cubica."""
    
    def test_cubic_smooth_interpolation(self, env_single_cycle_cubic):
        """Cubic interpola smoothly."""
        # [0,0] → [0.05,1] → [0.1,0] → cycle
        
        # Metà prima salita (non esattamente 0.5 per cubic)
        val = env_single_cycle_cubic.evaluate(0.025)
        assert 0.3 < val < 0.7  # Valore plausibile per cubic
        
        # Picco
        assert env_single_cycle_cubic.evaluate(0.05) == pytest.approx(1.0)
        
        # Ultimo breakpoint raggiungibile
        assert env_single_cycle_cubic.evaluate(0.1) == pytest.approx(0.0)
    
    def test_cubic_has_tangents(self, env_single_cycle_cubic):
        """Cubic pre-calcola tangenti per il segmento."""
        segment = env_single_cycle_cubic.segments[0]
        assert 'tangents' in segment
        assert len(segment['tangents']) == 3  # 3 breakpoints
    
    def test_cubic_cycle_repeats(self, env_single_cycle_cubic):
        """Cubic cycle si ripete."""
        # Primo e secondo ciclo hanno stesso valore a t relativi uguali
        val1 = env_single_cycle_cubic.evaluate(0.025)
        val2 = env_single_cycle_cubic.evaluate(0.125)  # +0.1s = +1 ciclo
        assert val1 == pytest.approx(val2)


# =============================================================================
# 5. TEST CICLI MULTIPLI
# =============================================================================

class TestMultipleCycles:
    """Test transizioni tra cicli multipli."""
    
    def test_two_cycles_structure(self, env_two_cycles):
        """Verifica struttura con due cicli."""
        assert len(env_two_cycles.segments) == 2
        assert env_two_cycles.segments[0]['cycle_duration'] == pytest.approx(0.05)
        assert env_two_cycles.segments[1]['cycle_duration'] == pytest.approx(0.09)
    
    def test_first_cycle_last_breakpoint(self, env_two_cycles):
        """Primo ciclo: ultimo breakpoint raggiungibile."""
        # Primo ciclo: [0, 0] → [0.05, 1]
        # t=0.05 deve valere 1.0
        assert env_two_cycles.evaluate(0.05) == pytest.approx(1.0)
    
    def test_first_cycle_active_until_second_starts(self, env_two_cycles):
        """Primo ciclo attivo fino a t=0.3."""
        # t=0.1 = 2 cicli completi → ultimo breakpoint
        assert env_two_cycles.evaluate(0.1) == pytest.approx(1.0)
        
        # t=0.15 = 3 cicli completi → ultimo breakpoint
        assert env_two_cycles.evaluate(0.15) == pytest.approx(1.0)
        
        # t=0.29 = 5.8 cicli → 80% del ciclo (0.04 / 0.05 = 0.8)
        result = env_two_cycles.evaluate(0.29)
        assert result == pytest.approx(0.8)
    
    def test_transition_at_second_cycle_start(self, env_two_cycles):
        """Transizione esatta a t=0.3."""
        # Just before: ancora primo ciclo
        result = env_two_cycles.evaluate(0.299)
        assert result == pytest.approx(0.98, abs=0.02)
        
        # Exactly at: inizia secondo ciclo
        assert env_two_cycles.evaluate(0.3) == pytest.approx(0.0)
    
    def test_second_cycle_last_breakpoint_reachable(self, env_two_cycles):
        """
        Secondo ciclo: ultimo breakpoint raggiungibile.
        
        CORREZIONE: [0.3, 0] → [0.39, 1]
        A t=0.39, deve valere 1.0 (non 0.0).
        """
        # Primo ciclo del secondo segmento
        assert env_two_cycles.evaluate(0.39) == pytest.approx(1.0)
        
        # Secondo ciclo del secondo segmento
        assert env_two_cycles.evaluate(0.48) == pytest.approx(1.0)
    
    def test_second_cycle_active_after_start(self, env_two_cycles):
        """Secondo ciclo attivo dopo t=0.3."""
        # t=0.345 = metà secondo ciclo (0.09 / 2 = 0.045)
        result = env_two_cycles.evaluate(0.345)
        assert result == pytest.approx(0.5)
        
        # t=0.38 = quasi fine primo ciclo (0.08 / 0.09 ≈ 88.9%)
        result = env_two_cycles.evaluate(0.38)
        assert result == pytest.approx(0.889, abs=0.01)
        
        # t=0.39 = ultimo breakpoint → valore 1.0
        assert env_two_cycles.evaluate(0.39) == pytest.approx(1.0)
        
        # t=0.39001 = wrap-around → quasi zero
        result = env_two_cycles.evaluate(0.39001)
        assert result == pytest.approx(0.011, abs=0.02)
    
    def test_partial_cycle_before_transition(self, env_two_cycles):
        """Ciclo parziale troncato prima della transizione."""
        # Primo ciclo: 0.05s
        # t=0.27 = 5.4 cicli → 40% del 6° ciclo
        result = env_two_cycles.evaluate(0.27)
        assert result == pytest.approx(0.4)
        
        # t=0.295 = 5.9 cicli → 90% del 6° ciclo
        result = env_two_cycles.evaluate(0.295)
        assert result == pytest.approx(0.9, abs=0.05)


# =============================================================================
# 6. TEST MIX CICLICO + NON CICLICO
# =============================================================================

class TestMixCyclicAndNormal:
    """Test mix segmenti ciclici e non ciclici."""
    
    def test_cyclic_segment_before_normal(self, env_cycle_then_normal):
        """Segmento ciclico attivo prima di t=0.5."""
        # Primo ciclo
        assert env_cycle_then_normal.evaluate(0.025) == pytest.approx(0.5)
        
        # Ultimo breakpoint primo ciclo
        assert env_cycle_then_normal.evaluate(0.05) == pytest.approx(1.0)
        
        # Ciclo continua
        assert env_cycle_then_normal.evaluate(0.1) == pytest.approx(1.0)
        assert env_cycle_then_normal.evaluate(0.25) == pytest.approx(1.0)
    
    def test_transition_to_normal_segment(self, env_cycle_then_normal):
        """Transizione a segmento non ciclico."""
        # Just before (quasi fine 10° ciclo)
        result = env_cycle_then_normal.evaluate(0.49)
        assert result == pytest.approx(0.8, abs=0.05)
        
        # Exactly at: inizia fade out
        assert env_cycle_then_normal.evaluate(0.5) == pytest.approx(0.5)
    
    def test_normal_segment_interpolates(self, env_cycle_then_normal):
        """Segmento non ciclico interpola normalmente."""
        # Fade out lineare: [0.5, 0.5] → [1.0, 0]
        assert env_cycle_then_normal.evaluate(0.75) == pytest.approx(0.25)
        assert env_cycle_then_normal.evaluate(1.0) == pytest.approx(0.0)
    
    def test_normal_segment_holds_after_end(self, env_cycle_then_normal):
        """Segmento non ciclico holds ultimo valore."""
        assert env_cycle_then_normal.evaluate(1.5) == pytest.approx(0.0)
        assert env_cycle_then_normal.evaluate(100.0) == pytest.approx(0.0)
    
    def test_partial_last_cycle_before_normal(self, env_cycle_then_normal):
        """Ultimo ciclo parziale prima del segmento normale."""
        # Ciclo: 0.05s, inizia segmento normale a t=0.5
        # t=0.48 = 9.6 cicli → 60% del 10° ciclo
        result = env_cycle_then_normal.evaluate(0.48)
        assert result == pytest.approx(0.6, abs=0.05)


# =============================================================================
# 7. TEST EDGE CASES TEMPORALI
# =============================================================================

class TestEdgeCasesTemporal:
    """Test casi limite temporali."""
    
    def test_exactly_on_breakpoint(self, env_single_cycle_linear):
        """Valutazione esattamente su un breakpoint."""
        assert env_single_cycle_linear.evaluate(0.0) == pytest.approx(0.0)
        
        # Ultimo breakpoint raggiungibile
        assert env_single_cycle_linear.evaluate(0.1) == pytest.approx(1.0)
        assert env_single_cycle_linear.evaluate(0.2) == pytest.approx(1.0)
    
    def test_negative_time(self, env_single_cycle_linear):
        """Tempo negativo: hold primo valore."""
        assert env_single_cycle_linear.evaluate(-1.0) == pytest.approx(0.0)
        assert env_single_cycle_linear.evaluate(-0.001) == pytest.approx(0.0)
    
    def test_zero_time(self, env_single_cycle_linear):
        """t=0 è valido."""
        assert env_single_cycle_linear.evaluate(0.0) == pytest.approx(0.0)
    
    def test_very_large_time(self, env_single_cycle_linear):
        """Tempo molto grande: ciclo continua."""
        # t=100.0 = 1000 cicli → ultimo breakpoint
        assert env_single_cycle_linear.evaluate(100.0) == pytest.approx(1.0, abs=1e-6)
        
        # t=100.025 = 1000.25 cicli
        assert env_single_cycle_linear.evaluate(100.025) == pytest.approx(0.25, abs=1e-6)
    
    def test_float_precision_edge(self, env_single_cycle_linear):
        """Edge case con precisione float."""
        # Ciclo: 0.1s
        # t=0.09999999999: dovrebbe essere quasi alla fine
        result = env_single_cycle_linear.evaluate(0.09999999999)
        assert result > 0.99
        
        # t=0.1: esattamente alla fine → valore 1.0
        assert env_single_cycle_linear.evaluate(0.1) == pytest.approx(1.0)
    
    def test_discontinuity_after_last_breakpoint(self, env_single_cycle_linear):
        """Discontinuità al wrap-around DOPO l'ultimo breakpoint."""
        # Ultimo breakpoint
        val_end = env_single_cycle_linear.evaluate(0.1)
        assert val_end == pytest.approx(1.0)
        
        # Subito dopo: wrap-around
        val_start = env_single_cycle_linear.evaluate(0.10001)
        assert val_start < 0.02
        
        # Discontinuità
        assert abs(val_end - val_start) > 0.98


# =============================================================================
# 8. TEST ULTIMO BREAKPOINT RAGGIUNGIBILE
# =============================================================================

class TestLastBreakpointReachable:
    """
    Test dedicati a verificare che l'ultimo breakpoint sia raggiungibile.
    Questo è il comportamento corretto per i cicli.
    """
    
    def test_simple_cycle_last_point(self):
        """Ciclo semplice: ultimo punto raggiungibile."""
        env = Envelope([[0, 0], [0.1, 1], 'cycle'])
        
        # t=0.1 deve valere 1.0
        assert env.evaluate(0.1) == pytest.approx(1.0)
        
        # t=0.2 deve valere 1.0 (secondo ciclo)
        assert env.evaluate(0.2) == pytest.approx(1.0)
    
    def test_offset_cycle_last_point(self):
        """Ciclo con offset: ultimo punto raggiungibile."""
        env = Envelope([[0.3, 0], [0.39, 1], 'cycle'])
        
        # t=0.39 deve valere 1.0
        assert env.evaluate(0.39) == pytest.approx(1.0)
        
        # t=0.48 deve valere 1.0 (secondo ciclo)
        assert env.evaluate(0.48) == pytest.approx(1.0)
        
        # t=0.57 deve valere 1.0 (terzo ciclo)
        assert env.evaluate(0.57) == pytest.approx(1.0)
    
    def test_three_point_cycle_last_point(self):
        """Ciclo con tre punti: ultimo punto raggiungibile."""
        env = Envelope([[0, 0], [0.05, 1], [0.1, 0.5], 'cycle'])
        
        # t=0.1 deve valere 0.5
        assert env.evaluate(0.1) == pytest.approx(0.5)
        
        # t=0.2 deve valere 0.5 (secondo ciclo)
        assert env.evaluate(0.2) == pytest.approx(0.5)
    
    def test_wrap_happens_after_last_point(self):
        """Wrap-around avviene DOPO l'ultimo punto, non su di esso."""
        env = Envelope([[0, 0], [0.1, 100], 'cycle'])
        
        # Esattamente su ultimo punto
        assert env.evaluate(0.1) == pytest.approx(100.0)
        
        # Epsilon dopo: wrap-around
        assert env.evaluate(0.1 + 1e-6) == pytest.approx(0.0, abs=0.01)
        assert env.evaluate(0.1 + 1e-3) == pytest.approx(1.0)
    
    def test_step_last_breakpoint_value(self):
        """Step: l'ultimo breakpoint restituisce il suo valore."""
        env = Envelope({
            'type': 'step',
            'points': [[0, 10], [0.1, 50], [0.2, 100], 'cycle']
        })
        
        # Esattamente su ultimo punto
        assert env.evaluate(0.2) == pytest.approx(100)
        
        # Appena dopo: wrap-around
        assert env.evaluate(0.20001) == pytest.approx(10)


# =============================================================================
# 9. TEST GESTIONE ERRORI
# =============================================================================

class TestErrorHandling:
    """Test validazione e gestione errori."""
    
    def test_cycle_with_one_breakpoint_error(self):
        """Ciclo con 1 solo breakpoint: errore."""
        with pytest.raises(ValueError, match="almeno 2 breakpoints"):
            Envelope([[0, 0], 'cycle'])
    
    def test_cycle_with_zero_breakpoints_error(self):
        """Ciclo senza breakpoints: errore."""
        with pytest.raises(ValueError, match="almeno 2 breakpoints"):
            Envelope(['cycle'])
    
    def test_invalid_string_marker(self):
        """Stringa diversa da 'cycle': errore."""
        with pytest.raises(ValueError, match="non riconosciuta"):
            Envelope([[0, 0], [0.1, 1], 'repeat'])
        
        with pytest.raises(ValueError, match="non riconosciuta"):
            Envelope([[0, 0], [0.1, 1], 'loop'])
    
    def test_invalid_breakpoint_format(self):
        """Formato breakpoint invalido: errore."""
        with pytest.raises(ValueError, match="non valido"):
            Envelope([[0, 0], [0.1], 'cycle'])  # Manca il valore
        
        with pytest.raises(ValueError, match="non valido"):
            Envelope([[0, 0], 0.1, 'cycle'])  # Non è lista
    
    def test_empty_envelope(self):
        """Envelope completamente vuoto: errore."""
        with pytest.raises(ValueError, match="almeno un breakpoint"):
            Envelope([])
    
    def test_invalid_type(self):
        """Tipo interpolazione invalido: errore."""
        with pytest.raises(ValueError, match="Tipo envelope non valido"):
            Envelope({
                'type': 'exponential',
                'points': [[0, 0], [0.1, 1], 'cycle']
            })
    
    def test_dict_missing_points(self):
        """Dict senza chiave 'points': errore."""
        with pytest.raises(KeyError):
            Envelope({'type': 'linear'})
    
    def test_non_dict_non_list_input(self):
        """Input né dict né list: errore."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            Envelope(42)
        
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            Envelope("[[0,0],[0.1,1]]")



# =============================================================================
# 11. TEST COMPATIBILITÀ
# =============================================================================

class TestBackwardCompatibility:
    """Test che envelope esistenti funzionino ancora."""
    
    def test_normal_envelope_still_works(self):
        """Envelope tradizionale funziona come prima."""
        env = Envelope([[0, 0], [0.5, 1], [1.0, 0]])
        
        assert env.evaluate(0.0) == pytest.approx(0.0)
        assert env.evaluate(0.25) == pytest.approx(0.5)
        assert env.evaluate(0.5) == pytest.approx(1.0)
        assert env.evaluate(0.75) == pytest.approx(0.5)
        assert env.evaluate(1.0) == pytest.approx(0.0)
        
        # Hold dopo fine
        assert env.evaluate(2.0) == pytest.approx(0.0)
    
    def test_single_breakpoint_constant(self):
        """Envelope con singolo breakpoint è costante."""
        env = Envelope([[0, 42]])
        
        assert env.evaluate(-1.0) == pytest.approx(42)
        assert env.evaluate(0.0) == pytest.approx(42)
        assert env.evaluate(100.0) == pytest.approx(42)
    
    def test_dict_without_cycle(self):
        """Dict senza 'cycle' funziona come prima."""
        env = Envelope({
            'type': 'cubic',
            'points': [[0, 0], [0.5, 1], [1.0, 0]]
        })
        
        assert env.type == 'cubic'
        assert not env.segments[0]['cycle']


# =============================================================================
# 12. TEST COMPLEX SCENARIOS
# =============================================================================

class TestComplexScenarios:
    """Test scenari complessi realistici."""
    
    def test_two_cycles_with_gap(self):
        """Due cicli separati da un gap temporale."""
        env = Envelope([
            [0, 0], [0.1, 1], 'cycle',       # Ciclo 1
            [0.5, 0.5], [0.7, 0.3], [1.0, 0], [1.05, 1], 'cycle'  # Ciclo 2 complesso
        ])
        
        # Primo ciclo
        assert env.evaluate(0.1) == pytest.approx(1.0)
        
        # Secondo ciclo (con 4 breakpoints)
        # A t=1.1: elapsed=0.6, cycle_dur=0.55, t_in_cycle=0.05, t_actual=0.55
        # Interpola tra [0.5,0.5] e [0.7,0.3]
        assert env.evaluate(1.1) == pytest.approx(0.45)  # VALORE CORRETTO!

    def test_very_short_cycle(self):
        """Ciclo molto breve (1ms)."""
        env = Envelope([[0, 0], [0.001, 1], 'cycle'])
        
        # t=0.001 = ultimo breakpoint primo ciclo
        assert env.evaluate(0.001) == pytest.approx(1.0, abs=1e-10)
        
        # t=0.01 = 10 cicli completi → ultimo breakpoint
        assert env.evaluate(0.01) == pytest.approx(1.0, abs=1e-8)
        
        # t=0.0105 = 10.5 cicli
        assert env.evaluate(0.0105) == pytest.approx(0.5, abs=1e-6)
    
    def test_many_breakpoints_in_cycle(self):
        """Ciclo con molti breakpoints."""
        env = Envelope([
            [0, 0],
            [0.1, 0.3],
            [0.2, 0.6],
            [0.3, 1.0],
            [0.4, 0.6],
            [0.5, 0.3],
            [0.6, 0],
            'cycle'
        ])
        
        assert env.evaluate(0.0) == pytest.approx(0.0)
        assert env.evaluate(0.3) == pytest.approx(1.0)
        assert env.evaluate(0.6) == pytest.approx(0.0)  # Ultimo breakpoint
        # t=0.9 = 1.5 cicli → t_in_cycle = 0.3 → valore 1.0
        assert env.evaluate(0.9) == pytest.approx(1.0)
        # t=1.2 = 2 cicli → ultimo breakpoint
        assert env.evaluate(1.2) == pytest.approx(0.0)


# =============================================================================
# 13. TEST PERFORMANCE
# =============================================================================

class TestPerformance:
    """Test performance per cicli con molte iterazioni."""
    
    def test_many_evaluations_fast(self, env_single_cycle_linear):
        """10000 valutazioni devono essere veloci."""
        import time
        
        start = time.time()
        for i in range(10000):
            env_single_cycle_linear.evaluate(i * 0.001)
        elapsed = time.time() - start
        
        # Dovrebbe richiedere < 0.1s
        assert elapsed < 0.1
    
    def test_very_large_time_efficient(self, env_single_cycle_linear):
        """Valutazione a tempi molto grandi è efficiente."""
        import time
        
        start = time.time()
        # t=10^6 = milione di secondi
        result = env_single_cycle_linear.evaluate(1_000_000.0)
        elapsed = time.time() - start
        
        # Modulo è O(1), dovrebbe essere istantaneo
        assert elapsed < 0.001
        # 10^6 % 0.1 = 0.0 → ultimo breakpoint
        assert result == pytest.approx(1.0, abs=1e-5)


# =============================================================================
# TEST INTEGRATE - ENVELOPE NORMALI
# =============================================================================

class TestIntegrateNormal:
    """Test integrale per envelope senza cicli."""
    
    def test_integrate_single_constant(self):
        """Envelope con singolo punto = costante."""
        env = Envelope([[0, 42]])
        # Integrale costante: base * altezza = 10 * 42 = 420
        assert env.integrate(0, 10) == pytest.approx(420.0)
    
    def test_integrate_linear_full_triangle(self):
        """Rampa lineare [0,0]->[10,100]: triangolo completo."""
        env = Envelope([[0, 0], [10, 100]])
        # Area triangolo: (base * altezza) / 2 = (10 * 100) / 2 = 500
        assert env.integrate(0, 10) == pytest.approx(500.0)
    
    def test_integrate_linear_partial(self):
        """Integrale parziale di rampa lineare."""
        env = Envelope([[0, 0], [10, 100]])
        # Da 0 a 5: triangolo più piccolo (5 * 50) / 2 = 125
        assert env.integrate(0, 5) == pytest.approx(125.0)
        # Da 5 a 10: trapezio con h=5, base1=50, base2=100
        # Area = h * (b1 + b2) / 2 = 5 * 150 / 2 = 375
        assert env.integrate(5, 10) == pytest.approx(375.0)
    
    def test_integrate_step_single_level(self):
        """Step con un solo gradino."""
        env = Envelope({'type': 'step', 'points': [[0, 10], [5, 10]]})
        # Rettangolo: 5 * 10 = 50
        assert env.integrate(0, 5) == pytest.approx(50.0)
    
    def test_integrate_step_multiple_levels(self):
        """Step con gradini multipli."""
        env = Envelope({
            'type': 'step',
            'points': [[0, 10], [5, 50], [10, 100]]
        })
        # Gradino 1 (0-5): 5 * 10 = 50
        # Gradino 2 (5-10): 5 * 50 = 250
        # Totale: 300
        assert env.integrate(0, 10) == pytest.approx(300.0)
    
    def test_integrate_cubic_simple_ramp(self):
        """Cubic semplice: verifica con integrazione numerica."""
        env = Envelope({'type': 'cubic', 'points': [[0, 0], [10, 100]]})
        # Per una rampa semplice, cubic dovrebbe dare circa 500
        # (tolleranza maggiore per integrazione numerica)
        assert env.integrate(0, 10) == pytest.approx(500.0, rel=1e-2)
    
    def test_integrate_reverse_interval(self):
        """Integrale da to_time > from_time: negativo."""
        env = Envelope([[0, 0], [10, 100]])
        # integrate(10, 0) = -integrate(0, 10)
        forward = env.integrate(0, 10)
        backward = env.integrate(10, 0)
        assert backward == pytest.approx(-forward)
    
    def test_integrate_zero_interval(self):
        """Integrale con from_time == to_time: zero."""
        env = Envelope([[0, 0], [10, 100]])
        assert env.integrate(5, 5) == pytest.approx(0.0)
    
    def test_integrate_outside_envelope_hold(self):
        """Integrale oltre i breakpoints: hold ultimo valore."""
        env = Envelope([[0, 0], [10, 100]])
        # Da 10 a 15: rettangolo 5 * 100 = 500
        assert env.integrate(10, 15) == pytest.approx(500.0)
    
    def test_integrate_before_envelope_hold(self):
        """Integrale prima dei breakpoints: hold primo valore."""
        env = Envelope([[5, 50], [10, 100]])
        # Da 0 a 5: rettangolo 5 * 50 = 250
        assert env.integrate(0, 5) == pytest.approx(250.0)
    
    def test_integrate_spans_multiple_segments(self):
        """Integrale che attraversa più segmenti."""
        env = Envelope([[0, 0], [5, 50], [10, 0]])
        # Segmento 1 (0-5): triangolo (5 * 50) / 2 = 125
        # Segmento 2 (5-10): triangolo (5 * 50) / 2 = 125
        # Totale: 250
        assert env.integrate(0, 10) == pytest.approx(250.0)


# =============================================================================
# TEST INTEGRATE - CICLI SINGOLI
# =============================================================================

class TestIntegrateSingleCycle:
    """Test integrale per envelope con un solo ciclo."""
    
    def test_integrate_cycle_single_period(self):
        """Integrale di esattamente un periodo di ciclo."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        # Un ciclo completo: triangolo (1 * 10) / 2 = 5
        assert env.integrate(0, 1) == pytest.approx(5.0)
    
    def test_integrate_cycle_two_periods(self):
        """Integrale di due periodi completi."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        # Due cicli completi: 2 * 5 = 10
        assert env.integrate(0, 2) == pytest.approx(10.0)
    
    def test_integrate_cycle_fractional_period(self):
        """Integrale di 1.5 periodi."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        # 1 ciclo completo = 5
        # + 0.5 ciclo = (0.5 * 5) / 2 = 1.25
        # Totale: 6.25
        assert env.integrate(0, 1.5) == pytest.approx(6.25)
    
    def test_integrate_cycle_partial_start(self):
        """Integrale che inizia a metà del primo ciclo."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        # Da 0.5 a 1.5:
        # - Fino alla fine del primo ciclo: trapezio
        # - Un ciclo completo: triangolo = 5
        # Approssimato: ~7.5
        result = env.integrate(0.5, 1.5)
        assert 7.0 < result < 8.0
    
    def test_integrate_cycle_many_periods(self):
        """Integrale di molti periodi (test efficienza)."""
        env = Envelope([[0, 0], [0.1, 1], 'cycle'])
        # Ciclo = (0.1 * 1) / 2 = 0.05
        # 100 cicli = 100 * 0.05 = 5.0
        assert env.integrate(0, 10) == pytest.approx(5.0, rel=1e-2)
    
    def test_integrate_cycle_step_type(self):
        """Ciclo con interpolazione step."""
        env = Envelope({
            'type': 'step',
            'points': [[0, 5], [1, 5], 'cycle']
        })
        # Rettangolo costante: 3 * 5 = 15
        assert env.integrate(0, 3) == pytest.approx(15.0)
    
    def test_integrate_cycle_cubic_type(self):
        """Ciclo con interpolazione cubic."""
        env = Envelope({
            'type': 'cubic',
            'points': [[0, 0], [0.5, 10], [1, 0], 'cycle']
        })
        # Ciclo simmetrico: area circa 5 per ciclo
        # 2 cicli: circa 10
        result = env.integrate(0, 2)
        assert 9.0 < result < 11.0


# =============================================================================
# TEST INTEGRATE - CICLI MULTIPLI
# =============================================================================

class TestIntegrateMultipleCycles:
    """Test integrale per envelope con cicli multipli."""
    
    def test_integrate_two_separate_cycles(self):
        """Due cicli separati."""
        env = Envelope([
            [0, 0], [1, 10], 'cycle',    # Ciclo 1: area = 5
            [5, 0], [6, 20], 'cycle'     # Ciclo 2: area = 10
        ])
        # Integrale 0-1: primo ciclo = 5
        assert env.integrate(0, 1) == pytest.approx(5.0)
        # Integrale 5-6: secondo ciclo = 10
        assert env.integrate(5, 6) == pytest.approx(10.0)
        # Integrale che attraversa entrambi: 0-7
        # Ciclo 1 (0-1): 5
        # Gap (1-5): 10 * 4 = 40 (hold ultimo valore)
        # Ciclo 2 (5-6): 10
        # Dopo ciclo 2 (6-7): 20 * 1 = 20
        # Totale: 75
        result = env.integrate(0, 7)
        assert result == pytest.approx(75.0, rel=1e-2)
    
    def test_integrate_adjacent_cycles(self):
        """Due cicli adiacenti senza gap."""
        env = Envelope([
            [0, 0], [1, 10], 'cycle',
            [1, 0], [2, 5], 'cycle'
        ])
        # Primo ciclo (0-1): 5
        # Secondo ciclo (1-2): 2.5
        result = env.integrate(0, 2)
        assert result == pytest.approx(7.5, rel=1e-2)


# =============================================================================
# TEST INTEGRATE - MIX CICLICO + NON CICLICO
# =============================================================================

class TestIntegrateMixedSegments:
    """Test integrale per envelope con mix ciclico + normale."""
    
    def test_integrate_cycle_then_normal(self):
        """Ciclo seguito da segmento normale."""
        env = Envelope([
            [0, 0], [1, 10], 'cycle',    # Ciclo
            [5, 10], [10, 0]             # Rampa discendente
        ])
        # Integrale completo 0-10:
        # Ciclo (0-1): 5
        # Hold (1-5): 10 * 4 = 40
        # Rampa (5-10): trapezio = 5 * 10 / 2 = 25
        # Totale: 70
        result = env.integrate(0, 10)
        assert result == pytest.approx(70.0, rel=1e-2)
    
    def test_integrate_normal_then_cycle(self):
        """Segmento normale seguito da ciclo."""
        env = Envelope([
            [0, 0], [5, 50],             # Rampa ascendente
            [5, 0], [6, 10], 'cycle'     # Ciclo
        ])
        # Rampa (0-5): 125
        # Ciclo (5-6): 5
        # Totale: 130
        result = env.integrate(0, 6)
        assert result == pytest.approx(130.0, rel=1e-2)
    
    def test_integrate_only_normal_part(self):
        """Integrale solo sul segmento normale di un mix."""
        env = Envelope([
            [0, 0], [1, 10], 'cycle',
            [5, 10], [10, 0]
        ])
        # Solo la rampa discendente (5-10): 25
        result = env.integrate(5, 10)
        assert result == pytest.approx(25.0, rel=1e-2)
    
    def test_integrate_only_cycle_part(self):
        """Integrale solo sul segmento ciclico di un mix."""
        env = Envelope([
            [0, 0], [1, 10], 'cycle',
            [5, 10], [10, 0]
        ])
        # Due periodi del ciclo: 2 * 5 = 10
        result = env.integrate(0, 2)
        assert result == pytest.approx(10.0, rel=1e-2)


# =============================================================================
# TEST INTEGRATE - EDGE CASES
# =============================================================================

class TestIntegrateEdgeCases:
    """Test casi limite per integrate."""
    
    def test_integrate_very_short_cycle(self):
        """Ciclo molto breve (precisione floating point)."""
        env = Envelope([[0, 0], [0.001, 1], 'cycle'])
        # 1000 cicli in 1 secondo
        # Area ciclo = (0.001 * 1) / 2 = 0.0005
        # 1000 cicli = 0.5
        result = env.integrate(0, 1)
        assert result == pytest.approx(0.5, rel=1e-2)
    
    def test_integrate_phase_boundary(self):
        """Integrale che termina esattamente su un multiplo del ciclo."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        # Esattamente 3 cicli: 3 * 5 = 15
        assert env.integrate(0, 3) == pytest.approx(15.0)
        # Esattamente 3.0 con epsilon
        assert env.integrate(0, 3.0000001) == pytest.approx(15.0, rel=1e-2)
    
    def test_integrate_offset_start(self):
        """Ciclo che non inizia a t=0."""
        env = Envelope([[2, 0], [3, 10], 'cycle'])
        # Prima del ciclo (0-2): 0 * 2 = 0
        # Un ciclo (2-3): 5
        # Totale (0-3): 5
        result = env.integrate(0, 3)
        assert result == pytest.approx(5.0, rel=1e-2)
    
    def test_integrate_asymmetric_cycle(self):
        """Ciclo asimmetrico con salita e discesa diverse."""
        env = Envelope([[0, 0], [0.3, 10], [1, 0], 'cycle'])
        # Ciclo asimmetrico: area ≈ 5
        result = env.integrate(0, 1)
        assert 4.5 < result < 5.5
    
    def test_integrate_tolerance_accumulation(self):
        """Test che l'errore numerico non si accumuli eccessivamente."""
        env = Envelope([[0, 0], [0.01, 1], 'cycle'])
        # 1000 cicli: ogni ciclo area = 0.005
        # Totale teorico = 5.0
        result = env.integrate(0, 10)
        # Tolleranza 1% per accumulo errori numerici
        assert result == pytest.approx(5.0, rel=1e-2)


# =============================================================================
# TEST INTEGRATE - VERIFICHE MATEMATICHE
# =============================================================================

class TestIntegrateMathematicalProperties:
    """Test proprietà matematiche dell'integrale."""
    
    def test_integrate_additivity(self):
        """Proprietà additiva: ∫[a,c] = ∫[a,b] + ∫[b,c]."""
        env = Envelope([[0, 0], [10, 100]])
        full = env.integrate(0, 10)
        part1 = env.integrate(0, 5)
        part2 = env.integrate(5, 10)
        assert full == pytest.approx(part1 + part2)
    
    def test_integrate_linearity_scaling(self):
        """Se scaliamo i valori 2x, l'integrale scala 2x."""
        env1 = Envelope([[0, 0], [10, 50]])
        env2 = Envelope([[0, 0], [10, 100]])
        area1 = env1.integrate(0, 10)
        area2 = env2.integrate(0, 10)
        # env2 ha valori doppi → area doppia
        assert area2 == pytest.approx(2 * area1)
    
    def test_integrate_time_scaling(self):
        """Se scaliamo il tempo 2x, l'integrale scala 2x."""
        env1 = Envelope([[0, 0], [5, 100]])
        env2 = Envelope([[0, 0], [10, 100]])
        area1 = env1.integrate(0, 5)
        area2 = env2.integrate(0, 10)
        # Stessa altezza, base doppia → area doppia
        assert area2 == pytest.approx(2 * area1)
    
    def test_integrate_symmetry(self):
        """Envelope simmetrico ha area prevedibile."""
        # Triangolo simmetrico salita+discesa
        env = Envelope([[0, 0], [5, 100], [10, 0]])
        area = env.integrate(0, 10)
        # Area totale = base * altezza / 2 = 10 * 100 / 2 = 500
        assert area == pytest.approx(500.0)
    
    def test_integrate_cycle_consistency(self):
        """N cicli = N * (area di 1 ciclo)."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        one_cycle = env.integrate(0, 1)
        five_cycles = env.integrate(0, 5)
        assert five_cycles == pytest.approx(5 * one_cycle)


# =============================================================================
# TEST INTEGRATE - CASI SPECIALI PER CUBIC
# =============================================================================

class TestIntegrateCubicSpecial:
    """Test specifici per integrazione cubic (numerica)."""
    
    def test_integrate_cubic_flat_plateau(self):
        """Cubic con plateau piatto."""
        env = Envelope({
            'type': 'cubic',
            'points': [[0, 0], [1, 10], [2, 10], [3, 0]]
        })
        # Salita (0-1): ~5
        # Plateau (1-2): 10
        # Discesa (2-3): ~5
        # Totale: ~20
        result = env.integrate(0, 3)
        assert 19 < result < 21
    
    def test_integrate_cubic_overshoot_prevention(self):
        """Cubic Fritsch-Carlson non deve overshooting."""
        # Plateau [1,10]->[2,10] deve restare a 10
        env = Envelope({
            'type': 'cubic',
            'points': [[0, 0], [1, 10], [2, 10], [3, 0]]
        })
        # Integrale su plateau (1-2): deve essere esattamente 10
        result = env.integrate(1, 2)
        assert result == pytest.approx(10.0, rel=1e-2)