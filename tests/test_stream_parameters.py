import pytest
from unittest.mock import MagicMock
from parameter import Parameter
from envelope import Envelope
from stream import Stream  
from parameter_factory import ParameterFactory

# =============================================================================
# FIXTURES E SETUP
# =============================================================================

class StreamStub:
    """
    Simulacro di Stream per testare solo l'inizializzazione parametri.
    """
    def __init__(self, stream_id="test_stream", duration=10.0, time_mode="absolute"):
        self.stream_id = stream_id
        self.duration = duration
        self.time_mode = time_mode
    
    def _init_stream_parameters(self, params: dict) -> None:
        """Il metodo sotto test, copiato da Stream"""
        factory = ParameterFactory(
            stream_id=self.stream_id,
            duration=self.duration,
            time_mode=self.time_mode
        )
        parameters = factory.create_all_parameters(params)
        for name, param in parameters.items():
            setattr(self, name, param)

@pytest.fixture
def stream_stub():
    return StreamStub()

# =============================================================================
# TEST CASES
# =============================================================================

def test_basic_parameter_creation(stream_stub):
    """
    Verifica che parametri semplici vengano caricati correttamente.
    Usa ._value per evitare il jitter stocastico.
    """
    params = {
        'volume': -12.0,
        'pan': 45.0
    }
    
    stream_stub._init_stream_parameters(params)
    
    # Verifica esistenza e tipo
    assert isinstance(stream_stub.volume, Parameter)
    assert isinstance(stream_stub.pan, Parameter)
    
    # Verifica valore caricato (stato interno)
    assert stream_stub.volume._value == -12.0
    assert stream_stub.pan._value == 45.0

def test_default_values(stream_stub):
    """Verifica caricamento default schema."""
    params = {} 
    stream_stub._init_stream_parameters(params)
    
    assert hasattr(stream_stub, 'volume')
    assert isinstance(stream_stub.volume, Parameter)
    # Verifica che non sia None (il valore esatto dipende dallo schema)
    assert stream_stub.volume._value is not None

def test_nested_keys_mapping(stream_stub):
    """Verifica mapping chiavi annidate (grain.duration -> grain_duration)."""
    params = {
        'grain': {
            'duration': 0.25
        }
    }
    
    stream_stub._init_stream_parameters(params)
    
    assert hasattr(stream_stub, 'grain_duration')
    assert isinstance(stream_stub.grain_duration, Parameter)
    # Controllo diretto sul valore caricato
    assert stream_stub.grain_duration._value == 0.25

def test_smart_parameter_assembly_range(stream_stub):
    """
    Verifica che 'range' finisca DENTRO l'oggetto Parameter.
    """
    params = {
        'volume': -6.0,
        'volume_range': 3.0
    }
    
    stream_stub._init_stream_parameters(params)
    
    # Il parametro deve contenere il range internamente
    assert stream_stub.volume._mod_range == 3.0
    
    # E non deve esistere come attributo separato (opzionale, dipende dalla pulizia)
    # assert not hasattr(stream_stub, 'volume_range')

def test_smart_parameter_assembly_dephase(stream_stub):
    """Verifica iniezione probabilità dephase."""
    params = {
        'pan': 0.0,
        'dephase': {
            'pc_rand_pan': 50
        }
    }
    
    stream_stub._init_stream_parameters(params)
    assert stream_stub.pan._mod_prob == 50

def test_raw_values_initialization(stream_stub):
    """Verifica parametri raw (non-Parameter)."""
    params = {
        'grain': {
            'envelope': 'hanning'
        }
    }
    
    stream_stub._init_stream_parameters(params)
    assert stream_stub.grain_envelope == 'hanning'

def test_envelope_parsing(stream_stub):
    """Verifica creazione Envelope."""
    params = {
        'volume': [[0, -60], [10, 0]]
    }
    
    stream_stub._init_stream_parameters(params)
    assert isinstance(stream_stub.volume._value, Envelope)