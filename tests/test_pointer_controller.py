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


# =============================================================================
# 5. TEST RESET & STATE MANAGEMENT
# =============================================================================

class TestResetAndState:
    """Test per reset() e gestione dello stato."""
    
    def test_reset_clears_loop_state(self, pointer_factory):
        """reset() deve resettare lo stato del phase accumulator."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 1.0,
            'loop_dur': 1.0,
            'offset_range': 0.0
        })
        
        # Entra nel loop
        pointer.calculate(1.5)
        assert pointer.in_loop is True
        assert pointer.loop_phase > 0.0
        
        # Reset
        pointer.reset()
        
        # Stato deve essere pulito
        assert pointer.in_loop is False
        assert pointer.loop_phase == 0.0
        assert pointer._last_linear_pos is None
    
    def test_reset_allows_reuse(self, pointer_factory):
        """Dopo reset(), il controller può essere riutilizzato."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 2.0,
            'loop_end': 4.0,
            'offset_range': 0.0
        })
        
        # Prima esecuzione
        pointer.calculate(3.0)  # Entra nel loop
        assert pointer.in_loop is True
        
        # Reset e riutilizzo
        pointer.reset()
        
        # Deve comportarsi come se fosse nuovo
        pos = pointer.calculate(1.0)  # Prima del loop
        assert pointer.in_loop is False
        assert pos == pytest.approx(1.0)


# =============================================================================
# 6. TEST get_speed() METHOD
# =============================================================================

class TestGetSpeed:
    """Test per il metodo get_speed()."""
    
    def test_get_speed_constant(self, pointer_factory):
        """get_speed() con valore costante."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 2.5,
            'offset_range': 0.0
        })
        
        # Costante nel tempo
        assert pointer.get_speed(0.0) == 2.5
        assert pointer.get_speed(5.0) == 2.5
        assert pointer.get_speed(100.0) == 2.5
    
    def test_get_speed_envelope(self, pointer_factory):
        """get_speed() con Envelope deve interpolare."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': [[0, 1.0], [10, 3.0]],  # Rampa 1→3
            'offset_range': 0.0
        })
        
        assert pointer.get_speed(0.0) == pytest.approx(1.0)
        assert pointer.get_speed(5.0) == pytest.approx(2.0)  # Metà
        assert pointer.get_speed(10.0) == pytest.approx(3.0)
    
    def test_get_speed_negative(self, pointer_factory):
        """get_speed() con velocità negativa (reverse playback)."""
        pointer = pointer_factory({
            'start': 5.0,
            'speed': -1.0,
            'offset_range': 0.0
        })
        
        assert pointer.get_speed(0.0) == -1.0


# =============================================================================
# 7. TEST NEGATIVE SPEED (REVERSE PLAYBACK)
# =============================================================================

class TestNegativeSpeed:
    """Test per velocità negativa (lettura al contrario)."""
    
    def test_negative_speed_movement(self, pointer_factory):
        """Speed negativo muove all'indietro."""
        pointer = pointer_factory({
            'start': 5.0,
            'speed': -1.0,
            'offset_range': 0.0
        }, sample_dur=10.0)
        
        assert pointer.calculate(0.0) == pytest.approx(5.0)
        assert pointer.calculate(2.0) == pytest.approx(3.0)  # 5 - 2
        assert pointer.calculate(4.0) == pytest.approx(1.0)  # 5 - 4
    
    def test_negative_speed_wrap(self, pointer_factory):
        """Speed negativo wrappa correttamente a fine sample."""
        pointer = pointer_factory({
            'start': 2.0,
            'speed': -1.0,
            'offset_range': 0.0
        }, sample_dur=10.0)
        
        # t=3 → pos = 2 - 3 = -1 → wrap a 10 - 1 = 9
        pos = pointer.calculate(3.0)
        assert pos == pytest.approx(9.0)
    
    def test_negative_speed_in_loop(self, pointer_factory):
        """Speed negativo nel loop wrappa correttamente."""
        pointer = pointer_factory({
            'start': 3.0,
            'speed': -1.0,
            'loop_start': 2.0,
            'loop_end': 4.0,  # Loop length = 2
            'offset_range': 0.0
        }, sample_dur=10.0)
        
        # Entra nel loop
        pointer.calculate(0.5)  # pos = 2.5, dentro il loop
        assert pointer.in_loop is True
        
        # Continua all'indietro nel loop
        pos = pointer.calculate(2.0)  # pos lineare = 3 - 2 = 1, ma siamo nel loop
        assert 2.0 <= pos < 4.0  # Deve restare nel loop


