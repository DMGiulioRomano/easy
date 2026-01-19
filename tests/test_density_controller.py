"""
Test suite per DensityController.
Usa fixtures globali da conftest.py (mock_evaluator, density_factory).
"""

import pytest
from unittest.mock import Mock, patch
from envelope import Envelope

# =============================================================================
# TEST INIZIALIZZAZIONE MODALITÀ
# =============================================================================

class TestDensityModeInit:
    
    def test_fill_factor_explicit(self, density_factory):
        """fill_factor esplicito → modalità fill_factor."""
        controller = density_factory({'fill_factor': 3.0})
        
        assert controller.mode == 'fill_factor'
        assert controller.fill_factor == 3.0
        assert controller.density is None
    
    def test_density_explicit(self, density_factory):
        """density esplicita → modalità density."""
        controller = density_factory({'density': 50.0})
        
        assert controller.mode == 'density'
        assert controller.density == 50.0
        assert controller.fill_factor is None
    
    def test_default_fill_factor(self, density_factory):
        """Nessun parametro → default fill_factor=2.0."""
        controller = density_factory({})
        
        assert controller.mode == 'fill_factor'
        assert controller.fill_factor == 2.0
    
    def test_fill_factor_priority(self, density_factory):
        """Se entrambi presenti, fill_factor ha priorità."""
        controller = density_factory({'fill_factor': 4.0, 'density': 100.0})
        
        assert controller.mode == 'fill_factor'
        assert controller.fill_factor == 4.0

    def test_distribution_init(self, density_factory):
        """Test valori default ed espliciti per distribution."""
        c_default = density_factory({})
        c_explicit = density_factory({'distribution': 0.5})
        
        assert c_default.distribution == 0.0
        assert c_explicit.distribution == 0.5


# =============================================================================
# TEST CALCOLO INTER-ONSET SINCRONO
# =============================================================================

class TestSynchronousInterOnset:
    """Test per distribution=0."""
    
    def test_fill_factor_mode_sync(self, density_factory):
        """
        density = fill_factor / grain_dur = 2.0 / 0.1 = 20
        inter_onset = 1 / 20 = 0.05
        """
        controller = density_factory({'fill_factor': 2.0, 'distribution': 0.0})
        
        result = controller.calculate_inter_onset(1.0, 0.1)
        assert result == pytest.approx(0.05, rel=1e-6)
    
    def test_density_mode_sync(self, density_factory):
        """density = 100 → inter_onset = 0.01"""
        controller = density_factory({'density': 100.0, 'distribution': 0.0})
        
        result = controller.calculate_inter_onset(0.0, 0.05)
        assert result == pytest.approx(0.01, rel=1e-6)


# =============================================================================
# TEST CALCOLO INTER-ONSET ASINCRONO
# =============================================================================

class TestAsynchronousInterOnset:
    """Test per distribution=1."""
    
    @patch('density_controller.random.uniform')
    def test_async_calc(self, mock_random, density_factory):
        """
        Async usa random.uniform(0, 2×avg).
        density=100 → avg=0.01 → uniform(0, 0.02)
        """
        mock_random.return_value = 0.015
        controller = density_factory({'density': 100.0, 'distribution': 1.0})
        
        result = controller.calculate_inter_onset(0.0, 0.1)
        
        mock_random.assert_called_once_with(0.0, 0.02)
        assert result == 0.015


# =============================================================================
# TEST INTERPOLAZIONE
# =============================================================================

class TestInterpolation:
    
    @patch('density_controller.random.uniform')
    def test_interpolation_half(self, mock_random, density_factory):
        """
        distribution=0.5.
        Avg=0.01. Sync=0.01. Async=0.016 (mocked).
        Result = 0.5*0.01 + 0.5*0.016 = 0.013
        """
        mock_random.return_value = 0.016
        controller = density_factory({'density': 100.0, 'distribution': 0.5})
        
        result = controller.calculate_inter_onset(0.0, 0.1)
        assert result == pytest.approx(0.013, rel=1e-6)


# =============================================================================
# TEST SAFETY CLAMP
# =============================================================================

class TestSafetyClamp:
    """
    Questi test passano grazie al mock_evaluator 'intelligente' 
    definito in conftest.py che simula il clamping su 'effective_density'.
    """
    
    def test_very_low_density_clamped(self, density_factory):
        """Density < 0.1 viene clampata a 0.1 → inter_onset = 10.0"""
        controller = density_factory({'density': 0.01, 'distribution': 0.0})
        
        result = controller.calculate_inter_onset(0.0, 0.1)
        assert result == pytest.approx(10.0, rel=1e-6)
    
    def test_very_high_density_clamped(self, density_factory):
        """Density > 4000 viene clampata a 4000 → inter_onset = 0.00025"""
        controller = density_factory({'density': 10000.0, 'distribution': 0.0})
        
        result = controller.calculate_inter_onset(0.0, 0.1)
        assert result == pytest.approx(0.00025, rel=1e-6)
    
    def test_zero_grain_duration_handled(self, density_factory):
        """grain_duration=0 viene protetto internamente prima del calcolo."""
        controller = density_factory({'fill_factor': 2.0, 'distribution': 0.0})
        
        # duration 0 diventa 0.001 -> density 2000 -> inter 0.0005
        result = controller.calculate_inter_onset(0.0, 0.0)
        assert result == pytest.approx(0.0005, rel=1e-6)


# =============================================================================
# TEST CON ENVELOPE
# =============================================================================

class TestWithEnvelope:
    
    def test_fill_factor_envelope(self, density_factory):
        """Testa fill_factor dinamico tramite Mock Envelope."""
        # Creiamo un envelope mock specifico
        env = Mock(spec=Envelope)
        env.evaluate.side_effect = lambda t: 1.0 + t # t=0->1, t=5->6
        
        controller = density_factory({'fill_factor': env, 'distribution': 0.0})
        
        # t=0: ff=1, dur=0.1 -> dens=10 -> inter=0.1
        assert controller.calculate_inter_onset(0.0, 0.1) == pytest.approx(0.1)
        
        # t=5: ff=6, dur=0.1 -> dens=60 -> inter=0.01666...
        expected = 0.1 / 6.0
        assert controller.calculate_inter_onset(5.0, 0.1) == pytest.approx(expected)

    def test_distribution_envelope(self, density_factory):
        """Testa distribution dinamico."""
        # 0.0 at t=0, 1.0 at t=10
        env = Mock(spec=Envelope)
        env.evaluate.side_effect = lambda t: t / 10.0
        
        controller = density_factory({'density': 100.0, 'distribution': env})
        
        with patch('density_controller.random.uniform') as mock_rand:
            mock_rand.return_value = 0.015
            
            # t=0 -> dist=0 (sync)
            assert controller.calculate_inter_onset(0.0, 0.1) == pytest.approx(0.01)
            
            # t=10 -> dist=1 (async)
            assert controller.calculate_inter_onset(10.0, 0.1) == 0.015


# =============================================================================
# TEST GETTERS
# =============================================================================

class TestGetterMethods:
    
    def test_getters_density_mode(self, density_factory):
        controller = density_factory({'density': 75.0})
        assert controller.get_density_value(0.0) == 75.0
        assert controller.get_fill_factor_value(0.0) is None
    
    def test_getters_fill_mode(self, density_factory):
        controller = density_factory({'fill_factor': 2.0})
        assert controller.get_density_value(0.0) is None
        assert controller.get_fill_factor_value(0.0) == 2.0