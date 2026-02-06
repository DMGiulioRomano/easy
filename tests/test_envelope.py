# test_envelope.py
"""
Test suite completa per Envelope dopo refactoring Sprint 3.

Formati supportati:
1. Standard breakpoints: [[t, v], ...]
2. Formato compatto: [[[x%, y], ...], total_time, n_reps, interp?]
3. Dict format: {'type': 'cubic', 'points': [...]}

Organizzazione:
1. Test inizializzazione e parsing
2. Test evaluate - standard format
3. Test evaluate - compact format
4. Test integrate - standard format
5. Test integrate - compact format
6. Test interpolation types (linear, step, cubic)
7. Test formato misto
8. Test edge cases
9. Test validazione errori
10. Test proprietà matematiche
"""

import pytest
from envelope import Envelope
from envelope_segment import NormalSegment


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def env_standard_ramp():
    """Rampa lineare standard: 0→100 in 10s."""
    return Envelope([[0, 0], [10, 100]])

@pytest.fixture
def env_standard_triangle():
    """Triangolo standard: salita e discesa."""
    return Envelope([[0, 0], [5, 100], [10, 0]])

@pytest.fixture
def env_compact_simple():
    """Formato compatto: 4 ripetizioni in 0.4s."""
    return Envelope([[[0, 0], [100, 1]], 0.4, 4])

@pytest.fixture
def env_compact_three_points():
    """Formato compatto con 3 punti nel pattern."""
    return Envelope([[[0, 0], [50, 0.5], [100, 1]], 0.3, 3])

@pytest.fixture
def env_dict_cubic():
    """Dict format con interpolazione cubic."""
    return Envelope({'type': 'cubic', 'points': [[0, 0], [1, 10], [2, 5]]})


# =============================================================================
# 1. TEST INIZIALIZZAZIONE E PARSING
# =============================================================================

class TestInitializationAndParsing:
    """Test parsing e validazione dell'input."""
    
    def test_parse_standard_list(self):
        """Parsing lista standard di breakpoints."""
        env = Envelope([[0, 0], [0.5, 1], [1.0, 0]])
        
        assert len(env.segments) == 1
        assert isinstance(env.segments[0], NormalSegment)
        assert env.type == 'linear'
    
    def test_parse_compact_format(self):
        """Parsing formato compatto."""
        env = Envelope([[[0, 0], [100, 1]], 0.4, 4])
        
        assert len(env.segments) == 1
        assert isinstance(env.segments[0], NormalSegment)
        # Breakpoints espansi: 4 cicli * 2 punti + 3 discontinuità = 11
        assert len(env.segments[0].breakpoints) == 11
    
    def test_parse_dict_format(self):
        """Parsing dict format."""
        env = Envelope({'type': 'cubic', 'points': [[0, 0], [1, 10]]})
        
        assert env.type == 'cubic'
        assert len(env.segments) == 1
        assert 'tangents' in env.segments[0].context
    
    def test_parse_mixed_format(self):
        """Parsing formato misto (compatto + standard)."""
        env = Envelope([
            [[[0, 0], [100, 1]], 0.2, 2],  # Compatto
            [0.5, 0.5],                     # Standard
            [1.0, 0]                        # Standard
        ])
        
        assert len(env.segments) == 1
        # Breakpoints espansi includono tutto
        assert len(env.segments[0].breakpoints) > 5
    
    def test_single_breakpoint(self):
        """Envelope con singolo breakpoint."""
        env = Envelope([[0, 42]])
        
        assert len(env.segments) == 1
        assert len(env.segments[0].breakpoints) == 1
    
    def test_type_defaults_to_linear(self):
        """Tipo default è 'linear' se non specificato."""
        env = Envelope([[0, 0], [1, 10]])
        assert env.type == 'linear'
    
    def test_compact_format_with_interp_type(self):
        """Formato compatto con tipo interpolazione."""
        env = Envelope([[[0, 0], [100, 1]], 0.2, 2, 'cubic'])
        assert env.type == 'cubic'


# =============================================================================
# 2. TEST EVALUATE - STANDARD FORMAT
# =============================================================================

