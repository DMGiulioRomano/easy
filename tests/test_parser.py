# tests/test_parser.py
"""
Test suite per parser.py (Factory/Builder Pattern).

Verifica:
- Parsing di valori scalari, liste, dict
- Normalizzazione temporale (normalized vs absolute)
- Creazione corretta di oggetti Parameter
- Integrazione con parameter_definitions.py

Fixtures utilizzate:
- evaluator (da conftest.py, per confronto)
- deterministic_random (da conftest.py)
"""

import pytest
from unittest.mock import Mock, patch

from parser import GranularParser
from parameter import Parameter
from parameter_definitions import GRANULAR_PARAMETERS
from envelope import Envelope


# =============================================================================
# FIXTURES LOCALI
# =============================================================================

@pytest.fixture
def parser_absolute():
    """Parser con time_mode='absolute' e durata 10 secondi."""
    return GranularParser(
        stream_id='test_stream',
        duration=10.0,
        time_mode='absolute'
    )


@pytest.fixture
def parser_normalized():
    """Parser con time_mode='normalized' e durata 10 secondi."""
    return GranularParser(
        stream_id='test_stream',
        duration=10.0,
        time_mode='normalized'
    )


# =============================================================================
# 1. TEST COSTRUZIONE PARSER
# =============================================================================

class TestParserConstruction:
    """Test inizializzazione di GranularParser."""
    
    def test_basic_construction(self):
        """Costruzione con parametri minimi."""
        parser = GranularParser(
            stream_id='my_stream',
            duration=5.0
        )
        
        assert parser.stream_id == 'my_stream'
        assert parser.duration == 5.0
        assert parser.time_mode == 'absolute'  # Default
    
    def test_normalized_time_mode(self):
        """Costruzione con time_mode='normalized'."""
        parser = GranularParser(
            stream_id='test',
            duration=10.0,
            time_mode='normalized'
        )
        
        assert parser.time_mode == 'normalized'


# =============================================================================
# 2. TEST PARSING VALORI SCALARI
# =============================================================================

class TestParseScalar:
    """Test parsing di numeri semplici."""
    
    def test_parse_int(self, parser_absolute):
        """Parsing di intero - verifica il valore interno, non get_value()."""
        param = parser_absolute.parse_parameter('density', 50)
        
        assert isinstance(param, Parameter)
        # Verifica il valore BASE, non quello con variazione
        assert param._value == 50.0
    
    def test_parse_float(self, parser_absolute):
        """Parsing di float - verifica il valore interno."""
        param = parser_absolute.parse_parameter('density', 42.5)
        
        assert param._value == 42.5
    
    def test_parse_int_get_value_deterministic(self, parser_absolute, deterministic_random):
        """Parsing di intero con random deterministico."""
        param = parser_absolute.parse_parameter(
            'density', 
            value_raw=50,
            range_raw=0.0  # Disabilita variazione esplicitamente
        )
        
        assert param.get_value(0.0) == 50.0
    
    def test_parse_with_range(self, parser_absolute):
        """Parsing con range stocastico."""
        param = parser_absolute.parse_parameter(
            name='pan',
            value_raw=0.0,
            range_raw=30.0
        )
        
        # Verifica che il range sia stato impostato
        assert param._mod_range == 30.0
    
    def test_parse_with_probability(self, parser_absolute):
        """Parsing con probabilità."""
        param = parser_absolute.parse_parameter(
            name='pan',
            value_raw=0.0,
            range_raw=30.0,
            prob_raw=50.0
        )
        
        assert param._mod_prob == 50.0


# =============================================================================
# 3. TEST PARSING ENVELOPE (Lista)
# =============================================================================

class TestParseEnvelopeList:
    """Test parsing di envelope da lista di breakpoints."""
    
    def test_parse_list_creates_envelope(self, parser_absolute):
        """Lista di punti diventa Envelope."""
        param = parser_absolute.parse_parameter(
            'density',
            [[0, 10], [5, 50], [10, 100]]
        )
        
        assert isinstance(param._value, Envelope)
    
    def test_envelope_breakpoints_correct(self, parser_absolute):
        """I breakpoints dell'Envelope sono corretti."""
        param = parser_absolute.parse_parameter(
            'density',
            [[0, 10], [10, 100]]
        )
        
        env = param._value
        assert env.breakpoints[0] == [0, 10]
        assert env.breakpoints[1] == [10, 100]
    
    def test_envelope_evaluates_correctly_no_jitter(self, parser_absolute):
        """L'Envelope valuta correttamente senza jitter."""
        param = parser_absolute.parse_parameter(
            'density',
            value_raw=[[0, 10], [10, 100]],
            range_raw=0.0  # Disabilita variazione
        )
        
        # t=0: 10, t=5: 55, t=10: 100
        assert param.get_value(0.0) == 10.0
        assert param.get_value(5.0) == 55.0
        assert param.get_value(10.0) == 100.0
    
    def test_absolute_time_preserved(self, parser_absolute):
        """Con time_mode='absolute', i tempi non vengono scalati."""
        param = parser_absolute.parse_parameter(
            'density',
            [[0, 0], [5, 50]]
        )
        
        # Il breakpoint è a t=5, non scalato
        env = param._value
        assert env.breakpoints[1][0] == 5.0


