# tests/test_pointer_controller.py
"""
Test per PointerController

Verifica:
- Inizializzazione parametri
- Movimento lineare (costante e envelope)
- Loop con phase accumulator
- Deviazioni stocastiche

Fixtures utilizzate (da conftest.py):
- evaluator: ParameterEvaluator standard
- sample_dur_sec: 10.0 secondi
- pointer_factory: factory per creare PointerController custom
- pointer_basic: start=0, speed=1, no loop
- pointer_with_loop: loop fisso 2.0-4.0
- env_linear: Envelope [0,0] → [10,100]
"""

import pytest
import random
from pointer_controller import PointerController
from envelope import Envelope


# =============================================================================
# 1. TEST INIZIALIZZAZIONE
# =============================================================================

class TestPointerControllerInit:
    """Test inizializzazione parametri."""
    
    def test_default_values(self, pointer_factory):
        """Verifica valori default quando params è vuoto."""
        pointer = pointer_factory({})
        
        assert pointer.start == 0.0
        assert pointer.speed == 1.0
        assert pointer.jitter == 0.0
        assert pointer.offset_range == 0.0
        assert pointer.has_loop is False
    
    def test_basic_params(self, pointer_factory):
        """Verifica parsing parametri base."""
        pointer = pointer_factory({
            'start': 1.5,
            'speed': 2.0,
            'jitter': 0.01,
            'offset_range': 0.2
        })
        
        assert pointer.start == 1.5
        assert pointer.speed == 2.0
        assert pointer.jitter == 0.01
        assert pointer.offset_range == 0.2
    
    def test_speed_envelope(self, pointer_factory):
        """Verifica che speed envelope venga parsato correttamente."""
        pointer = pointer_factory({
            'speed': [[0, 1.0], [5, 2.0]]
        })
        
        assert isinstance(pointer.speed, Envelope)


# =============================================================================
# 2. TEST CONFIGURAZIONE LOOP
# =============================================================================

class TestLoopConfiguration:
    """Test configurazione loop."""
    
    def test_no_loop(self, pointer_basic):
        """Nessun loop se loop_start non è definito."""
        assert pointer_basic.has_loop is False
        assert pointer_basic.loop_start is None
    
    def test_loop_with_end(self, pointer_with_loop):
        """Loop con loop_start e loop_end fissi."""
        assert pointer_with_loop.has_loop is True
        assert pointer_with_loop.loop_start == 2.0
        assert pointer_with_loop.loop_end == 4.0
        assert pointer_with_loop.loop_dur is None
    
    def test_loop_with_dur(self, pointer_factory):
        """Loop con loop_start e loop_dur."""
        pointer = pointer_factory({
            'loop_start': 1.0,
            'loop_dur': 2.0
        })
        
        assert pointer.has_loop is True
        assert pointer.loop_start == 1.0
        assert pointer.loop_end is None
        assert pointer.loop_dur == 2.0
    
    def test_loop_start_only(self, pointer_factory, sample_dur_sec):
        """Solo loop_start → loop fino a fine sample."""
        pointer = pointer_factory({'loop_start': 2.0})
        
        assert pointer.has_loop is True
        assert pointer.loop_start == 2.0
        assert pointer.loop_end == sample_dur_sec  # Fine sample
    
    def test_loop_dur_envelope(self, pointer_factory):
        """Loop con loop_dur come Envelope."""
        pointer = pointer_factory({
            'loop_start': 0.0,
            'loop_dur': [[0, 1.0], [5, 0.5]]
        })
        
        assert pointer.has_loop is True
        assert isinstance(pointer.loop_dur, Envelope)
    
    def test_loop_normalized(self, pointer_factory):
        """Loop con valori normalizzati (sample_dur=10.0)."""
        pointer = pointer_factory({
            'loop_unit': 'normalized',
            'loop_start': 0.2,  # 20% di 10.0 = 2.0
            'loop_end': 0.6     # 60% di 10.0 = 6.0
        })
        
        assert pointer.loop_start == pytest.approx(2.0)
        assert pointer.loop_end == pytest.approx(6.0)