class TestEvaluateStandard:
    """Test evaluate con formato standard."""
    
    def test_evaluate_at_breakpoints(self, env_standard_ramp):
        """Valutazione esatta ai breakpoints."""
        assert env_standard_ramp.evaluate(0) == pytest.approx(0.0)
        assert env_standard_ramp.evaluate(10) == pytest.approx(100.0)
    
    def test_evaluate_between_breakpoints(self, env_standard_ramp):
        """Interpolazione lineare tra breakpoints."""
        assert env_standard_ramp.evaluate(5) == pytest.approx(50.0)
        assert env_standard_ramp.evaluate(2.5) == pytest.approx(25.0)
        assert env_standard_ramp.evaluate(7.5) == pytest.approx(75.0)
    
    def test_evaluate_before_first_breakpoint(self, env_standard_ramp):
        """Hold primo valore prima del primo breakpoint."""
        assert env_standard_ramp.evaluate(-5) == pytest.approx(0.0)
        assert env_standard_ramp.evaluate(-0.001) == pytest.approx(0.0)
    
    def test_evaluate_after_last_breakpoint(self, env_standard_ramp):
        """Hold ultimo valore dopo l'ultimo breakpoint."""
        assert env_standard_ramp.evaluate(15) == pytest.approx(100.0)
        assert env_standard_ramp.evaluate(100) == pytest.approx(100.0)
    
    def test_evaluate_triangle_peak(self, env_standard_triangle):
        """Valutazione al picco del triangolo."""
        assert env_standard_triangle.evaluate(5) == pytest.approx(100.0)
    
    def test_evaluate_triangle_slopes(self, env_standard_triangle):
        """Valutazione sulle pendenze del triangolo."""
        # Salita
        assert env_standard_triangle.evaluate(2.5) == pytest.approx(50.0)
        # Discesa
        assert env_standard_triangle.evaluate(7.5) == pytest.approx(50.0)
    
    def test_evaluate_constant_envelope(self):
        """Envelope costante."""
        env = Envelope([[0, 42], [10, 42]])
        assert env.evaluate(5) == pytest.approx(42.0)
        assert env.evaluate(-5) == pytest.approx(42.0)
        assert env.evaluate(15) == pytest.approx(42.0)
    
    def test_evaluate_single_breakpoint(self):
        """Singolo breakpoint: sempre costante."""
        env = Envelope([[5, 100]])
        assert env.evaluate(0) == pytest.approx(100.0)
        assert env.evaluate(5) == pytest.approx(100.0)
        assert env.evaluate(10) == pytest.approx(100.0)


# =============================================================================
# 3. TEST EVALUATE - COMPACT FORMAT
# =============================================================================

class TestEvaluateCompact:
    """Test evaluate con formato compatto."""
    
    def test_evaluate_first_cycle(self, env_compact_simple):
        """Primo ciclo (0-0.1s)."""
        assert env_compact_simple.evaluate(0.0) == pytest.approx(0.0)
        assert env_compact_simple.evaluate(0.05) == pytest.approx(0.5)
        assert env_compact_simple.evaluate(0.1) == pytest.approx(1.0)
    
    def test_evaluate_at_discontinuity(self, env_compact_simple):
        """Valutazione alla discontinuità (reset)."""
        # t=0.100001 è il punto di discontinuità
        assert env_compact_simple.evaluate(0.100001) == pytest.approx(0.0)
    
    def test_evaluate_second_cycle(self, env_compact_simple):
        """Secondo ciclo (0.1-0.2s)."""
        assert env_compact_simple.evaluate(0.15) == pytest.approx(0.5, abs=1e-4)
        assert env_compact_simple.evaluate(0.2) == pytest.approx(1.0)
    
    def test_evaluate_last_cycle(self, env_compact_simple):
        """Ultimo ciclo (0.3-0.4s)."""
        assert env_compact_simple.evaluate(0.35) == pytest.approx(0.5, abs=1e-4)
        assert env_compact_simple.evaluate(0.4) == pytest.approx(1.0)
    
    def test_evaluate_after_compact(self, env_compact_simple):
        """Dopo l'ultimo ciclo: hold."""
        assert env_compact_simple.evaluate(0.5) == pytest.approx(1.0)
        assert env_compact_simple.evaluate(1.0) == pytest.approx(1.0)
    
    def test_evaluate_three_points_pattern(self, env_compact_three_points):
        """Pattern con 3 punti."""
        # Primo ciclo: 0%, 50%, 100%
        assert env_compact_three_points.evaluate(0.0) == pytest.approx(0.0)
        assert env_compact_three_points.evaluate(0.05) == pytest.approx(0.5)
        assert env_compact_three_points.evaluate(0.1) == pytest.approx(1.0)
        
        # Secondo ciclo
        assert env_compact_three_points.evaluate(0.15) == pytest.approx(0.5)


