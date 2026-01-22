# tests/test_parameter_factory.py
"""
Test suite per parameter_factory.py

Verifica:
- Costruzione di ParameterFactory
- Navigazione YAML con dot notation (_get_nested)
- Risoluzione probabilità dephase (_resolve_dephase_prob)
- Creazione parametri smart e raw
- Integrazione con GranularParser
- create_all_parameters() e create_single_parameter()
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from parameter_factory import ParameterFactory
from parameter_schema import ParameterSpec, STREAM_PARAMETER_SCHEMA
from parameter import Parameter
from envelope import Envelope


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def factory():
    """Factory standard per test."""
    return ParameterFactory(
        stream_id='test_stream',
        duration=10.0,
        time_mode='absolute'
    )


@pytest.fixture
def factory_normalized():
    """Factory con time_mode='normalized'."""
    return ParameterFactory(
        stream_id='test_stream',
        duration=10.0,
        time_mode='normalized'
    )


@pytest.fixture
def minimal_yaml():
    """YAML minimo con solo parametri obbligatori."""
    return {
        'volume': -6.0,
        'pan': 0.0,
        'grain': {
            'duration': 0.05,
            'envelope': 'hanning'
        }
    }


@pytest.fixture
def full_yaml():
    """YAML completo con range e dephase."""
    return {
        'volume': -6.0,
        'volume_range': 3.0,
        'pan': 45.0,
        'pan_range': 30.0,
        'grain': {
            'duration': 0.05,
            'duration_range': 0.01,
            'envelope': 'gaussian',
            'reverse': 0
        },
        'dephase': {
            'pc_rand_volume': 50.0,
            'pc_rand_pan': 100.0,
            'pc_rand_duration': 25.0,
            'pc_rand_reverse': 10.0
        }
    }


# =============================================================================
# 1. TEST COSTRUZIONE FACTORY
# =============================================================================

class TestFactoryConstruction:
    """Test inizializzazione di ParameterFactory."""
    
    def test_basic_construction(self):
        """Costruzione con parametri minimi."""
        factory = ParameterFactory(
            stream_id='my_stream',
            duration=5.0
        )
        
        assert factory._stream_id == 'my_stream'
    
    def test_default_time_mode(self):
        """time_mode default è 'absolute'."""
        factory = ParameterFactory('test', 10.0)
        
        # Verifichiamo indirettamente tramite il parser interno
        assert factory._parser.time_mode == 'absolute'
    
    def test_normalized_time_mode(self):
        """time_mode può essere 'normalized'."""
        factory = ParameterFactory('test', 10.0, time_mode='normalized')
        
        assert factory._parser.time_mode == 'normalized'
    
    def test_parser_receives_correct_params(self):
        """Il parser interno riceve i parametri corretti."""
        factory = ParameterFactory(
            stream_id='stream_42',
            duration=15.0,
            time_mode='normalized'
        )
        
        assert factory._parser.stream_id == 'stream_42'
        assert factory._parser.duration == 15.0
        assert factory._parser.time_mode == 'normalized'


# =============================================================================
# 2. TEST _get_nested() - NAVIGAZIONE DOT NOTATION
# =============================================================================

class TestGetNested:
    """Test del metodo statico per navigazione YAML."""
    
    def test_simple_path(self):
        """Percorso semplice senza dot."""
        data = {'volume': -6.0}
        result = ParameterFactory._get_nested(data, 'volume', 0.0)
        
        assert result == -6.0
    
    def test_nested_one_level(self):
        """Percorso nested a un livello."""
        data = {'grain': {'duration': 0.05}}
        result = ParameterFactory._get_nested(data, 'grain.duration', 0.0)
        
        assert result == 0.05
    
    def test_nested_two_levels(self):
        """Percorso nested a due livelli."""
        data = {'audio': {'grain': {'duration': 0.1}}}
        result = ParameterFactory._get_nested(data, 'audio.grain.duration', 0.0)
        
        assert result == 0.1
    
    def test_missing_key_returns_default(self):
        """Chiave mancante ritorna il default."""
        data = {'volume': -6.0}
        result = ParameterFactory._get_nested(data, 'missing', 42.0)
        
        assert result == 42.0
    
    def test_missing_nested_key_returns_default(self):
        """Chiave nested mancante ritorna il default."""
        data = {'grain': {'duration': 0.05}}
        result = ParameterFactory._get_nested(data, 'grain.missing', 99.0)
        
        assert result == 99.0
    
    def test_missing_parent_returns_default(self):
        """Parent mancante ritorna il default."""
        data = {'volume': -6.0}
        result = ParameterFactory._get_nested(data, 'grain.duration', 0.05)
        
        assert result == 0.05
    
    def test_empty_dict_returns_default(self):
        """Dict vuoto ritorna il default."""
        data = {}
        result = ParameterFactory._get_nested(data, 'any.path', 'default')
        
        assert result == 'default'
    
    def test_none_value_is_returned(self):
        """None come valore (non default) viene ritornato."""
        data = {'value': None}
        result = ParameterFactory._get_nested(data, 'value', 'default')
        
        assert result is None
    
    def test_returns_complex_types(self):
        """Può ritornare tipi complessi (liste, dict)."""
        data = {'envelope': [[0, 0], [10, 100]]}
        result = ParameterFactory._get_nested(data, 'envelope', None)
        
        assert result == [[0, 0], [10, 100]]
    
    def test_default_can_be_any_type(self):
        """Il default può essere di qualsiasi tipo."""
        data = {}
        
        assert ParameterFactory._get_nested(data, 'x', 42) == 42
        assert ParameterFactory._get_nested(data, 'x', 'str') == 'str'
        assert ParameterFactory._get_nested(data, 'x', [1, 2]) == [1, 2]
        assert ParameterFactory._get_nested(data, 'x', None) is None


# =============================================================================
# 3. TEST _resolve_dephase_prob() - LOGICA DEPHASE
# =============================================================================

class TestResolveDephaseProb:
    """Test risoluzione probabilità dephase."""
    
    def test_no_dephase_key_returns_none(self, factory):
        """Se spec non ha dephase_key, ritorna None."""
        spec = ParameterSpec(
            name='test',
            yaml_path='test',
            default=0,
            dephase_key=None  # Nessun dephase
        )
        
        # Passiamo range_val=None (o qualsiasi cosa, tanto esce subito)
        result = factory._resolve_dephase_prob(spec, {'pc_rand_test': 50}, range_val=None)
        assert result is None
    
    def test_dephase_none_returns_none(self, factory):
        """Se dephase è None (assente nel YAML), ritorna None."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            dephase_key='pc_rand_volume'
        )
        
        result = factory._resolve_dephase_prob(spec, None, range_val=None)
        assert result is None
    
    # --- NUOVI TEST PER LA LOGICA JITTER IMPLICITO ---

    def test_implicit_jitter_when_range_is_missing(self, factory):
        """
        CRUCIALE: Se dephase esiste, chiave manca, e range manca -> Jitter Implicito (1.0).
        """
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            dephase_key='pc_rand_volume'
        )
        
        # dephase vuoto, range_val None
        result = factory._resolve_dephase_prob(spec, {}, range_val=None)
        
        # Deve ritornare la costante importata (che è 1.0)
        from parameter_definitions import IMPLICIT_JITTER_PROB
        assert result == IMPLICIT_JITTER_PROB
    
    def test_explicit_range_implies_100_percent(self, factory):
        """
        CRUCIALE: Se dephase esiste, chiave manca, MA range c'è -> 100% (None).
        """
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            dephase_key='pc_rand_volume'
        )
        
        # dephase vuoto, ma range_val è definito (es. 0.5)
        result = factory._resolve_dephase_prob(spec, {}, range_val=0.5)
        
        assert result is None  # None significa 100% nella logica Parameter

    # --- FINE NUOVI TEST ---

    def test_dephase_key_present_returns_value(self, factory):
        """Se la chiave dephase è presente, ritorna il valore."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            dephase_key='pc_rand_volume'
        )
        
        result = factory._resolve_dephase_prob(spec, {'pc_rand_volume': 75.0}, range_val=None)
        assert result == 75.0
    
    def test_dephase_value_zero_is_returned(self, factory):
        """Valore 0 viene ritornato (non confuso con None)."""
        spec = ParameterSpec(
            name='pan',
            yaml_path='pan',
            default=0,
            dephase_key='pc_rand_pan'
        )
        
        result = factory._resolve_dephase_prob(spec, {'pc_rand_pan': 0}, range_val=None)
        assert result == 0
    
    def test_dephase_value_100_is_returned(self, factory):
        """Valore 100 viene ritornato correttamente."""
        spec = ParameterSpec(
            name='pan',
            yaml_path='pan',
            default=0,
            dephase_key='pc_rand_pan'
        )
        
        result = factory._resolve_dephase_prob(spec, {'pc_rand_pan': 100}, range_val=None)
        assert result == 100
# =============================================================================
# 4. TEST _extract_raw_value()
# =============================================================================

class TestExtractRawValue:
    """Test estrazione valori raw (non-Parameter)."""
    
    def test_extracts_string(self, factory):
        """Estrae correttamente una stringa."""
        spec = ParameterSpec(
            name='grain_envelope',
            yaml_path='grain.envelope',
            default='gaussian',
            is_smart=False
        )
        yaml_data = {'grain': {'envelope': 'hanning'}}
        
        result = factory._extract_raw_value(spec, yaml_data)
        assert result == 'hanning'
    
    def test_uses_default_when_missing(self, factory):
        """Usa il default quando il valore manca."""
        spec = ParameterSpec(
            name='grain_envelope',
            yaml_path='grain.envelope',
            default='gaussian',
            is_smart=False
        )
        yaml_data = {'grain': {}}  # envelope mancante
        
        result = factory._extract_raw_value(spec, yaml_data)
        assert result == 'gaussian'
    
    def test_extracts_number(self, factory):
        """Può estrarre anche numeri come raw."""
        spec = ParameterSpec(
            name='some_raw',
            yaml_path='raw_value',
            default=0,
            is_smart=False
        )
        yaml_data = {'raw_value': 42}
        
        result = factory._extract_raw_value(spec, yaml_data)
        assert result == 42
    
    def test_extracts_list(self, factory):
        """Può estrarre liste come raw."""
        spec = ParameterSpec(
            name='list_param',
            yaml_path='my_list',
            default=[],
            is_smart=False
        )
        yaml_data = {'my_list': [1, 2, 3]}
        
        result = factory._extract_raw_value(spec, yaml_data)
        assert result == [1, 2, 3]


# =============================================================================
# 5. TEST _create_smart_parameter()
# =============================================================================

class TestCreateSmartParameter:
    """Test creazione di Parameter objects."""
    
    def test_creates_parameter_object(self, factory):
        """Crea un oggetto Parameter."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            range_path='volume_range',
            dephase_key='pc_rand_volume'
        )
        yaml_data = {'volume': -12.0}
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        assert isinstance(result, Parameter)
    
    def test_uses_yaml_value(self, factory):
        """Usa il valore dal YAML."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0
        )
        yaml_data = {'volume': -12.0}
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        # Verifica che il valore base sia quello del YAML
        assert result._value == -12.0
    
    def test_uses_default_when_missing(self, factory):
        """Usa il default quando manca dal YAML."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0
        )
        yaml_data = {}  # volume mancante
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        assert result._value == -6.0
    
    def test_extracts_range(self, factory):
        """Estrae il range quando specificato."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            range_path='volume_range'
        )
        yaml_data = {'volume': -6.0, 'volume_range': 3.0}
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        assert result._mod_range == 3.0
    
    def test_range_none_when_no_range_path(self, factory):
        """Range è None se range_path non è definito."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            range_path=None  # Nessun range
        )
        yaml_data = {'volume': -6.0, 'volume_range': 3.0}
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        assert result._mod_range is None
    
    def test_extracts_dephase_prob(self, factory):
        """Estrae la probabilità dephase."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            dephase_key='pc_rand_volume'
        )
        yaml_data = {'volume': -6.0}
        dephase = {'pc_rand_volume': 50.0}
        
        result = factory._create_smart_parameter(spec, yaml_data, dephase)
        
        assert result._mod_prob == 50.0
    
    def test_handles_nested_yaml_path(self, factory):
        """Gestisce percorsi YAML nested."""
        spec = ParameterSpec(
            name='grain_duration',
            yaml_path='grain.duration',
            default=0.05,
            range_path='grain.duration_range'
        )
        yaml_data = {
            'grain': {
                'duration': 0.1,
                'duration_range': 0.02
            }
        }
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        assert result._value == 0.1
        assert result._mod_range == 0.02
    
    def test_handles_envelope_value(self, factory):
        """Gestisce envelope come valore."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0
        )
        yaml_data = {'volume': [[0, -12], [10, 0]]}  # Envelope
        
        result = factory._create_smart_parameter(spec, yaml_data, None)
        
        assert isinstance(result._value, Envelope)