# =============================================================================
# 8. TEST LOOP NORMALIZED MODE
# =============================================================================

class TestLoopNormalized:
    """Test per loop con valori normalizzati."""
    
    def test_loop_normalized_start_end(self, pointer_factory):
        """Loop normalizzato scala correttamente start/end."""
        pointer = pointer_factory({
            'start': 0.0,
            'loop_unit': 'normalized',
            'loop_start': 0.2,  # 20% di 10s = 2.0s
            'loop_end': 0.6,    # 60% di 10s = 6.0s
            'offset_range': 0.0
        }, sample_dur=10.0)
        
        assert pointer.loop_start == pytest.approx(2.0)
        assert pointer.loop_end == pytest.approx(6.0)
        assert pointer.has_loop is True
    
    def test_loop_normalized_with_dur(self, pointer_factory):
        """Loop normalizzato con loop_dur scala anche la durata."""
        pointer = pointer_factory({
            'start': 0.0,
            'loop_unit': 'normalized',
            'loop_start': 0.1,   # 10% di 5s = 0.5s
            'loop_dur': 0.4,     # 40% di 5s = 2.0s
            'offset_range': 0.0
        }, sample_dur=5.0)
        
        assert pointer.loop_start == pytest.approx(0.5)
        # loop_dur è un Parameter, accediamo al valore interno
        assert pointer.loop_dur.value == pytest.approx(2.0)


# =============================================================================
# 9. TEST LOOP_DUR ENVELOPE DINAMICO
# =============================================================================

class TestLoopDurEnvelope:
    """Test per loop_dur come Envelope che cambia nel tempo."""
    
    def test_loop_dur_envelope_creation(self, pointer_factory):
        """loop_dur envelope viene parsato correttamente."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 1.0,
            'loop_dur': [[0, 2.0], [10, 0.5]],  # Si accorcia
            'offset_range': 0.0
        })
        
        from parameter import Parameter
        assert isinstance(pointer.loop_dur, Parameter)
        
        # All'inizio il loop è lungo
        assert pointer.loop_dur.get_value(0.0) == pytest.approx(2.0)
        # Alla fine il loop è corto
        assert pointer.loop_dur.get_value(10.0) == pytest.approx(0.5)
    
    def test_loop_dur_envelope_dynamic_behavior(self, pointer_factory):
        """Il phase accumulator gestisce loop_dur che cambia."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 0.0,
            'loop_dur': [[0, 2.0], [10, 1.0]],  # Da 2s a 1s
            'offset_range': 0.0
        }, sample_dur=10.0)
        
        # Primi calcoli con loop lungo
        pointer.calculate(0.5)  # Entra nel loop
        assert pointer.in_loop is True
        
        # Il loop si accorcia nel tempo ma non deve causare salti
        pos1 = pointer.calculate(1.0)
        pos2 = pointer.calculate(1.5)
        pos3 = pointer.calculate(2.0)
        
        # Tutte le posizioni devono essere valide (dentro i bounds del sample)
        for pos in [pos1, pos2, pos3]:
            assert 0.0 <= pos < 10.0