# =============================================================================
# 4. TEST INTEGRATE - STANDARD FORMAT
# =============================================================================

class TestIntegrateStandard:
    """Test integrate con formato standard."""
    
    def test_integrate_full_ramp(self, env_standard_ramp):
        """Integrale rampa completa: triangolo."""
        # Area = (base * altezza) / 2 = (10 * 100) / 2 = 500
        area = env_standard_ramp.integrate(0, 10)
        assert area == pytest.approx(500.0)
    
    def test_integrate_half_ramp(self, env_standard_ramp):
        """Integrale metà rampa."""
        # Da 0 a 5: area = (5 * 50) / 2 = 125
        area = env_standard_ramp.integrate(0, 5)
        assert area == pytest.approx(125.0)
    
    def test_integrate_triangle_full(self, env_standard_triangle):
        """Integrale triangolo completo."""
        # Salita + discesa: 2 * (5 * 100) / 2 = 500
        area = env_standard_triangle.integrate(0, 10)
        assert area == pytest.approx(500.0)
    
    def test_integrate_constant(self):
        """Integrale envelope costante."""
        env = Envelope([[0, 50], [10, 50]])
        # Area = base * altezza = 10 * 50 = 500
        area = env.integrate(0, 10)
        assert area == pytest.approx(500.0)
    
    def test_integrate_with_hold_before(self):
        """Integrale con hold prima del primo breakpoint."""
        env = Envelope([[5, 50], [10, 100]])
        # Hold (0-5): 5 * 50 = 250
        # Rampa (5-10): trapezio = (5 * (50+100)) / 2 = 375
        # Totale: 625
        area = env.integrate(0, 10)
        assert area == pytest.approx(625.0)
    
    def test_integrate_with_hold_after(self):
        """Integrale con hold dopo l'ultimo breakpoint."""
        env = Envelope([[0, 0], [10, 100]])
        # Rampa (0-10): 500
        # Hold (10-15): 5 * 100 = 500
        # Totale: 1000
        area = env.integrate(0, 15)
        assert area == pytest.approx(1000.0)
    
    def test_integrate_zero_interval(self, env_standard_ramp):
        """Intervallo nullo: area zero."""
        assert env_standard_ramp.integrate(5, 5) == pytest.approx(0.0)
    
    def test_integrate_reverse_interval(self, env_standard_ramp):
        """Intervallo invertito: area negativa."""
        forward = env_standard_ramp.integrate(0, 10)
        backward = env_standard_ramp.integrate(10, 0)
        assert backward == pytest.approx(-forward)


# =============================================================================
# 5. TEST INTEGRATE - COMPACT FORMAT
# =============================================================================

class TestIntegrateCompact:
    """Test integrate con formato compatto."""
    
    def test_integrate_one_cycle(self):
        """Integrale di un singolo ciclo."""
        env = Envelope([[[0, 0], [100, 1]], 0.1, 1])
        # Area triangolo: (0.1 * 1) / 2 = 0.05
        area = env.integrate(0, 0.1)
        assert area == pytest.approx(0.05)
    
    def test_integrate_multiple_cycles(self, env_compact_simple):
        """Integrale di 4 cicli."""
        # Area 1 ciclo = 0.05
        # Area 4 cicli = 0.2
        area = env_compact_simple.integrate(0, 0.4)
        assert area == pytest.approx(0.2, rel=1e-2)
    
    def test_integrate_partial_cycles(self, env_compact_simple):
        """Integrale parziale (1.5 cicli)."""
        # 1.5 cicli = 1.5 * 0.05 = 0.075
        area = env_compact_simple.integrate(0, 0.15)
        assert area == pytest.approx(0.075, rel=1e-2)
    
    def test_integrate_across_discontinuity(self, env_compact_simple):
        """Integrale che attraversa discontinuità."""
        # Da 0.05 a 0.15 (attraversa discontinuità a 0.100001)
        area = env_compact_simple.integrate(0.05, 0.15)
        expected = 0.05  # Circa metà di 2 cicli
        assert area == pytest.approx(expected, rel=1e-2)
    
    def test_integrate_with_hold_after_compact(self, env_compact_simple):
        """Integrale oltre l'ultimo ciclo."""
        # Cicli (0-0.4): 0.2
        # Hold (0.4-0.5): 0.1 * 1 = 0.1
        # Totale: 0.3
        area = env_compact_simple.integrate(0, 0.5)
        assert area == pytest.approx(0.3, rel=1e-2)


