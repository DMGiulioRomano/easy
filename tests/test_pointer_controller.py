"""
tests/test_pointer_controller.py

Test suite aggiornata per il refactoring Fase 2 (ParameterFactory + Unified Deviation).
"""

import pytest
from unittest.mock import MagicMock, patch
from pointer_controller import PointerController
from envelope import Envelope
from parameter import Parameter

# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def base_params():
    """Parametri base minimi."""
    return {
        'start': 0.0,
        'speed': 1.0,
        'offset_range': 0.0 # ex jitter/offset
    }

@pytest.fixture
def controller(base_params):
    """Istanza base del controller."""
    return PointerController(
        params=base_params,
        stream_id="test_stream",
        duration=10.0,
        sample_dur_sec=5.0, # Sample lungo 5 secondi
        time_mode='absolute'
    )

# =============================================================================
# 1. TEST INIZIALIZZAZIONE & FACTORY
# =============================================================================

def test_initialization_creates_smart_parameters(controller):
    """Verifica che i parametri vengano creati come oggetti Parameter."""
    assert hasattr(controller, 'speed')
    assert isinstance(controller.speed, Parameter)
    assert controller.speed.value == 1.0
    
    assert hasattr(controller, 'deviation') # Mappato da 'offset_range' nello schema
    assert isinstance(controller.deviation, Parameter)
    assert controller.deviation.value == 0.0

def test_loop_params_initialization():
    """Verifica inizializzazione parametri loop."""
    params = {
        'start': 0.0,
        'loop_start': 1.0,
        'loop_end': 2.0
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    assert pc.has_loop is True
    assert pc.loop_start == 1.0
    assert pc.loop_end == 2.0
    assert pc.loop_dur is None

def test_loop_dur_smart_parameter():
    """Verifica che loop_dur diventi uno Smart Parameter."""
    params = {
        'start': 0.0,
        'loop_start': 1.0,
        'loop_dur': 0.5
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    assert pc.loop_end is None
    assert isinstance(pc.loop_dur, Parameter)
    assert pc.loop_dur.value == 0.5

# =============================================================================
# 2. TEST MOVIMENTO LINEARE
# =============================================================================

def test_linear_movement_constant_speed(controller):
    """Test movimento a velocità costante 1.0."""
    # t=0 -> pos=0
    assert controller.calculate(0.0) == 0.0
    # t=1 -> pos=1
    assert controller.calculate(1.0) == 1.0
    # t=2.5 -> pos=2.5
    assert controller.calculate(2.5) == 2.5

def test_linear_movement_speed_2(base_params):
    """Test movimento a velocità 2.0."""
    base_params['speed'] = 2.0
    pc = PointerController(base_params, "t", 10.0, 5.0)
    
    assert pc.calculate(1.0) == 2.0

def test_linear_movement_envelope_integration():
    """
    CRUCIALE: Test integrazione analitica quando speed è un Envelope.
    Envelope speed: 0.0 -> 2.0 in 2 secondi. (Accelerazione lineare)
    Posizione = Integrale(at) = 0.5 * a * t^2
    a (pendenza) = 1.0
    t=2 => 0.5 * 1 * 4 = 2.0
    """
    params = {
        'start': 0.0,
        'speed': [[0, 0], [2, 2]], # Rampa 0->2
        'offset_range': 0.0
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    # Verifica che speed sia un envelope
    assert isinstance(pc.speed.value, Envelope)
    
    # Calcolo a t=2
    pos = pc.calculate(2.0)
    
    # Tolleranza floating point
    assert abs(pos - 2.0) < 0.0001

# =============================================================================
# 3. TEST LOOP LOGIC
# =============================================================================

def test_loop_static_bounds():
    """Test loop semplice con start/end fissi."""
    params = {
        'start': 0.0,
        'speed': 1.0,
        'loop_start': 1.0,
        'loop_end': 3.0, # Loop length = 2.0
        'offset_range': 0.0
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    # t=0.5 -> pos=0.5 (Fuori loop, comportamento pre-loop)
    # Nota: L'implementazione attuale wrappa sul buffer se non è entrato nel loop.
    # Se start=0, loop_start=1.
    assert pc.calculate(0.5) == 0.5
    
    # t=1.5 -> Entra nel loop? 
    # Linear pos = 1.5. È tra 1.0 e 3.0.
    # Deve essere 1.5.
    assert pc.calculate(1.5) == 1.5
    
    # t=3.5 -> Linear pos 3.5.
    # Ha superato loop_end (3.0).
    # Deve wrappare: 3.5 - 1.0 (start) = 2.5. 2.5 % 2.0 (len) = 0.5. 
    # Posizione assoluta = 1.0 (start) + 0.5 = 1.5
    assert pc.calculate(3.5) == 1.5

def test_loop_dynamic_duration():
    """Test loop con durata variabile (Parameter)."""
    params = {
        'start': 0.0,
        'speed': 1.0,
        'loop_start': 1.0,
        'loop_dur': 1.0, # Loop [1.0, 2.0]
        'offset_range': 0.0
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    # 1. PRIMING: Entriamo nel loop a t=1.5 (Pos=1.5)
    # Questo setta pc._in_loop = True
    pc.calculate(1.5) 
    
    # 2. TEST: Ora saltiamo a t=2.5
    # Linear=2.5. Wrap: (2.5-1.0)%1.0 = 0.5. Pos=1.5
    assert pc.calculate(2.5) == 1.5
# =============================================================================
# 4. TEST DEVIATION (Unified Jitter)
# =============================================================================

def test_deviation_application():
    """
    Verifica che offset_range venga applicato.
    Usiamo un seed fisso o mockiamo random per determinismo.
    """
    params = {
        'start': 0.0,
        'speed': 0.0, # Fermo
        'offset_range': 0.1 # 10% di 5s = 0.5s range totale
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    with patch('random.uniform', return_value=0.5): 
        # Mock random.uniform per ritornare il massimo positivo
        # Deviation calculation:
        # dev_normalized = 0 (base) + 0.5 * 0.1 (range) = 0.05
        # context_length = 5.0 (sample duration)
        # deviation_seconds = 0.05 * 5.0 = 0.25
        # final = 0.0 + 0.25 = 0.25
        
        pos = pc.calculate(1.0)
        assert abs(pos - 0.25) < 0.0001

def test_implicit_jitter_is_applied():
    """
    Verifica che anche senza offset_range, venga applicato 
    il default jitter (definito in parameter_definitions).
    """
    params = {
        'start': 0.0,
        'speed': 0.0,
        # offset_range MANCANTE -> Attiva Jitter Implicito
    }
    pc = PointerController(params, "t", 10.0, 5.0)
    
    # Verifichiamo che il parametro abbia un range interno (default jitter)
    # default_jitter per pointer_deviation è 0.005 (0.5%)
    # 0.5% di 5s = 0.025s
    
    with patch('random.uniform', return_value=0.5):
        # dev_norm = 0 + 0.5 * 0.005 = 0.0025
        # dev_sec = 0.0025 * 5.0 = 0.0125
        pos = pc.calculate(1.0)
        
        # Ci aspettiamo un valore diverso da 0
        assert pos > 0.0
        assert abs(pos - 0.0125) < 0.0001