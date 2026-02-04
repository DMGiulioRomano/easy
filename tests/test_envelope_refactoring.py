# tests/test_envelope_refactoring.py
"""
Test suite per verificare backward compatibility dopo refactoring Sprint 2B.

Organizzazione:
1. Test che vecchi format funzionino ancora
2. Test che evaluate() dia stessi risultati
3. Test che integrate() dia stessi risultati
4. Test che errori vengano sollevati come prima
5. Test nuova architettura (segments come List[Segment])
"""

import pytest
from envelope import Envelope
from envelope_segment import NormalSegment, CyclicSegment


# =============================================================================
# 1. TEST BACKWARD COMPATIBILITY - FORMATI
# =============================================================================

class TestBackwardCompatibilityFormats:
    """Test che vecchi formati funzionino ancora."""
    
    def test_simple_list_format(self):
        """Lista semplice di breakpoints."""
        env = Envelope([[0, 0], [0.5, 1], [1.0, 0]])
        assert len(env.segments) == 1
        assert isinstance(env.segments[0], NormalSegment)
    
    def test_cycle_format(self):
        """Formato con marker 'cycle'."""
        env = Envelope([[0, 0], [0.1, 1], 'cycle'])
        assert len(env.segments) == 1
        assert isinstance(env.segments[0], CyclicSegment)
    
    def test_mixed_cycle_normal(self):
        """Mix di segmenti ciclici e normali."""
        env = Envelope([[0, 0], [0.1, 1], 'cycle', [0.5, 0.5], [1.0, 0]])
        assert len(env.segments) == 2
        assert isinstance(env.segments[0], CyclicSegment)
        assert isinstance(env.segments[1], NormalSegment)
    
    def test_dict_format_linear(self):
        """Dict con tipo 'linear'."""
        env = Envelope({'type': 'linear', 'points': [[0, 0], [1, 10]]})
        assert env.type == 'linear'
        assert len(env.segments) == 1
    
    def test_dict_format_cubic(self):
        """Dict con tipo 'cubic'."""
        env = Envelope({'type': 'cubic', 'points': [[0, 0], [1, 10]]})
        assert env.type == 'cubic'
        # Cubic deve avere tangenti in context
        assert 'tangents' in env.segments[0].context
    
    def test_dict_format_step(self):
        """Dict con tipo 'step'."""
        env = Envelope({'type': 'step', 'points': [[0, 0], [1, 10]]})
        assert env.type == 'step'


# =============================================================================
# 2. TEST BACKWARD COMPATIBILITY - EVALUATE
# =============================================================================

class TestBackwardCompatibilityEvaluate:
    """Test che evaluate() dia stessi risultati."""
    
    def test_evaluate_simple_ramp(self):
        """Rampa semplice."""
        env = Envelope([[0, 0], [10, 100]])
        assert env.evaluate(0) == pytest.approx(0.0)
        assert env.evaluate(5) == pytest.approx(50.0)
        assert env.evaluate(10) == pytest.approx(100.0)
    
    def test_evaluate_hold_after(self):
        """Hold dopo l'ultimo breakpoint."""
        env = Envelope([[0, 0], [1, 10]])
        assert env.evaluate(2.0) == pytest.approx(10.0)
        assert env.evaluate(100.0) == pytest.approx(10.0)
    
    def test_evaluate_hold_before(self):
        """Hold prima del primo breakpoint."""
        env = Envelope([[5, 50], [10, 100]])
        assert env.evaluate(0.0) == pytest.approx(50.0)
        assert env.evaluate(2.5) == pytest.approx(50.0)
    
    def test_evaluate_cycle_wrapping(self):
        """Ciclo con wrapping temporale."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        # Primo ciclo
        assert env.evaluate(0.5) == pytest.approx(5.0)
        # Secondo ciclo (wraps)
        assert env.evaluate(1.5) == pytest.approx(5.0)
        # Terzo ciclo
        assert env.evaluate(2.5) == pytest.approx(5.0)
    
    def test_evaluate_step_interpolation(self):
        """Step interpolation."""
        env = Envelope({'type': 'step', 'points': [[0, 10], [5, 50]]})
        assert env.evaluate(0) == pytest.approx(10.0)
        assert env.evaluate(2.5) == pytest.approx(10.0)
        assert env.evaluate(5) == pytest.approx(50.0)


# =============================================================================
# 3. TEST BACKWARD COMPATIBILITY - INTEGRATE
# =============================================================================

class TestBackwardCompatibilityIntegrate:
    """Test che integrate() dia stessi risultati."""
    
    def test_integrate_triangle(self):
        """Triangolo: area base*altezza/2."""
        env = Envelope([[0, 0], [5, 100], [10, 0]])
        area = env.integrate(0, 10)
        assert area == pytest.approx(500.0)
    
    def test_integrate_rectangle(self):
        """Rettangolo: area base*altezza."""
        env = Envelope([[0, 50], [10, 50]])
        area = env.integrate(0, 10)
        assert area == pytest.approx(500.0)
    
    def test_integrate_cycle_single_period(self):
        """Ciclo: un periodo completo."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        area = env.integrate(0, 1)
        assert area == pytest.approx(5.0)
    
    def test_integrate_cycle_multiple_periods(self):
        """Ciclo: N periodi = N * area_singolo."""
        env = Envelope([[0, 0], [1, 10], 'cycle'])
        one_cycle = env.integrate(0, 1)
        five_cycles = env.integrate(0, 5)
        assert five_cycles == pytest.approx(5 * one_cycle)
    
    def test_integrate_mixed_segments(self):
        """Mix ciclo + normale."""
        env = Envelope([
            [0, 0], [1, 10], 'cycle',  # Ciclo: 0-1
            [5, 10], [10, 0]            # Normale: 5-10
        ])
        # Ciclo (0-5): 5 ripetizioni = 5 * 5 = 25
        # Normale (5-10): triangolo = 25
        # Totale: 50
        total = env.integrate(0, 10)
        assert total == pytest.approx(50.0, rel=1e-2)  # NON 70.0!