# =============================================================================
# 6. TEST INTERPOLATION TYPES
# =============================================================================

class TestInterpolationTypes:
    """Test tipi di interpolazione (linear, step, cubic)."""
    
    def test_linear_interpolation(self):
        """Interpolazione lineare."""
        env = Envelope({'type': 'linear', 'points': [[0, 0], [10, 100]]})
        assert env.type == 'linear'
        assert env.evaluate(5) == pytest.approx(50.0)
    
    def test_step_interpolation_evaluate(self):
        """Step: hold valore sinistro."""
        env = Envelope({'type': 'step', 'points': [[0, 10], [5, 50], [10, 100]]})
        assert env.type == 'step'
        
        # Hold valore a sinistra fino al prossimo breakpoint
        assert env.evaluate(0) == pytest.approx(10.0)
        assert env.evaluate(2.5) == pytest.approx(10.0)
        assert env.evaluate(4.9) == pytest.approx(10.0)
        assert env.evaluate(5) == pytest.approx(50.0)
        assert env.evaluate(7.5) == pytest.approx(50.0)
        assert env.evaluate(10) == pytest.approx(100.0)
    
    def test_step_interpolation_integrate(self):
        """Step: area rettangolo."""
        env = Envelope({'type': 'step', 'points': [[0, 10], [5, 50]]})
        # Rettangolo: 5 * 10 = 50
        area = env.integrate(0, 5)
        assert area == pytest.approx(50.0)
    
    def test_cubic_interpolation(self, env_dict_cubic):
        """Cubic: usa tangenti Fritsch-Carlson."""
        assert env_dict_cubic.type == 'cubic'
        assert 'tangents' in env_dict_cubic.segments[0].context
        
        # Cubic dovrebbe passare per i breakpoints
        assert env_dict_cubic.evaluate(0) == pytest.approx(0.0)
        assert env_dict_cubic.evaluate(1) == pytest.approx(10.0)
        assert env_dict_cubic.evaluate(2) == pytest.approx(5.0)
    
    def test_cubic_smooth_interpolation(self):
        """Cubic: interpolazione smooth (no overshoot)."""
        env = Envelope({'type': 'cubic', 'points': [[0, 0], [1, 10], [2, 10]]})
        
        # Non deve superare 10 (Fritsch-Carlson previene overshoot)
        for t in [0.5, 1.0, 1.5]:
            val = env.evaluate(t)
            assert 0 <= val <= 10.1  # Piccola tolleranza


# =============================================================================
# 7. TEST FORMATO MISTO
# =============================================================================

class TestMixedFormats:
    """Test combinazioni di formati."""
    
    def test_compact_plus_standard(self):
        """Formato compatto + standard breakpoints."""
        env = Envelope([
            [[[0, 0], [100, 1]], 0.2, 2],  # Compatto: 0-0.2
            [0.5, 0.5],                     # Standard
            [1.0, 0]                        # Standard
        ])
        
        # Parte compatta
        assert env.evaluate(0.1) == pytest.approx(1.0)
        
        # Parte standard
        assert env.evaluate(0.5) == pytest.approx(0.5)
        assert env.evaluate(0.75) == pytest.approx(0.25)
    
    def test_multiple_compact_segments(self):
        """Più segmenti compatti nella stessa lista."""
        env = Envelope([
            [[[0, 0], [100, 1]], 0.2, 2],      # Primo compatto
            [[[0, 1], [100, 0]], 0.4, 2]       # Secondo compatto
        ])
        
        # Primo segmento
        assert env.evaluate(0.1) == pytest.approx(1.0)
        
        # Transizione (tra i due segmenti compatti)
        # Dopo espansione, ci sono breakpoints connessi
        assert env.evaluate(0.3) == pytest.approx(0.5, abs=1e-4)
    
    def test_dict_with_compact_points(self):
        """Dict con formato compatto in 'points'."""
        env = Envelope({
            'type': 'cubic',
            'points': [[[0, 0], [100, 1]], 0.2, 2]
        })
        
        assert env.type == 'cubic'
        assert env.evaluate(0.1) == pytest.approx(1.0, rel=1e-2)