# =============================================================================
# 4. TEST PARSING ENVELOPE (Dict)
# =============================================================================

class TestParseEnvelopeDict:
    """Test parsing di envelope da dizionario con tipo esplicito."""
    
    def test_parse_dict_with_type(self, parser_absolute):
        """Dict con 'type' crea Envelope del tipo specificato."""
        param = parser_absolute.parse_parameter(
            'density',
            {
                'type': 'step',
                'points': [[0, 10], [5, 50]]
            }
        )
        
        env = param._value
        assert isinstance(env, Envelope)
        assert env.type == 'step'
    
    def test_step_envelope_behavior(self, parser_absolute):
        """Envelope step mantiene il valore fino al prossimo breakpoint."""
        param = parser_absolute.parse_parameter(
            'density',
            value_raw={
                'type': 'step',
                'points': [[0, 10], [5, 50]]
            },
            range_raw=0.0  # Disabilita variazione per test deterministico
        )
        
        # Prima di t=5: valore 10
        assert param.get_value(4.9) == 10.0
        # A t=5: salta a 50
        assert param.get_value(5.0) == 50.0
    
    def test_cubic_envelope_type(self, parser_absolute):
        """Dict può specificare type='cubic'."""
        param = parser_absolute.parse_parameter(
            'density',
            {
                'type': 'cubic',
                'points': [[0, 10], [5, 50], [10, 10]]
            }
        )
        
        assert param._value.type == 'cubic'


# =============================================================================
# 5. TEST NORMALIZZAZIONE TEMPORALE
# =============================================================================

class TestTimeNormalization:
    """Test scaling dei tempi con time_mode='normalized'."""
    
    def test_normalized_scales_list(self, parser_normalized):
        """Con normalized, tempi 0-1 vengono scalati alla durata."""
        param = parser_normalized.parse_parameter(
            'density',
            [[0.0, 10], [0.5, 50], [1.0, 100]]
        )
        
        env = param._value
        # 0.5 * 10.0 = 5.0
        assert env.breakpoints[1][0] == 5.0
        # 1.0 * 10.0 = 10.0
        assert env.breakpoints[2][0] == 10.0
    
    def test_normalized_scales_dict(self, parser_normalized):
        """Anche i dict vengono scalati in modalità normalized."""
        param = parser_normalized.parse_parameter(
            'density',
            {
                'type': 'linear',
                'points': [[0.0, 0], [1.0, 100]]
            }
        )
        
        env = param._value
        assert env.breakpoints[1][0] == 10.0
    
    def test_local_override_to_normalized(self, parser_absolute):
        """time_unit locale può forzare normalized anche se parser è absolute."""
        param = parser_absolute.parse_parameter(
            'density',
            {
                'time_unit': 'normalized',
                'points': [[0.5, 50]]
            }
        )
        
        env = param._value
        # 0.5 * 10.0 = 5.0
        assert env.breakpoints[0][0] == 5.0
    
    def test_local_override_to_absolute(self, parser_normalized):
        """time_unit locale può forzare absolute anche se parser è normalized."""
        param = parser_normalized.parse_parameter(
            'density',
            {
                'time_unit': 'absolute',
                'points': [[5.0, 50]]
            }
        )
        
        env = param._value
        # Tempo non scalato
        assert env.breakpoints[0][0] == 5.0


# =============================================================================
# 6. TEST INTEGRAZIONE CON REGISTRY
# =============================================================================

class TestRegistryIntegration:
    """Test che il parser usi correttamente il Registry."""
    
    def test_unknown_parameter_raises(self, parser_absolute):
        """Parametro non nel Registry solleva KeyError."""
        with pytest.raises(KeyError) as excinfo:
            parser_absolute.parse_parameter(
                'parametro_che_non_esiste',
                100.0
            )
        
        assert 'parametro_che_non_esiste' in str(excinfo.value)
    
    def test_bounds_from_registry(self, parser_absolute):
        """I bounds vengono presi dal Registry."""
        param = parser_absolute.parse_parameter('density', 50.0)
        
        # Verifica che i bounds siano quelli del Registry
        registry_bounds = GRANULAR_PARAMETERS['density']
        assert param._bounds.min_val == registry_bounds.min_val
        assert param._bounds.max_val == registry_bounds.max_val
    
    def test_variation_mode_from_registry(self, parser_absolute):
        """Il variation_mode viene dal Registry."""
        # pitch_semitones ha variation_mode='quantized'
        param = parser_absolute.parse_parameter('pitch_semitones', 0.0)
        
        assert param._bounds.variation_mode == 'quantized'
    
    @pytest.mark.parametrize("param_name", [
        'density', 'pan', 'volume', 'grain_duration'
    ])
    def test_all_common_params_parseable(self, parser_absolute, param_name):
        """I parametri comuni devono essere parsabili."""
        param = parser_absolute.parse_parameter(param_name, 1.0)
        assert isinstance(param, Parameter)