# =============================================================================
# 6. TEST create_all_parameters()
# =============================================================================

class TestCreateAllParameters:
    """Test creazione di tutti i parametri."""
    
    def test_returns_dict(self, factory, minimal_yaml):
        """Ritorna un dizionario."""
        result = factory.create_all_parameters(minimal_yaml)
        
        assert isinstance(result, dict)
    
    def test_dict_keys_are_param_names(self, factory, minimal_yaml):
        """Le chiavi sono i nomi dei parametri."""
        result = factory.create_all_parameters(minimal_yaml)
        
        # Almeno questi parametri devono esistere
        assert 'volume' in result
        assert 'pan' in result
        assert 'grain_duration' in result
        assert 'grain_envelope' in result
    
    def test_smart_params_are_parameter_objects(self, factory, minimal_yaml):
        """I parametri smart sono oggetti Parameter."""
        result = factory.create_all_parameters(minimal_yaml)
        
        assert isinstance(result['volume'], Parameter)
        assert isinstance(result['pan'], Parameter)
        assert isinstance(result['grain_duration'], Parameter)
    
    def test_raw_params_are_raw_values(self, factory, minimal_yaml):
        """I parametri raw sono valori diretti."""
        result = factory.create_all_parameters(minimal_yaml)
        
        assert result['grain_envelope'] == 'hanning'
        assert not isinstance(result['grain_envelope'], Parameter)
    
    def test_uses_defaults_for_missing(self, factory):
        """Usa i default per parametri mancanti."""
        yaml_data = {}  # Tutto mancante
        
        result = factory.create_all_parameters(yaml_data)
        
        # Verifica che usi i default dallo schema
        from parameter_schema import get_parameter_spec
        vol_spec = get_parameter_spec('volume')
        
        assert result['volume']._value == vol_spec.default
    
    def test_handles_dephase_block(self, factory, full_yaml):
        """Gestisce correttamente il blocco dephase."""
        result = factory.create_all_parameters(full_yaml)
        
        # Volume ha dephase 50%
        assert result['volume']._mod_prob == 50.0
        # Pan ha dephase 100%
        assert result['pan']._mod_prob == 100.0
    
    def test_handles_range_values(self, factory, full_yaml):
        """Gestisce correttamente i valori range."""
        result = factory.create_all_parameters(full_yaml)
        
        assert result['volume']._mod_range == 3.0
        assert result['pan']._mod_range == 30.0
    
    def test_count_matches_schema(self, factory, minimal_yaml):
        """Il numero di parametri corrisponde allo schema."""
        result = factory.create_all_parameters(minimal_yaml)
        
        assert len(result) == len(STREAM_PARAMETER_SCHEMA)
    
    def test_no_dephase_block_all_none(self, factory, minimal_yaml):
        """Senza blocco dephase, tutte le prob sono None."""
        # minimal_yaml non ha 'dephase'
        result = factory.create_all_parameters(minimal_yaml)
        
        assert result['volume']._mod_prob is None
        assert result['pan']._mod_prob is None