# =============================================================================
# 3. TEST MOVIMENTO LINEARE (senza loop)
# =============================================================================

class TestLinearMovement:
    """Test movimento lineare senza loop."""
    
    def test_constant_speed(self, pointer_basic):
        """Movimento con velocità costante (speed=1)."""
        # Senza jitter/offset, posizione = tempo
        assert pointer_basic.calculate(0.0) == pytest.approx(0.0)
        assert pointer_basic.calculate(1.0) == pytest.approx(1.0)
        assert pointer_basic.calculate(5.0) == pytest.approx(5.0)
    
    def test_double_speed(self, pointer_factory):
        """Movimento con velocità doppia."""
        pointer = pointer_factory(
            {'start': 0.0, 'speed': 2.0},
            sample_dur=20.0
        )
        
        assert pointer.calculate(1.0) == pytest.approx(2.0)
        assert pointer.calculate(5.0) == pytest.approx(10.0)
    
    def test_with_start_offset(self, pointer_factory):
        """Movimento con posizione iniziale."""
        pointer = pointer_factory({'start': 2.0, 'speed': 1.0})
        
        assert pointer.calculate(0.0) == pytest.approx(2.0)
        assert pointer.calculate(1.0) == pytest.approx(3.0)
    
    def test_wrap_at_sample_end(self, pointer_factory):
        """Verifica wrap quando supera la durata del sample."""
        pointer = pointer_factory(
            {'start': 0.0, 'speed': 1.0},
            sample_dur=5.0
        )
        
        # A t=7, posizione lineare = 7, wrap a 5.0 → 2.0
        assert pointer.calculate(7.0) == pytest.approx(2.0)
    
    def test_speed_envelope_integration(self, pointer_factory):
        """Movimento con speed envelope (richiede integrazione)."""
        pointer = pointer_factory(
            {'start': 0.0, 'speed': [[0, 1.0], [5, 2.0]]},
            sample_dur=20.0
        )
        
        # L'integrazione di una rampa 1→2 su 5 secondi
        # Area trapezio = (1+2)/2 * 5 = 7.5
        pos_5 = pointer.calculate(5.0)
        assert 5.0 < pos_5 < 10.0  # Più di lineare (5), meno di doppio (10)


# =============================================================================
# 4. TEST LOOP CON PHASE ACCUMULATOR
# =============================================================================

class TestLoopPhaseAccumulator:
    """Test loop con phase accumulator."""
    
    def test_enters_loop(self, pointer_with_loop):
        """Verifica entrata nel loop (2.0 - 4.0)."""
        # Prima del loop
        assert pointer_with_loop.in_loop is False
        
        # Calcola a t=1 (prima del loop)
        pointer_with_loop.calculate(1.0)
        assert pointer_with_loop.in_loop is False
        
        # Calcola a t=2.5 (dentro il loop)
        pointer_with_loop.calculate(2.5)
        assert pointer_with_loop.in_loop is True
    
    def test_loop_wrapping(self, pointer_with_loop):
        """Verifica che il loop faccia wrap correttamente."""
        # Forza entrata nel loop
        pointer_with_loop.calculate(2.5)  # Entra nel loop
        
        # Dopo altri 2 secondi, dovrebbe aver fatto un giro completo
        pos = pointer_with_loop.calculate(4.5)
        
        # Dovrebbe essere tra 2.0 e 4.0 (nel loop)
        assert 2.0 <= pos < 4.0
    
    def test_loop_phase_property(self, pointer_with_loop):
        """Verifica che loop_phase sia accessibile e corretto."""
        # Prima del loop
        assert pointer_with_loop.loop_phase == 0.0
        
        # Entra a metà loop (t=3.0, loop 2.0-4.0, fase ~0.5)
        pointer_with_loop.calculate(3.0)
        
        assert 0.4 <= pointer_with_loop.loop_phase <= 0.6


# =============================================================================
# 5. TEST DEVIAZIONI STOCASTICHE
# =============================================================================

