# tests/test_pitch_controller.py
"""
Test per PitchController

Verifica:
- Conversione semitones_to_ratio (metodo statico)
- Inizializzazione parametri (modalità ratio vs semitoni)
- Calcolo pitch in entrambe le modalità
- Range stocastico

Fixtures utilizzate (da conftest.py):
- evaluator: ParameterEvaluator standard
- pitch_factory: factory per creare PitchController custom
- pitch_ratio_default: ratio=1.0 (default)
- pitch_ratio_double: ratio=2.0
- pitch_semitones_fifth: shift_semitones=7
- pitch_semitones_envelope: shift_semitones envelope 0→12
- pitch_with_range: ratio mode con range
- pitch_semitones_with_range: semitones mode con range
- env_linear: Envelope [0,0] → [10,100]
"""

import pytest
import random
import math
from pitch_controller import PitchController
from envelope import Envelope


# =============================================================================
# 1. TEST CONVERSIONE STATICA semitones_to_ratio
# =============================================================================

class TestSemitonesToRatio:
    """Test del metodo statico di conversione."""
    
    def test_zero_semitones_is_unity(self):
        """0 semitoni = ratio 1.0 (nessuna trasposizione)."""
        assert PitchController.semitones_to_ratio(0) == 1.0
    
    def test_octave_up(self):
        """12 semitoni = ratio 2.0 (ottava sopra)."""
        assert PitchController.semitones_to_ratio(12) == pytest.approx(2.0)
    
    def test_octave_down(self):
        """-12 semitoni = ratio 0.5 (ottava sotto)."""
        assert PitchController.semitones_to_ratio(-12) == pytest.approx(0.5)
    
    def test_fifth(self):
        """7 semitoni = quinta giusta ≈ 1.498."""
        expected = pow(2.0, 7/12)  # ≈ 1.4983...
        assert PitchController.semitones_to_ratio(7) == pytest.approx(expected)
    
    def test_minor_third(self):
        """3 semitoni = terza minore ≈ 1.189."""
        expected = pow(2.0, 3/12)
        assert PitchController.semitones_to_ratio(3) == pytest.approx(expected)
    
    def test_two_octaves(self):
        """24 semitoni = ratio 4.0 (due ottave)."""
        assert PitchController.semitones_to_ratio(24) == pytest.approx(4.0)
    
    def test_negative_two_octaves(self):
        """-24 semitoni = ratio 0.25 (due ottave sotto)."""
        assert PitchController.semitones_to_ratio(-24) == pytest.approx(0.25)


# =============================================================================
# 2. TEST INIZIALIZZAZIONE
# =============================================================================

class TestPitchControllerInit:
    """Test inizializzazione parametri."""
    
    def test_default_ratio_mode(self, pitch_ratio_default):
        """Senza parametri → modalità ratio, ratio=1.0."""
        assert pitch_ratio_default.mode == 'ratio'
        assert pitch_ratio_default.base_ratio == 1.0
        assert pitch_ratio_default.base_semitones is None
        assert pitch_ratio_default.range == 0.0
    
    def test_explicit_ratio(self, pitch_ratio_double):
        """Ratio esplicito → modalità ratio."""
        assert pitch_ratio_double.mode == 'ratio'
        assert pitch_ratio_double.base_ratio == 2.0
        assert pitch_ratio_double.base_semitones is None
    
    def test_semitones_mode(self, pitch_semitones_fifth):
        """shift_semitones presente → modalità semitoni."""
        assert pitch_semitones_fifth.mode == 'semitones'
        assert pitch_semitones_fifth.base_semitones == 7
        assert pitch_semitones_fifth.base_ratio is None
    
    def test_semitones_envelope(self, pitch_semitones_envelope):
        """shift_semitones come envelope."""
        assert pitch_semitones_envelope.mode == 'semitones'
        assert isinstance(pitch_semitones_envelope.base_semitones, Envelope)
    
    def test_ratio_envelope(self, pitch_factory):
        """ratio come envelope."""
        pitch = pitch_factory({'ratio': [[0, 1.0], [10, 2.0]]})
        
        assert pitch.mode == 'ratio'
        assert isinstance(pitch.base_ratio, Envelope)
    
    def test_range_parsed(self, pitch_with_range):
        """Range viene parsato correttamente."""
        assert pitch_with_range.range == 0.5
    
    def test_range_envelope(self, pitch_factory):
        """Range come envelope."""
        pitch = pitch_factory({
            'ratio': 1.0,
            'range': [[0, 0.0], [10, 1.0]]
        })
        
        assert isinstance(pitch.range, Envelope)


# =============================================================================
# 3. TEST CALCOLO MODALITÀ RATIO
# =============================================================================