# =============================================================================
# 7. TEST create_single_parameter()
# =============================================================================

class TestCreateSingleParameter:
    """Test creazione di un singolo parametro."""
    
    def test_creates_smart_parameter(self, factory, minimal_yaml):
        """Crea un Parameter per parametri smart."""
        result = factory.create_single_parameter('volume', minimal_yaml)
        
        assert isinstance(result, Parameter)
    
    def test_creates_raw_value(self, factory, minimal_yaml):
        """Ritorna valore raw per parametri non-smart."""
        result = factory.create_single_parameter('grain_envelope', minimal_yaml)
        
        assert result == 'hanning'
        assert not isinstance(result, Parameter)
    
    def test_raises_for_unknown_param(self, factory, minimal_yaml):
        """Solleva KeyError per parametro sconosciuto."""
        with pytest.raises(KeyError):
            factory.create_single_parameter('unknown_param', minimal_yaml)
    
    def test_uses_correct_values(self, factory):
        """Usa i valori corretti dal YAML."""
        yaml_data = {
            'volume': -18.0,
            'volume_range': 6.0,
            'dephase': {'pc_rand_volume': 75.0}
        }
        
        result = factory.create_single_parameter('volume', yaml_data)
        
        assert result._value == -18.0
        assert result._mod_range == 6.0
        assert result._mod_prob == 75.0