class TestStochasticDeviations:
    """Test deviazioni stocastiche."""
    
    def test_jitter_applied(self, pointer_factory):
        """Verifica che jitter venga applicato."""
        pointer = pointer_factory({
            'start': 5.0,
            'speed': 0.0,  # Fermo
            'jitter': 0.1  # ±0.1 secondi
        })
        
        # Raccogli molte posizioni
        random.seed(None)  # Random reale
        positions = [pointer.calculate(0.0) for _ in range(100)]
        
        # Dovrebbero variare attorno a 5.0 ma entro ±0.1
        assert min(positions) < 5.0
        assert max(positions) > 5.0
        assert all(4.9 <= p <= 5.1 for p in positions)
    
    def test_offset_range_applied(self, pointer_factory):
        """Verifica che offset_range venga applicato."""
        pointer = pointer_factory({
            'start': 5.0,
            'speed': 0.0,
            'jitter': 0.0,
            'offset_range': 0.5  # ±25% del context (sample_dur=10)
        })
        
        # offset_deviation = ±0.5 * 0.5 * 10 = ±2.5
        random.seed(None)
        positions = [pointer.calculate(0.0) for _ in range(100)]
        
        # Dovrebbero variare significativamente
        assert max(positions) - min(positions) > 1.0
    
    def test_jitter_with_mock(self, pointer_factory, monkeypatch):
        """Test deterministico di jitter con mock random."""
        monkeypatch.setattr(random, "uniform", lambda a, b: 0.5 * (a + b))
        
        pointer = pointer_factory({
            'start': 5.0,
            'speed': 0.0,
            'jitter': 0.2  # Mock restituirà 0 (media di -0.2 e 0.2)
        })
        
        pos = pointer.calculate(0.0)
        assert pos == pytest.approx(5.0)  # Deviazione = 0


# =============================================================================
# 6. TEST RESET
# =============================================================================

class TestReset:
    """Test reset dello stato."""
    
    def test_reset_loop_state(self, pointer_with_loop):
        """Verifica che reset pulisca lo stato del loop."""
        # Entra nel loop
        pointer_with_loop.calculate(3.0)
        assert pointer_with_loop.in_loop is True
        
        # Reset
        pointer_with_loop.reset()
        
        assert pointer_with_loop.in_loop is False
        assert pointer_with_loop.loop_phase == 0.0


# =============================================================================
# 7. TEST REPR
# =============================================================================

class TestRepr:
    """Test rappresentazione stringa."""
    
    def test_repr_without_loop(self, pointer_factory):
        """Repr senza loop."""
        pointer = pointer_factory({'start': 1.0, 'speed': 2.0})
        
        repr_str = repr(pointer)
        assert "start=1.0" in repr_str
        assert "speed=2.0" in repr_str
        assert "loop" not in repr_str
    
    def test_repr_with_loop(self, pointer_with_loop):
        """Repr con loop."""
        repr_str = repr(pointer_with_loop)
        assert "loop=" in repr_str


# =============================================================================
# 8. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_negative_speed(self, pointer_factory):
        """Speed negativo (lettura al contrario)."""
        pointer = pointer_factory({
            'start': 5.0,
            'speed': -1.0
        })
        
        # A t=2, posizione = 5 + (-1 * 2) = 3
        pos = pointer.calculate(2.0)
        assert pos == pytest.approx(3.0)
    
    def test_zero_speed(self, pointer_factory):
        """Speed zero (fermo in posizione)."""
        pointer = pointer_factory({
            'start': 3.0,
            'speed': 0.0
        })
        
        # Rimane sempre a 3.0
        assert pointer.calculate(0.0) == pytest.approx(3.0)
        assert pointer.calculate(10.0) == pytest.approx(3.0)
    
    def test_very_short_loop(self, pointer_factory):
        """Loop molto corto (test stabilità numerica)."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed': 1.0,
            'loop_start': 1.0,
            'loop_dur': 0.01  # 10ms
        })
        
        # Non deve crashare
        pos = pointer.calculate(5.0)
        
        # Deve rimanere nel range del loop
        assert 1.0 <= pos < 1.01