class TestRatioModeCalculation:
    """Test calcolo in modalità ratio."""
    
    def test_constant_ratio(self, pitch_ratio_default):
        """Ratio costante senza range → sempre lo stesso valore."""
        assert pitch_ratio_default.calculate(0.0) == pytest.approx(1.0)
        assert pitch_ratio_default.calculate(5.0) == pytest.approx(1.0)
        assert pitch_ratio_default.calculate(10.0) == pytest.approx(1.0)
    
    def test_double_ratio(self, pitch_ratio_double):
        """Ratio=2.0 → sempre 2.0."""
        assert pitch_ratio_double.calculate(0.0) == pytest.approx(2.0)
        assert pitch_ratio_double.calculate(5.0) == pytest.approx(2.0)
    
    def test_ratio_envelope(self, pitch_factory):
        """Ratio come envelope varia nel tempo."""
        pitch = pitch_factory({'ratio': [[0, 1.0], [10, 2.0]]})
        
        # A t=0: ratio=1.0
        assert pitch.calculate(0.0) == pytest.approx(1.0)
        # A t=5: ratio=1.5 (interpolazione lineare)
        assert pitch.calculate(5.0) == pytest.approx(1.5)
        # A t=10: ratio=2.0
        assert pitch.calculate(10.0) == pytest.approx(2.0)
    
    def test_ratio_with_range_bounds(self, pitch_with_range, monkeypatch):
        """Range applica deviazione entro i limiti."""
        # Mock random.uniform per valore massimo (+0.5)
        monkeypatch.setattr(random, "uniform", lambda a, b: 0.5)
        
        # base=1.0, range=0.5, deviation = 0.5 * 0.5 = 0.25
        result = pitch_with_range.calculate(0.0)
        assert result == pytest.approx(1.25)
    
    def test_ratio_with_range_negative(self, pitch_with_range, monkeypatch):
        """Range con deviazione negativa."""
        # Mock random.uniform per valore minimo (-0.5)
        monkeypatch.setattr(random, "uniform", lambda a, b: -0.5)
        
        # base=1.0, range=0.5, deviation = -0.5 * 0.5 = -0.25
        result = pitch_with_range.calculate(0.0)
        assert result == pytest.approx(0.75)


# =============================================================================
# 4. TEST CALCOLO MODALITÀ SEMITONI
# =============================================================================

class TestSemitonesModeCalculation:
    """Test calcolo in modalità semitoni."""
    
    def test_constant_semitones(self, pitch_semitones_fifth):
        """Semitoni costanti senza range → ratio costante."""
        expected_ratio = PitchController.semitones_to_ratio(7)
        
        assert pitch_semitones_fifth.calculate(0.0) == pytest.approx(expected_ratio)
        assert pitch_semitones_fifth.calculate(5.0) == pytest.approx(expected_ratio)
    
    def test_zero_semitones(self, pitch_factory):
        """0 semitoni → ratio 1.0."""
        pitch = pitch_factory({'shift_semitones': 0})
        
        assert pitch.calculate(0.0) == pytest.approx(1.0)
    
    def test_negative_semitones(self, pitch_factory):
        """-12 semitoni → ratio 0.5 (ottava giù)."""
        pitch = pitch_factory({'shift_semitones': -12})
        
        assert pitch.calculate(0.0) == pytest.approx(0.5)
    
    def test_semitones_envelope(self, pitch_semitones_envelope):
        """Semitoni come envelope variano nel tempo."""
        # A t=0: 0 semitoni → ratio 1.0
        assert pitch_semitones_envelope.calculate(0.0) == pytest.approx(1.0)
        
        # A t=5: 6 semitoni → tritono ≈ 1.414
        expected_5 = PitchController.semitones_to_ratio(6)
        assert pitch_semitones_envelope.calculate(5.0) == pytest.approx(expected_5)
        
        # A t=10: 12 semitoni → ratio 2.0
        assert pitch_semitones_envelope.calculate(10.0) == pytest.approx(2.0)
    
    def test_semitones_with_range(self, pitch_semitones_with_range, monkeypatch):
        """Range in semitoni applica deviazione intera."""
        # Mock random.randint per restituire +2 (massimo per range=4)
        monkeypatch.setattr(random, "randint", lambda a, b: 2)
        
        # base=0, range=4, deviation=+2 → 2 semitoni
        result = pitch_semitones_with_range.calculate(0.0)
        expected = PitchController.semitones_to_ratio(2)
        assert result == pytest.approx(expected)
    
    def test_semitones_range_negative_deviation(self, pitch_semitones_with_range, monkeypatch):
        """Range con deviazione negativa."""
        # Mock random.randint per restituire -2
        monkeypatch.setattr(random, "randint", lambda a, b: -2)
        
        # base=0, range=4, deviation=-2 → -2 semitoni
        result = pitch_semitones_with_range.calculate(0.0)
        expected = PitchController.semitones_to_ratio(-2)
        assert result == pytest.approx(expected)


# =============================================================================
# 5. TEST STOCASTICITÀ (senza mock)
# =============================================================================