# =============================================================================
# 8. TEST INTEGRAZIONE CON ENVELOPE
# =============================================================================

class TestEnvelopeIntegration:
    """Test che envelope vengano gestiti correttamente."""
    
    def test_envelope_as_value(self, factory):
        """Envelope come valore base."""
        yaml_data = {
            'volume': [[0, -12], [5, -6], [10, -12]]
        }
        
        result = factory.create_single_parameter('volume', yaml_data)
        
        assert isinstance(result._value, Envelope)
        # Verifica interpolazione
        assert result._value.evaluate(5) == -6.0
    
    def test_envelope_as_range(self, factory):
        """Envelope come valore range."""
        yaml_data = {
            'volume': -6.0,
            'volume_range': [[0, 0], [10, 6]]  # Range che cresce
        }
        
        result = factory.create_single_parameter('volume', yaml_data)
        
        assert isinstance(result._mod_range, Envelope)
    
    def test_envelope_as_dephase(self, factory):
        """Envelope come probabilità dephase."""
        yaml_data = {
            'volume': -6.0,
            'dephase': {
                'pc_rand_volume': [[0, 0], [10, 100]]  # Prob che cresce
            }
        }
        
        result = factory.create_single_parameter('volume', yaml_data)
        
        assert isinstance(result._mod_prob, Envelope)