# =============================================================================
# 8. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_very_small_values(self):
        """Valori molto piccoli."""
        env = Envelope([[0, 0.0001], [1, 0.0002]])
        assert env.evaluate(0.5) == pytest.approx(0.00015)
    
    def test_very_large_values(self):
        """Valori molto grandi."""
        env = Envelope([[0, 1e6], [1, 2e6]])
        assert env.evaluate(0.5) == pytest.approx(1.5e6)
    
    def test_negative_values(self):
        """Valori negativi."""
        env = Envelope([[0, -100], [1, 100]])
        assert env.evaluate(0.5) == pytest.approx(0.0)
    
    def test_zero_duration_segment(self):
        """Breakpoints con stesso tempo (durata zero)."""
        env = Envelope([[0, 0], [0, 10], [1, 20]])
        # Secondo breakpoint sovrascrive il primo
        assert env.evaluate(0) == pytest.approx(10.0)
    
    def test_unsorted_breakpoints(self):
        """Breakpoints non ordinati: vengono ordinati automaticamente."""
        env = Envelope([[10, 100], [0, 0], [5, 50]])
        # Dovrebbero essere ordinati: [0,0], [5,50], [10,100]
        assert env.evaluate(0) == pytest.approx(0.0)
        assert env.evaluate(5) == pytest.approx(50.0)
        assert env.evaluate(10) == pytest.approx(100.0)
    
    def test_compact_single_repetition(self):
        """Formato compatto con n_reps=1."""
        env = Envelope([[[0, 0], [100, 1]], 0.1, 1])
        # Singolo ciclo, nessuna discontinuità
        assert len(env.segments[0].breakpoints) == 2
        assert env.evaluate(0.05) == pytest.approx(0.5)
    
    def test_compact_many_repetitions(self):
        """Formato compatto con molte ripetizioni."""
        env = Envelope([[[0, 0], [100, 1]], 1.0, 100])
        # 100 cicli: 100 * 2 punti + 99 discontinuità = 299 breakpoints
        assert len(env.segments[0].breakpoints) == 299
        
        # Verifica alcuni valori
        assert env.evaluate(0.005) == pytest.approx(0.5)  # Metà primo ciclo
        assert env.evaluate(0.505) == pytest.approx(0.5, abs=1e-4)  # Metà 51° ciclo


# =============================================================================
# 9. TEST VALIDAZIONE ERRORI
# =============================================================================

class TestValidation:
    """Test validazione input."""
    
    def test_error_empty_list(self):
        """Lista vuota: errore."""
        with pytest.raises(ValueError, match="vuota"):
            Envelope([])
    
    def test_error_invalid_breakpoint_format(self):
        """Breakpoint con formato invalido."""
        with pytest.raises(ValueError, match="non valido"):
            Envelope([[0]])  # Manca il valore
    
    def test_error_invalid_type(self):
        """Input né list né dict: errore."""
        with pytest.raises(ValueError, match="non valido"):
            Envelope(42)
        
        with pytest.raises(ValueError, match="non valido"):
            Envelope("[[0,0],[1,10]]")
    
    def test_error_dict_missing_points(self):
        """Dict senza chiave 'points': errore."""
        with pytest.raises(KeyError):
            Envelope({'type': 'linear'})
    
    def test_error_invalid_interp_type(self):
        """Tipo interpolazione non riconosciuto."""
        with pytest.raises(ValueError, match="non riconosciuto"):
            Envelope({'type': 'exponential', 'points': [[0, 0], [1, 10]]})
    
    def test_error_compact_zero_reps(self):
        """Formato compatto con n_reps=0."""
        with pytest.raises(ValueError, match="n_reps deve essere >= 1"):
            Envelope([[[0, 0], [100, 1]], 0.2, 0])
    
    def test_error_compact_negative_time(self):
        """Formato compatto con total_time negativo."""
        with pytest.raises(ValueError, match="total_time deve essere > 0"):
            Envelope([[[0, 0], [100, 1]], -0.2, 2])
    
    def test_error_compact_empty_pattern(self):
        """Formato compatto con pattern vuoto."""
        with pytest.raises(ValueError, match="pattern_points non può essere vuoto"):
            Envelope([[], 0.2, 2])