class TestStochasticBehavior:
    """Test che il range produca effettivamente variazione."""
    
    def test_ratio_range_produces_variation(self, pitch_with_range):
        """Con range > 0, valori successivi dovrebbero variare."""
        values = [pitch_with_range.calculate(0.0) for _ in range(50)]
        
        # Non tutti uguali
        assert len(set(values)) > 1
        
        # Tutti entro i bounds (base=1.0, range=0.5 → 0.75 a 1.25)
        for v in values:
            assert 0.75 <= v <= 1.25
    
    def test_semitones_range_produces_variation(self, pitch_semitones_with_range):
        """Con range > 0 in semitoni, valori dovrebbero variare."""
        values = [pitch_semitones_with_range.calculate(0.0) for _ in range(50)]
        
        # Non tutti uguali
        assert len(set(values)) > 1
        
        # Tutti corrispondono a semitoni interi -2, -1, 0, +1, +2
        valid_ratios = {PitchController.semitones_to_ratio(s) for s in [-2, -1, 0, 1, 2]}
        for v in values:
            assert any(abs(v - vr) < 1e-9 for vr in valid_ratios)
    
    def test_zero_range_no_variation(self, pitch_ratio_default):
        """Range=0 → nessuna variazione."""
        values = [pitch_ratio_default.calculate(0.0) for _ in range(20)]
        
        # Tutti identici
        assert all(v == values[0] for v in values)


# =============================================================================
# 6. TEST BOUNDS E CLIPPING
# =============================================================================

class TestBoundsAndClipping:
    """Test che i bounds vengano rispettati."""
    
    def test_ratio_clipped_to_min(self, pitch_factory):
        """Ratio sotto il minimo viene clippato."""
        # Bounds: pitch_ratio min=0.125
        pitch = pitch_factory({'ratio': 0.01})  # Troppo basso
        
        result = pitch.calculate(0.0)
        assert result >= 0.125
    
    def test_ratio_clipped_to_max(self, pitch_factory):
        """Ratio sopra il massimo viene clippato."""
        # Bounds: pitch_ratio max=8.0
        pitch = pitch_factory({'ratio': 100.0})  # Troppo alto
        
        result = pitch.calculate(0.0)
        assert result <= 8.0
    
    def test_semitones_clipped_to_min(self, pitch_factory):
        """Semitoni sotto il minimo vengono clippati."""
        # Bounds: pitch_semitones min=-36
        pitch = pitch_factory({'shift_semitones': -100})
        
        result = pitch.calculate(0.0)
        # -36 semitoni = 2^(-36/12) = 2^(-3) = 0.125
        min_ratio = PitchController.semitones_to_ratio(-36)
        assert result >= min_ratio - 1e-9
    
    def test_semitones_clipped_to_max(self, pitch_factory):
        """Semitoni sopra il massimo vengono clippati."""
        # Bounds: pitch_semitones max=36
        pitch = pitch_factory({'shift_semitones': 100})
        
        result = pitch.calculate(0.0)
        # 36 semitoni = 2^(36/12) = 2^3 = 8.0
        max_ratio = PitchController.semitones_to_ratio(36)
        assert result <= max_ratio + 1e-9


# =============================================================================
# 7. TEST REPR
# =============================================================================

class TestRepr:
    """Test rappresentazione stringa."""
    
    def test_repr_ratio_mode(self, pitch_ratio_double):
        """Repr in modalità ratio."""
        r = repr(pitch_ratio_double)
        assert "PitchController" in r
        assert "ratio=2.0" in r
    
    def test_repr_semitones_mode(self, pitch_semitones_fifth):
        """Repr in modalità semitoni."""
        r = repr(pitch_semitones_fifth)
        assert "PitchController" in r
        assert "semitones=7" in r
    
    def test_repr_with_range(self, pitch_with_range):
        """Repr include range se presente."""
        r = repr(pitch_with_range)
        assert "range=" in r


# =============================================================================
# 8. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_very_small_range(self, pitch_factory, monkeypatch):
        """Range molto piccolo produce deviazione minima."""
        pitch = pitch_factory({'ratio': 1.0, 'range': 0.001})
        
        monkeypatch.setattr(random, "uniform", lambda a, b: 0.5)
        
        result = pitch.calculate(0.0)
        # 1.0 + 0.5 * 0.001 = 1.0005
        assert result == pytest.approx(1.0005)
    
    def test_fractional_semitones_in_envelope(self, pitch_factory):
        """Envelope può produrre semitoni frazionari (microtoni)."""
        pitch = pitch_factory({'shift_semitones': [[0, 0], [10, 1]]})
        
        # A t=5: 0.5 semitoni (quarto di tono)
        result = pitch.calculate(5.0)
        expected = PitchController.semitones_to_ratio(0.5)
        assert result == pytest.approx(expected)
    
    def test_negative_time(self, pitch_ratio_double):
        """Tempo negativo usa il valore iniziale dell'envelope."""
        # Per ratio costante non fa differenza
        result = pitch_ratio_double.calculate(-5.0)
        assert result == pytest.approx(2.0)
    
    def test_time_beyond_envelope(self, pitch_semitones_envelope):
        """Tempo oltre l'envelope usa il valore finale."""
        # Envelope 0→12 in 10s, a t=20 dovrebbe essere 12 semitoni
        result = pitch_semitones_envelope.calculate(20.0)
        assert result == pytest.approx(2.0)  # 12 semitoni = ratio 2.0