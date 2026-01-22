"""
test_pitch_controller.py

Test suite per PitchController dopo il refactoring (Factory + Parameter Objects).
Verifica:
- Selezione corretta della modalità (Ratio vs Semitoni).
- Calcolo corretto dei valori base (Statici ed Envelope).
- Applicazione corretta della stocasticità (Continua vs Quantizzata).
"""

import pytest
import random
import math
from pitch_controller import PitchController

# Helper per calcolare ratio da semitoni
def semitone_to_ratio(st):
    return math.pow(2.0, st / 12.0)

class TestPitchController:
    
    @pytest.fixture
    def create_controller(self):
        """Factory fixture per istanziare il controller."""
        def _create(params, duration=1.0):
            return PitchController(
                params=params,
                stream_id="test_stream",
                duration=duration,
                time_mode="absolute"
            )
        return _create

    # =========================================================================
    # 1. TEST MODALITÀ RATIO (Default)
    # =========================================================================

    def test_ratio_mode_static(self, create_controller):
        """Test modalità ratio con valore statico."""
        # FIX: Impostiamo range=0 per disabilitare il default_jitter (0.02)
        # definito in parameter_definitions.py
        params = {'ratio': 1.5, 'range': 0}
        controller = create_controller(params)
    
        assert controller.mode == 'ratio'
        assert controller.calculate(0.0) == 1.5
        assert controller.calculate(0.5) == 1.5

    def test_ratio_mode_envelope(self, create_controller):
        """Test modalità ratio con envelope lineare."""
        # Envelope: 0s -> 1.0, 1s -> 2.0
        # FIX: range=0 per testare l'interpolazione pura senza rumore
        params = {'ratio': [[0, 1.0], [1, 2.0]], 'range': 0}
        controller = create_controller(params, duration=1.0)
        
        assert controller.mode == 'ratio'
        # A metà tempo (0.5s) deve essere 1.5 esatto
        assert pytest.approx(controller.calculate(0.5), 0.0001) == 1.5

    def test_ratio_mode_randomness_continuous(self, create_controller):
        """
        Test stocasticità in modalità Ratio.
        Deve essere CONTINUA (additive), non quantizzata.
        """
        random.seed(42)
        params = {
            'ratio': 1.0,
            'range': 0.2  # +/- 0.1
        }
        controller = create_controller(params)
        
        results = [controller.calculate(0.0) for _ in range(100)]
        
        # 1. Verifica limiti
        assert min(results) >= 0.9
        assert max(results) <= 1.1
        
        # 2. Verifica continuità:
        # Se fosse quantizzato, avremmo pochi valori unici.
        # Essendo float continui, quasi tutti devono essere diversi.
        unique_values = set(results)
        assert len(unique_values) > 50, "La variazione ratio deve essere continua (molti valori unici)"

    # =========================================================================
    # 2. TEST MODALITÀ SEMITONI
    # =========================================================================

    def test_semitones_mode_static(self, create_controller):
        """Test conversione statica semitoni -> ratio."""
        # 12 semitoni = 1 ottava = ratio 2.0
        params = {'shift_semitones': 12}
        controller = create_controller(params)
        
        assert controller.mode == 'semitones'
        assert pytest.approx(controller.calculate(0.0), 0.001) == 2.0
        
        # -12 semitoni = ratio 0.5
        controller = create_controller({'shift_semitones': -12})
        assert pytest.approx(controller.calculate(0.0), 0.001) == 0.5

    def test_semitones_mode_envelope(self, create_controller):
        """Test envelope sui semitoni."""
        # 0s -> 0st (1.0), 1s -> 12st (2.0)
        params = {'shift_semitones': [[0, 0], [1, 12]]}
        controller = create_controller(params, duration=1.0)
        
        # t=0.5 -> 6 semitoni -> sqrt(2) ~= 1.414
        expected = semitone_to_ratio(6)
        assert pytest.approx(controller.calculate(0.5), 0.01) == expected

    def test_semitones_mode_randomness_quantized(self, create_controller):
        """
        Test stocasticità in modalità Semitoni.
        Deve essere QUANTIZZATA (interi), come definito nel registry.
        """
        random.seed(42)
        params = {
            'shift_semitones': 0,
            'range': 4.0  # +/- 2 semitoni. Possibili: -2, -1, 0, 1, 2
        }
        controller = create_controller(params)
        
        results = [controller.calculate(0.0) for _ in range(100)]
        
        # Calcoliamo i ratio attesi per i semitoni interi
        expected_ratios = {
            semitone_to_ratio(st) for st in [-2, -1, 0, 1, 2]
        }
        
        # Verifica: Ogni risultato generato DEVE appartenere all'insieme dei ratio quantizzati
        for val in results:
            # Usiamo approx per confronto float
            match_found = any(math.isclose(val, exp, rel_tol=1e-5) for exp in expected_ratios)
            assert match_found, f"Valore generato {val} non è un semitono intero valido"
            
        # Verifica che non abbiamo generato valori continui strani
        unique_values = set(round(v, 5) for v in results)
        assert len(unique_values) <= 5, "Ci dovrebbero essere al massimo 5 valori unici (quantizzazione)"

    # =========================================================================
    # 3. TEST PRIORITÀ E COESISTENZA
    # =========================================================================

    def test_semitones_priority(self, create_controller):
        """Se entrambi presenti, shift_semitones deve vincere su ratio."""
        params = {
            'ratio': 500.0,       # Valore assurdo per verifica
            'shift_semitones': 0  # Valore reale (ratio 1.0)
        }
        controller = create_controller(params)
        
        assert controller.mode == 'semitones'
        assert pytest.approx(controller.calculate(0.0), 0.01) == 1.0

    def test_range_absorption(self, create_controller):
        """Verifica che il parametro 'range' venga assorbito correttamente."""
        # Se metto range ma non dephase, il dephase è implicito (1%)
        # Per forzare il test, mettiamo dephase probabilistico al 100%
        params = {
            'ratio': 1.0,
            'range': 0.5,
            'dephase': {'pc_rand_pitch': 100} # Sempre attivo
        }
        controller = create_controller(params)
        
        val = controller.calculate(0.0)
        # Deve essere diverso da 1.0 (a meno di sfortuna estrema del random)
        assert val != 1.0
        assert 0.75 <= val <= 1.25

    def test_properties_exposure(self, create_controller):
        """Verifica che le proprietà per la visualizzazione siano corrette."""
        params = {'shift_semitones': 12, 'range': 2}
        controller = create_controller(params)
        
        # In modalità semitoni
        assert controller.base_semitones == 12
        assert controller.base_ratio is None
        # Range raw esposto
        assert controller.range == 2