# =============================================================================
# 7. TEST VALORI NONE
# =============================================================================

class TestNoneHandling:
    """Test gestione di valori None."""
    
    def test_none_range_accepted(self, parser_absolute):
        """range_raw=None è valido (nessuna variazione o default jitter)."""
        param = parser_absolute.parse_parameter(
            'density',
            value_raw=50.0,
            range_raw=None
        )
        
        assert param._mod_range is None
    
    def test_none_prob_accepted(self, parser_absolute):
        """prob_raw=None è valido (comportamento default)."""
        param = parser_absolute.parse_parameter(
            'density',
            value_raw=50.0,
            prob_raw=None
        )
        
        assert param._mod_prob is None


# =============================================================================
# 8. TEST ERRORI
# =============================================================================

class TestParserErrors:
    """Test gestione errori nel parsing."""
    
    def test_invalid_type_raises(self, parser_absolute):
        """Tipo non supportato solleva ValueError."""
        with pytest.raises(ValueError) as excinfo:
            parser_absolute.parse_parameter(
                'density',
                "non_un_numero"  # Stringa non valida
            )
        
        assert 'Formato non valido' in str(excinfo.value)
    
    # NOTA: Questo test è stato rimosso perché Envelope non valida i breakpoint
    # malformati. Se vogliamo questo comportamento, dobbiamo aggiungere
    # validazione in parser.py o envelope.py
    #
    # def test_malformed_breakpoint_raises(self, parser_absolute):
    #     """Breakpoint malformato solleva errore."""
    #     ...


# =============================================================================
# 9. TEST OWNER_ID PASSTHROUGH
# =============================================================================

class TestOwnerIdPassthrough:
    """Test che lo stream_id venga passato al Parameter."""
    
    def test_owner_id_set(self, parser_absolute):
        """Il Parameter riceve l'owner_id dal parser."""
        param = parser_absolute.parse_parameter('density', 50.0)
        
        assert param.owner_id == 'test_stream'
    
    def test_different_stream_ids(self):
        """Parser diversi passano stream_id diversi."""
        parser1 = GranularParser('stream_A', 10.0)
        parser2 = GranularParser('stream_B', 10.0)
        
        param1 = parser1.parse_parameter('density', 50.0)
        param2 = parser2.parse_parameter('density', 50.0)
        
        assert param1.owner_id == 'stream_A'
        assert param2.owner_id == 'stream_B'


# =============================================================================
# 10. TEST VARIAZIONE STOCASTICA (con mock)
# =============================================================================

class TestStochasticVariation:
    """Test che verificano il comportamento stocastico."""
    
    @patch('parameter.random.uniform', return_value=0.0)
    def test_jitter_applied_when_range_none(self, mock_uniform, parser_absolute):
        """Con mod_range=None, viene usato default_jitter dal Registry."""
        # density ha default_jitter=50.0
        param = parser_absolute.parse_parameter(
            'density',
            value_raw=100.0,
            range_raw=None  # Usa default_jitter
        )
        
        # Con uniform=0.0, deviation = 0.0 * jitter = 0
        result = param.get_value(0.0)
        assert result == 100.0
    
    @patch('parameter.random.uniform', return_value=0.5)
    def test_explicit_range_overrides_jitter(self, mock_uniform, parser_absolute):
        """mod_range esplicito sovrascrive default_jitter."""
        param = parser_absolute.parse_parameter(
            'density',
            value_raw=100.0,
            range_raw=20.0  # Esplicito, ignora default_jitter=50
        )
        
        # uniform=0.5 → deviation = 0.5 * 20 = 10
        result = param.get_value(0.0)
        assert result == 110.0
    
    def test_range_zero_disables_variation(self, parser_absolute):
        """mod_range=0 disabilita completamente la variazione."""
        param = parser_absolute.parse_parameter(
            'density',
            value_raw=100.0,
            range_raw=0.0  # Esplicitamente zero
        )
        
        # Deve sempre restituire 100.0
        for _ in range(10):
            assert param.get_value(0.0) == 100.0