# =============================================================================
# 10. TEST PROPRIETÀ MATEMATICHE
# =============================================================================

class TestMathematicalProperties:
    """Test proprietà matematiche dell'integrale."""
    
    def test_additivity(self, env_standard_ramp):
        """∫[a,c] = ∫[a,b] + ∫[b,c]."""
        full = env_standard_ramp.integrate(0, 10)
        part1 = env_standard_ramp.integrate(0, 5)
        part2 = env_standard_ramp.integrate(5, 10)
        assert full == pytest.approx(part1 + part2)
    
    def test_linearity_scaling(self):
        """Scalare i valori 2x scala l'integrale 2x."""
        env1 = Envelope([[0, 0], [10, 50]])
        env2 = Envelope([[0, 0], [10, 100]])
        
        area1 = env1.integrate(0, 10)
        area2 = env2.integrate(0, 10)
        
        assert area2 == pytest.approx(2 * area1)
    
    def test_time_scaling(self):
        """Scalare il tempo 2x scala l'integrale 2x."""
        env1 = Envelope([[0, 0], [5, 100]])
        env2 = Envelope([[0, 0], [10, 100]])
        
        area1 = env1.integrate(0, 5)
        area2 = env2.integrate(0, 10)
        
        assert area2 == pytest.approx(2 * area1)
    
    def test_symmetry(self, env_standard_triangle):
        """Triangolo simmetrico: area prevedibile."""
        area = env_standard_triangle.integrate(0, 10)
        # Base * altezza / 2 = 10 * 100 / 2 = 500
        assert area == pytest.approx(500.0)
    
    def test_compact_n_cycles_equals_n_times_one(self):
        """N cicli compatti = N * (area 1 ciclo)."""
        env = Envelope([[[0, 0], [100, 1]], 1.0, 10])
        
        one_cycle = env.integrate(0, 0.1)
        ten_cycles = env.integrate(0, 1.0)
        
        assert ten_cycles == pytest.approx(10 * one_cycle, rel=1e-2)
    
    def test_integral_bounds_independence(self):
        """Integrale indipendente dai bounds se completamente contenuto."""
        env1 = Envelope([[0, 0], [1, 10]])
        env2 = Envelope([[0, 0], [1, 10], [2, 10]])  # Stesso ma con hold esteso
        
        # Integrale su [0,1] deve essere uguale
        area1 = env1.integrate(0, 1)
        area2 = env2.integrate(0, 1)
        assert area1 == pytest.approx(area2)


# =============================================================================
# 11. TEST BACKWARD COMPATIBILITY
# =============================================================================

class TestBackwardCompatibility:
    """Test compatibilità con envelope standard (NON-cycle)."""
    
    def test_simple_envelope_works(self):
        """Envelope semplice funziona come prima."""
        env = Envelope([[0, 0], [0.5, 1], [1.0, 0]])
        
        assert env.evaluate(0.0) == pytest.approx(0.0)
        assert env.evaluate(0.25) == pytest.approx(0.5)
        assert env.evaluate(0.5) == pytest.approx(1.0)
        assert env.evaluate(0.75) == pytest.approx(0.5)
        assert env.evaluate(1.0) == pytest.approx(0.0)
    
    def test_dict_format_works(self):
        """Dict format funziona come prima."""
        env = Envelope({
            'type': 'cubic',
            'points': [[0, 0], [0.5, 1], [1.0, 0]]
        })
        
        assert env.type == 'cubic'
        assert env.evaluate(0.5) == pytest.approx(1.0)
    
    def test_is_envelope_like_standard(self):
        """is_envelope_like riconosce formato standard."""
        assert Envelope.is_envelope_like([[0, 0], [1, 10]])
        assert Envelope.is_envelope_like({'type': 'linear', 'points': [[0, 0]]})
        
        env = Envelope([[0, 0], [1, 10]])
        assert Envelope.is_envelope_like(env)
    
    def test_is_envelope_like_compact(self):
        """is_envelope_like riconosce formato compatto."""
        assert Envelope.is_envelope_like([[[0, 0], [100, 1]], 0.2, 2])
    
    def test_is_envelope_like_invalid(self):
        """is_envelope_like rifiuta formati invalidi."""
        assert not Envelope.is_envelope_like(42)
        assert not Envelope.is_envelope_like("envelope")
        assert not Envelope.is_envelope_like([])
        assert not Envelope.is_envelope_like({})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])