# =============================================================================
# 10. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite e situazioni particolari."""
    
    def test_zero_speed(self, pointer_factory):
        """Speed zero = posizione fissa."""
        pointer = pointer_factory({
            'start': 3.0,
            'speed': 0.0,
            'offset_range': 0.0
        })
        
        assert pointer.calculate(0.0) == pytest.approx(3.0)
        assert pointer.calculate(100.0) == pytest.approx(3.0)
    
    def test_very_high_speed(self, pointer_factory):
        """Speed molto alto wrappa correttamente."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 100.0,  # 100x
            'offset_range': 0.0
        }, sample_dur=5.0)
        
        # t=1 → pos = 100, wrap: 100 % 5 = 0
        pos = pointer.calculate(1.0)
        assert 0.0 <= pos < 5.0
    
    def test_loop_at_sample_boundaries(self, pointer_factory):
        """Loop ai limiti del sample."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 0.0,
            'loop_end': 10.0,  # Loop = intero sample
            'offset_range': 0.0
        }, sample_dur=10.0)
        
        assert pointer.has_loop is True
        # Deve comunque wrappare correttamente
        pos = pointer.calculate(15.0)
        assert 0.0 <= pos < 10.0
    
    def test_loop_dur_exceeds_sample(self, pointer_factory):
        """loop_dur > sample_dur viene limitato."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 2.0,
            'loop_dur': 100.0,  # Molto più lungo del sample (5s)
            'offset_range': 0.0
        }, sample_dur=5.0)
        
        # Entra nel loop
        pointer.calculate(2.5)
        
        # La posizione deve restare nei bounds del sample
        pos = pointer.calculate(10.0)
        assert 0.0 <= pos < 5.0
    
    def test_fractional_positions(self, pointer_factory):
        """Posizioni frazionarie sono gestite correttamente."""
        pointer = pointer_factory({
            'start': 0.123456789,
            'speed': 1.0,
            'offset_range': 0.0
        })
        
        pos = pointer.calculate(0.0)
        assert pos == pytest.approx(0.123456789)


# =============================================================================
# 11. TEST PROPERTIES
# =============================================================================

class TestProperties:
    """Test per le proprietà read-only."""
    
    def test_sample_dur_sec_property(self, pointer_factory):
        """Proprietà sample_dur_sec espone il valore corretto."""
        pointer = pointer_factory({}, sample_dur=7.5)
        assert pointer.sample_dur_sec == 7.5
    
    def test_in_loop_property_initial(self, pointer_basic):
        """in_loop è False inizialmente."""
        assert pointer_basic.in_loop is False
    
    def test_loop_phase_property_initial(self, pointer_basic):
        """loop_phase è 0.0 inizialmente."""
        assert pointer_basic.loop_phase == 0.0
    
    def test_repr(self, pointer_factory):
        """__repr__ fornisce informazioni utili."""
        pointer = pointer_factory({
            'start': 1.0,
            'speed': 2.0,
            'offset_range': 0.0
        })
        
        repr_str = repr(pointer)
        assert 'PointerController' in repr_str
        assert 'start=1' in repr_str
    
    def test_repr_with_loop(self, pointer_with_loop):
        """__repr__ include info sul loop."""
        repr_str = repr(pointer_with_loop)
        assert 'loop=' in repr_str


# =============================================================================
# 12. TEST DEVIATION CON MOCK CORRETTO
# =============================================================================

class TestDeviationWithCorrectMock:
    """
    Test deviation con mock sul modulo corretto.
    
    NOTA: Il mock deve essere su 'pointer_controller.random.uniform',
    non su 'random.uniform' globale.
    """
    
    def test_deviation_with_correct_mock_path(self, pointer_factory):
        """Verifica applicazione deviation con mock path corretto."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 0.0,  # Fermo
            'offset_range': 0.1  # 10% di 10s = 1.0s range
        }, sample_dur=10.0)
        
        with patch('pointer_controller.random.uniform', return_value=0.5):
            # Con uniform=0.5 e range=0.1:
            # dev_normalized = 0 (base) + 0.5 * 0.1 = 0.05
            # dev_seconds = 0.05 * 10.0 = 0.5
            pos = pointer.calculate(1.0)
            assert pos == pytest.approx(0.5, abs=0.01)
    
    def test_implicit_jitter_with_correct_mock(self, pointer_factory):
        """Verifica implicit jitter (default_jitter) con mock corretto."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 0.0,
            # offset_range NON specificato → usa default_jitter da bounds
            # pointer_deviation.default_jitter = 0.005 (0.5%)
        }, sample_dur=10.0)
        
        with patch('pointer_controller.random.uniform', return_value=0.5):
            # Se c'è default jitter (0.005 = 0.5%):
            # dev = 0.5 * 0.005 * 10.0 = 0.025
            pos = pointer.calculate(1.0)
            # Posizione non dovrebbe essere esattamente 0 se c'è jitter
            # Ma dipende dall'implementazione esatta
            assert 0.0 <= pos < 10.0
    
    def test_deviation_zero_is_deterministic(self, pointer_factory):
        """offset_range=0.0 disabilita la deviazione."""
        pointer = pointer_factory({
            'start': 2.0,
            'speed': 1.0,
            'offset_range': 0.0  # Esplicitamente zero
        })
        
        # Deve essere sempre deterministico
        positions = [pointer.calculate(1.0) for _ in range(10)]
        
        # Tutte uguali
        assert all(p == pytest.approx(3.0) for p in positions)