"""
test_density_controller.py

Test suite per DensityController.
Verifica:
- Inizializzazione e scelta strategia (Fill Factor vs Density).
- Calcolo Inter-Onset Time (IOT) in modalità Sincrona e Asincrona (Truax).
- Safety Clamping (limiti fisici di densità).
- Integrazione con ParameterFactory (jitter sui valori di ingresso).
"""

import pytest
import random
from density_controller import DensityController

class TestDensityController:
    
    @pytest.fixture
    def create_controller(self):
        """Factory fixture per istanziare il controller."""
        def _create(params, duration=1.0):
            # Assicura un default per evitare errori se mancano chiavi opzionali
            if 'fill_factor' not in params and 'density' not in params:
                pass # Usa logica default del controller
            
            return DensityController(
                params=params,
                stream_id="test_stream",
                duration=duration,
                time_mode="absolute"
            )
        return _create

    # =========================================================================
    # 1. TEST MODALITÀ E PRIORITÀ
    # =========================================================================

    def test_mode_density_explicit(self, create_controller):
        """Se c'è solo 'density', usa modalità density."""
        # FIX: density_range=0 per disabilitare jitter implicito (50.0 default)
        params = {'density': 10, 'density_range': 0}
        ctrl = create_controller(params)
        
        assert ctrl.mode == 'density'
        assert ctrl.get_density_value(0.0) == 10.0
        assert ctrl.get_fill_factor_value(0.0) is None

    def test_mode_fill_factor_explicit(self, create_controller):
        """Se c'è 'fill_factor', usa modalità fill_factor."""
        # FIX: fill_factor_range=0 per sicurezza (anche se default è 0)
        params = {'fill_factor': 2.5, 'fill_factor_range': 0}
        ctrl = create_controller(params)
        
        assert ctrl.mode == 'fill_factor'
        assert ctrl.get_fill_factor_value(0.0) == 2.5
        assert ctrl.get_density_value(0.0) is None

    def test_mode_priority(self, create_controller):
        """Se ci sono entrambi, 'fill_factor' vince su 'density'."""
        params = {
            'fill_factor': 4.0, 'fill_factor_range': 0,
            'density': 100.0, 'density_range': 0
        }
        ctrl = create_controller(params)
        
        assert ctrl.mode == 'fill_factor'
        # Il valore usato deve essere quello di fill_factor
        assert ctrl.get_fill_factor_value(0.0) == 4.0

    def test_mode_default(self, create_controller):
        """Se non c'è nulla, usa default (Fill Factor 2.0)."""
        params = {}
        ctrl = create_controller(params)
        
        # Default interno crea un parametro FillFactor=2.0
        # Poiché è creato internamente senza range, dovrebbe essere stabile
        assert ctrl.mode == 'fill_factor'
        
        # Nota: Qui potrebbe esserci jitter se lo schema default lo prevede.
        # Controlliamo approssimativamente o disabilitiamo range se possibile.
        # Il default factory crea fill_factor=2.0.
        val = ctrl.get_fill_factor_value(0.0)
        assert val is not None
        # Accettiamo piccola variazione se c'è jitter default su fill_factor (ma di solito è 0)
        assert pytest.approx(val, abs=0.1) == 2.0

    # =========================================================================
    # 2. TEST CALCOLO SINCRONO (Distribution = 0)
    # =========================================================================

    def test_calc_density_sync(self, create_controller):
        """
        Test calcolo IOT con Density fissa e Distribution 0 (Sync).
        Formula: IOT = 1 / Density
        """
        # FIX: density_range=0
        params = {'density': 10.0, 'density_range': 0, 'distribution': 0.0}
        ctrl = create_controller(params)
        
        # Density 10 -> IOT 0.1s
        iot = ctrl.calculate_inter_onset(elapsed_time=0.0, current_grain_duration=0.5)
        assert pytest.approx(iot) == 0.1

    def test_calc_fill_factor_sync(self, create_controller):
        """
        Test calcolo IOT con Fill Factor fisso.
        Formula: Density = FF / GrainDur -> IOT = 1 / Density = GrainDur / FF
        """
        # FIX: fill_factor_range=0
        params = {'fill_factor': 2.0, 'fill_factor_range': 0, 'distribution': 0.0}
        ctrl = create_controller(params)
        
        # Grain 0.1s, FF 2.0 -> Density 20 -> IOT 0.05s
        iot = ctrl.calculate_inter_onset(elapsed_time=0.0, current_grain_duration=0.1)
        assert pytest.approx(iot) == 0.05
        
        # Grain 0.5s, FF 2.0 -> Density 4 -> IOT 0.25s
        iot = ctrl.calculate_inter_onset(elapsed_time=0.0, current_grain_duration=0.5)
        assert pytest.approx(iot) == 0.25

    def test_calc_fill_factor_zero_division_protection(self, create_controller):
        """Test protezione divisione per zero se grain_duration è piccolissimo."""
        params = {'fill_factor': 1.0, 'fill_factor_range': 0}
        ctrl = create_controller(params)
        
        # Grain 0.0 -> SafeDur 0.0001 -> Density 10000 -> Clamped 4000 -> IOT 0.00025
        iot = ctrl.calculate_inter_onset(elapsed_time=0.0, current_grain_duration=0.0)
        assert iot > 0
        assert pytest.approx(iot, rel=1e-3) == 0.00025

    # =========================================================================
    # 3. TEST CALCOLO ASINCRONO (Distribution > 0)
    # =========================================================================

    def test_calc_async_truax_model(self, create_controller):
        """
        Test modello asincrono (Distribution 1.0).
        L'IOT deve variare casualmente tra 0 e 2*AvgIOT.
        """
        random.seed(42)
        # FIX: density_range=0 per isolare la casualità della distribuzione
        params = {'density': 10.0, 'density_range': 0, 'distribution': 1.0} # Avg IOT = 0.1
        ctrl = create_controller(params)
        
        results = []
        for _ in range(100):
            results.append(ctrl.calculate_inter_onset(0.0, 0.1))
            
        # Verifica limiti Truax: 0 < IOT < 2 * Avg (0.2)
        assert min(results) >= 0.0
        assert max(results) <= 0.2
        
        # Verifica che ci sia variazione (non sincrono)
        assert len(set(results)) > 50

    def test_calc_interpolated(self, create_controller):
        """Test interpolazione (Distribution 0.5)."""
        random.seed(42)
        # FIX: density_range=0
        params = {'density': 10.0, 'density_range': 0, 'distribution': 0.5} # Avg = 0.1
        ctrl = create_controller(params)
        
        # Sync = 0.1
        # Async = [0, 0.2]
        # Result = 0.5 * 0.1 + 0.5 * Async -> Range [0.05, 0.15]
        
        results = [ctrl.calculate_inter_onset(0.0, 0.1) for _ in range(50)]
        
        assert min(results) >= 0.05
        assert max(results) <= 0.15

    # =========================================================================
    # 4. SAFETY CLAMPING
    # =========================================================================

    def test_safety_clamp_max_density(self, create_controller):
        """Verifica che la densità non superi 4000 Hz."""
        # FIX: density_range=0
        params = {'density': 10000.0, 'density_range': 0, 'distribution': 0.0}
        ctrl = create_controller(params)
        
        # Density 10000 -> Clamped 4000 -> IOT 0.00025
        iot = ctrl.calculate_inter_onset(0.0, 0.1)
        assert pytest.approx(iot) == 0.00025

    def test_safety_clamp_min_density(self, create_controller):
        """Verifica che la densità non scenda sotto 0.1 Hz."""
        # FIX: density_range=0
        params = {'density': 0.0001, 'density_range': 0, 'distribution': 0.0}
        ctrl = create_controller(params)
        
        # Density 0.0001 -> Clamped 0.1 -> IOT 10.0
        iot = ctrl.calculate_inter_onset(0.0, 0.1)
        assert pytest.approx(iot) == 10.0

    # =========================================================================
    # 5. INTEGRAZIONE PARAMETER (Jitter)
    # =========================================================================

    def test_parameter_jitter_integration(self, create_controller):
        """
        Verifica che 'density_range' nel YAML attivi il jitter nel Parameter,
        facendo variare l'IOT anche se distribution=0 (sincrono).
        """
        random.seed(999)
        # Qui VOGLIAMO il range!
        params = {
            'density': 10.0,
            'density_range': 5.0,  # Jitter +/- 2.5 su density (Range 7.5 - 12.5)
            'distribution': 0.0    # Sincrono rispetto alla densità calcolata
        }
        ctrl = create_controller(params)
        
        results = [ctrl.calculate_inter_onset(0.0, 0.1) for _ in range(20)]
        
        # Devono essere diversi tra loro
        assert len(set(results)) > 10
        
        # Verifica range approssimativo:
        # Min Density ~7.5 -> Max IOT ~0.133
        # Max Density ~12.5 -> Min IOT ~0.08
        assert 0.07 < min(results) 
        assert max(results) < 0.14