# =============================================================================
# 4. TEST BACKWARD COMPATIBILITY - ERRORI
# =============================================================================

class TestBackwardCompatibilityErrors:
    """Test che errori vengano sollevati come prima."""
    
    def test_error_invalid_type(self):
        """Tipo interpolazione invalido."""
        with pytest.raises(ValueError, match="non riconosciuto"):
            Envelope({'type': 'exponential', 'points': [[0, 0], [1, 10]]})
    
    def test_error_cycle_too_few_points(self):
        """Ciclo con meno di 2 breakpoints."""
        with pytest.raises(ValueError, match="almeno 2 breakpoints"):
            Envelope([[0, 0], 'cycle'])
    
    def test_error_invalid_string_marker(self):
        """Stringa diversa da 'cycle'."""
        with pytest.raises(ValueError, match="non riconosciuta"):
            Envelope([[0, 0], [0.1, 1], 'repeat'])
    
    def test_error_invalid_breakpoint_format(self):
        """Breakpoint con formato invalido."""
        with pytest.raises(ValueError, match="non valido"):
            Envelope([[0, 0], [0.1], 'cycle'])  # Manca il valore
    
    def test_error_empty_envelope(self):
        """Envelope vuoto."""
        with pytest.raises(ValueError, match="almeno un breakpoint"):
            Envelope([])


# =============================================================================
# 5. TEST NUOVA ARCHITETTURA
# =============================================================================

class TestNewArchitecture:
    """Test che verificano la nuova architettura."""
    
    def test_segments_are_segment_instances(self):
        """Segments sono istanze di Segment, non dict."""
        env = Envelope([[0, 0], [1, 10]])
        assert len(env.segments) == 1
        assert isinstance(env.segments[0], NormalSegment)
        assert not isinstance(env.segments[0], dict)
    
    def test_strategy_is_created_by_factory(self):
        """Strategy è creata tramite factory."""
        env = Envelope({'type': 'cubic', 'points': [[0, 0], [1, 10]]})
        # Strategy deve essere istanza, non None
        assert env.strategy is not None
        assert hasattr(env.strategy, 'evaluate')
        assert hasattr(env.strategy, 'integrate')
    
    def test_cubic_context_has_tangents(self):
        """Cubic segments hanno tangenti in context."""
        env = Envelope({'type': 'cubic', 'points': [[0, 0], [1, 10], [2, 5]]})
        segment = env.segments[0]
        assert 'tangents' in segment.context
        assert len(segment.context['tangents']) == 3
    
    def test_segment_delegation_works(self):
        """Envelope delega correttamente ai Segment."""
        env = Envelope([[0, 0], [1, 10]])
        segment = env.segments[0]
        
        # evaluate() deve delegare
        env_result = env.evaluate(0.5)
        seg_result = segment.evaluate(0.5)
        assert env_result == pytest.approx(seg_result)
        
        # integrate() deve delegare
        env_area = env.integrate(0, 1)
        seg_area = segment.integrate(0, 1)
        assert env_area == pytest.approx(seg_area)


# =============================================================================
# 6. TEST PROPERTIES MATEMATICHE (REGRESSIONE)
# =============================================================================

class TestMathematicalPropertiesRegression:
    """Test che proprietà matematiche siano preservate."""
    
    def test_additivity(self):
        """∫[a,c] = ∫[a,b] + ∫[b,c]."""
        env = Envelope([[0, 0], [10, 100]])
        full = env.integrate(0, 10)
        part1 = env.integrate(0, 5)
        part2 = env.integrate(5, 10)
        assert full == pytest.approx(part1 + part2)
    
    def test_reverse_interval(self):
        """∫[a,b] = -∫[b,a]."""
        env = Envelope([[0, 0], [10, 100]])
        forward = env.integrate(0, 10)
        backward = env.integrate(10, 0)
        assert backward == pytest.approx(-forward)
    
    def test_zero_interval(self):
        """∫[a,a] = 0."""
        env = Envelope([[0, 0], [10, 100]])
        assert env.integrate(5, 5) == pytest.approx(0.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])