# =============================================================================
# 9. TEST TIME_MODE NORMALIZATION
# =============================================================================

class TestTimeModeNormalization:
    """Test normalizzazione temporale degli envelope."""
    
    def test_absolute_mode_no_scaling(self, factory):
        """In mode absolute, i tempi non vengono scalati."""
        yaml_data = {
            'volume': [[0, -12], [5, -6], [10, 0]]  # Tempi assoluti
        }
        
        result = factory.create_single_parameter('volume', yaml_data)
        
        # I breakpoints devono rimanere invariati
        assert result._value.breakpoints[1][0] == 5  # t=5 non scalato
    
    def test_normalized_mode_scales_times(self, factory_normalized):
        """In mode normalized, i tempi vengono scalati per duration."""
        # factory_normalized ha duration=10.0
        yaml_data = {
            'volume': [[0, -12], [0.5, -6], [1.0, 0]]  # Tempi 0-1
        }
        
        result = factory_normalized.create_single_parameter('volume', yaml_data)
        
        # 0.5 * 10.0 = 5.0
        assert result._value.breakpoints[1][0] == 5.0


# =============================================================================
# 10. TEST EDGE CASES E ERRORI
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_empty_yaml(self, factory):
        """YAML vuoto usa tutti i default."""
        result = factory.create_all_parameters({})
        
        # Deve funzionare senza errori
        assert 'volume' in result
        assert 'pan' in result
    
    def test_none_values_in_yaml(self, factory):
        """Valori None nel YAML vengono gestiti."""
        yaml_data = {
            'volume': None,  # Esplicitamente None
            'grain': {'envelope': None}
        }
        
        # Non deve crashare
        result = factory.create_all_parameters(yaml_data)
        
        # Volume None dovrebbe diventare il default o essere gestito
        assert result['volume'] is not None or result['volume']._value is None
    
    def test_extra_yaml_fields_ignored(self, factory, minimal_yaml):
        """Campi YAML extra vengono ignorati."""
        minimal_yaml['unknown_field'] = 'should be ignored'
        minimal_yaml['another_unknown'] = {'nested': 'data'}
        
        # Non deve crashare
        result = factory.create_all_parameters(minimal_yaml)
        
        # I parametri normali funzionano
        assert 'volume' in result
        # I campi extra non creano attributi
        assert 'unknown_field' not in result


# =============================================================================
# 11. TEST OWNER_ID PASSTHROUGH
# =============================================================================

class TestOwnerIdPassthrough:
    """Test che stream_id venga passato ai Parameter."""
    
    def test_parameter_has_correct_owner(self):
        """I Parameter creati hanno il corretto owner_id."""
        factory = ParameterFactory('my_unique_stream', 10.0)
        yaml_data = {'volume': -6.0}
        
        result = factory.create_single_parameter('volume', yaml_data)
        
        assert result.owner_id == 'my_unique_stream'
    
    def test_all_parameters_same_owner(self, minimal_yaml):
        """Tutti i Parameter hanno lo stesso owner_id."""
        factory = ParameterFactory('shared_owner', 10.0)
        result = factory.create_all_parameters(minimal_yaml)
        
        for name, param in result.items():
            if isinstance(param, Parameter):
                assert param.owner_id == 'shared_owner'