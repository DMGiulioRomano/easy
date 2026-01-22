"""
test_grain_reverse_comprehensive.py

Test completo della logica grain_reverse basato sulla tabella delle possibilità.

Struttura:
- PARTE 1: Derivazione di base_reverse (6 casi deterministici)
- PARTE 2: Applicazione probabilità (8 casi con seed random)
- PARTE 3: Validazione sintassi YAML (reject valori espliciti)

La separazione permette di:
- Testare parsing YAML indipendentemente dalla logica probabilistica
- Usare seed random per test deterministici della probabilità
- Identificare facilmente il punto di fallimento
"""

import pytest
import random
from stream import Stream
from parameter_evaluator import ParameterEvaluator


# =============================================================================
# PARTE 1: DERIVAZIONE DI BASE_REVERSE
# =============================================================================

class TestBaseReverseDerivation:
    """
    Test derivazione di base_reverse da YAML + pointer_speed.
    
    Tabella dei 6 casi:
    ┌────┬───────────────┬──────────────────┬────────────────────┬──────────────┐
    │ #  │ pointer_speed │ grain.reverse    │ grain_reverse_mode │ base_reverse │
    ├────┼───────────────┼──────────────────┼────────────────────┼──────────────┤
    │ 1  │ + (avanti)    │ Assente          │ 'auto'             │ 0.0 (False)  │
    │ 2  │ + (avanti)    │ reverse:         │ True               │ 1.0 (True)   │
    │ 3  │ - (indietro)  │ Assente          │ 'auto'             │ 1.0 (True)   │
    │ 4  │ - (indietro)  │ reverse:         │ True               │ 1.0 (True)   │
    │ 5  │ 0 (fermo)     │ Assente          │ 'auto'             │ 0.0 (False)  │
    │ 6  │ 0 (fermo)     │ reverse:         │ True               │ 1.0 (True)   │
    └────┴───────────────┴──────────────────┴────────────────────┴──────────────┘
    """
    
    @pytest.fixture
    def stream_factory(self):
        """Factory per creare stream con parametri custom."""
        def _factory(params):
            # Assicura che ci sia il sample minimo
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            return Stream(params, sample_dur_sec=1.0, time_mode='absolute')
        return _factory
    
    def test_case_1_forward_speed_auto_mode(self, stream_factory):
        """
        CASO 1: Speed positivo + reverse assente → base_reverse = False
        """
        stream = stream_factory({
            'stream_id': 'case_1',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {'duration': 0.05},
            # reverse: ASSENTE
            'pointer': {'speed': 1.5}
        })
        
        # Verifica parsing
        assert stream.grain_reverse_mode == 'auto'
        
        # Verifica base_reverse (senza randomness)
        assert stream.grain_reverse_randomness is None
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is False
    
    def test_case_2_forward_speed_forced_reverse(self, stream_factory):
        """
        CASO 2: Speed positivo + reverse: (forzato) → base_reverse = True
        """
        stream = stream_factory({
            'stream_id': 'case_2',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {
                'duration': 0.05,
                'reverse': None  # Python: chiave presente, valore None
            },
            'pointer': {'speed': 2.0}
        })
        
        # Verifica parsing
        assert stream.grain_reverse_mode is True
        
        # Verifica base_reverse (ignora speed!)
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True
    
    def test_case_3_backward_speed_auto_mode(self, stream_factory):
        """
        CASO 3: Speed negativo + reverse assente → base_reverse = True
        """
        stream = stream_factory({
            'stream_id': 'case_3',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {'duration': 0.05},
            # reverse: ASSENTE
            'pointer': {'speed': -1.5}
        })
        
        # Verifica parsing
        assert stream.grain_reverse_mode == 'auto'
        
        # Verifica base_reverse
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True
    
    def test_case_4_backward_speed_forced_reverse(self, stream_factory):
        """
        CASO 4: Speed negativo + reverse: → base_reverse = True
        """
        stream = stream_factory({
            'stream_id': 'case_4',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {
                'duration': 0.05,
                'reverse': None
            },
            'pointer': {'speed': -2.0}
        })
        
        # Verifica parsing
        assert stream.grain_reverse_mode is True
        
        # Verifica base_reverse
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True
    
    def test_case_5_zero_speed_auto_mode(self, stream_factory):
        """
        CASO 5: Speed zero + reverse assente → base_reverse = False
        """
        stream = stream_factory({
            'stream_id': 'case_5',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {'duration': 0.05},
            'pointer': {'speed': 0.0}
        })
        
        # Verifica parsing
        assert stream.grain_reverse_mode == 'auto'
        
        # Verifica base_reverse
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is False
    
    def test_case_6_zero_speed_forced_reverse(self, stream_factory):
        """
        CASO 6: Speed zero + reverse: → base_reverse = True
        """
        stream = stream_factory({
            'stream_id': 'case_6',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {
                'duration': 0.05,
                'reverse': None
            },
            'pointer': {'speed': 0.0}
        })
        
        # Verifica parsing
        assert stream.grain_reverse_mode is True
        
        # Verifica base_reverse
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True


# =============================================================================
# PARTE 2: APPLICAZIONE PROBABILITÀ
# =============================================================================

class TestProbabilisticFlip:
    """
    Test applicazione probabilità su base_reverse.
    
    Tabella degli 8 casi:
    ┌────┬──────────────┬─────────────────┬──────────┬─────────────┬───────────────┐
    │ #  │ base_reverse │ pc_rand_reverse │ Gate     │ Final value │ grain_reverse │
    ├────┼──────────────┼─────────────────┼──────────┼─────────────┼───────────────┤
    │ 1  │ 0.0 (False)  │ None            │ Chiuso   │ 0.0         │ False         │
    │ 2  │ 0.0 (False)  │ 0               │ Chiuso   │ 0.0         │ False         │
    │ 3  │ 0.0 (False)  │ 50              │ 50%      │ 0.0/1.0     │ 50% True      │
    │ 4  │ 0.0 (False)  │ 100             │ Sempre   │ 1.0         │ True          │
    │ 5  │ 1.0 (True)   │ None            │ Chiuso   │ 1.0         │ True          │
    │ 6  │ 1.0 (True)   │ 0               │ Chiuso   │ 1.0         │ True          │
    │ 7  │ 1.0 (True)   │ 50              │ 50%      │ 0.0/1.0     │ 50% False     │
    │ 8  │ 1.0 (True)   │ 100             │ Sempre   │ 0.0         │ False         │
    └────┴──────────────┴─────────────────┴──────────┴─────────────┴───────────────┘
    """
    
    @pytest.fixture
    def stream_factory(self):
        """Factory per creare stream con parametri custom."""
        def _factory(params):
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            return Stream(params, sample_dur_sec=1.0, time_mode='absolute')
        return _factory
    
    # -------------------------------------------------------------------------
    # CASI CON BASE_REVERSE = FALSE
    # -------------------------------------------------------------------------
    
    def test_case_1_false_none(self, stream_factory):
        """
        CASO 1: base=False, prob=None → gate chiuso → False
        """
        stream = stream_factory({
            'stream_id': 'prob_1',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': 1.0}
            # dephase: ASSENTE → grain_reverse_randomness = None
        })
        
        stream.generate_grains()
        
        # Tutti i grani devono essere False
        for grain in stream.grains:
            assert grain.grain_reverse is False
    
    def test_case_2_false_zero(self, stream_factory):
        """
        CASO 2: base=False, prob=0 → gate chiuso → False
        """
        stream = stream_factory({
            'stream_id': 'prob_2',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': 1.0},
            'dephase': {'pc_rand_reverse': 0}
        })
        
        stream.generate_grains()
        
        # Tutti False
        for grain in stream.grains:
            assert grain.grain_reverse is False
    
    def test_case_3_false_fifty(self, stream_factory):
        """
        CASO 3: base=False, prob=50 → 50% flip → circa 50% True
        """
        random.seed(42)
        
        stream = stream_factory({
            'stream_id': 'prob_3',
            'onset': 0.0,
            'duration': 5.0,  # Molti grani per statistica
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': 1.0},
            'dephase': {'pc_rand_reverse': 50}
        })
        
        stream.generate_grains()
        
        # Conta True
        true_count = sum(1 for g in stream.grains if g.grain_reverse is True)
        total = len(stream.grains)
        ratio = true_count / total
        
        # Deve essere circa 50% (con tolleranza per stocasticità)
        assert 0.3 < ratio < 0.7, \
            f"Atteso ~50% True, trovato {ratio*100:.1f}% ({true_count}/{total})"
    
    def test_case_4_false_hundred(self, stream_factory):
        """
        CASO 4: base=False, prob=100 → flip sempre → True
        """
        stream = stream_factory({
            'stream_id': 'prob_4',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': 1.0},
            'dephase': {'pc_rand_reverse': 100}
        })
        
        stream.generate_grains()
        
        # Tutti True
        for grain in stream.grains:
            assert grain.grain_reverse is True
    
    # -------------------------------------------------------------------------
    # CASI CON BASE_REVERSE = TRUE
    # -------------------------------------------------------------------------
    
    def test_case_5_true_none(self, stream_factory):
        """
        CASO 5: base=True, prob=None → gate chiuso → True
        """
        stream = stream_factory({
            'stream_id': 'prob_5',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': -1.0}  # Speed negativo → base=True
            # dephase: ASSENTE
        })
        
        stream.generate_grains()
        
        # Tutti True
        for grain in stream.grains:
            assert grain.grain_reverse is True
    
    def test_case_6_true_zero(self, stream_factory):
        """
        CASO 6: base=True, prob=0 → gate chiuso → True
        """
        stream = stream_factory({
            'stream_id': 'prob_6',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': -1.0},
            'dephase': {'pc_rand_reverse': 0}
        })
        
        stream.generate_grains()
        
        # Tutti True
        for grain in stream.grains:
            assert grain.grain_reverse is True
    
    def test_case_7_true_fifty(self, stream_factory):
        """
        CASO 7: base=True, prob=50 → 50% flip → circa 50% False
        """
        random.seed(123)
        
        stream = stream_factory({
            'stream_id': 'prob_7',
            'onset': 0.0,
            'duration': 5.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': -1.0},  # base=True
            'dephase': {'pc_rand_reverse': 50}
        })
        
        stream.generate_grains()
        
        # Conta False (flip di True)
        false_count = sum(1 for g in stream.grains if g.grain_reverse is False)
        total = len(stream.grains)
        ratio = false_count / total
        
        # Deve essere circa 50%
        assert 0.3 < ratio < 0.7, \
            f"Atteso ~50% False, trovato {ratio*100:.1f}% ({false_count}/{total})"
    
    def test_case_8_true_hundred(self, stream_factory):
        """
        CASO 8: base=True, prob=100 → flip sempre → False
        """
        stream = stream_factory({
            'stream_id': 'prob_8',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': -1.0},
            'dephase': {'pc_rand_reverse': 100}
        })
        
        stream.generate_grains()
        
        # Tutti False (flip di True)
        for grain in stream.grains:
            assert grain.grain_reverse is False


# =============================================================================
# PARTE 3: VALIDAZIONE SINTASSI YAML
# =============================================================================

class TestYamlValidation:
    """
    Test che la sintassi YAML ristretta venga rispettata.
    
    Accettato:
    - reverse: assente (auto mode)
    - reverse: (chiave vuota, forzato reverse)
    
    Rifiutato:
    - reverse: true
    - reverse: false
    - reverse: 'auto'
    - qualsiasi altro valore
    """
    
    @pytest.fixture
    def stream_factory(self):
        """Factory per creare stream."""
        def _factory(params):
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            return Stream(params, sample_dur_sec=1.0, time_mode='absolute')
        return _factory
    
    def test_reject_explicit_true(self, stream_factory):
        """Deve rifiutare reverse: true"""
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': True}
            })
    
    def test_reject_explicit_false(self, stream_factory):
        """Deve rifiutare reverse: false"""
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': False}
            })
    
    def test_reject_string_auto(self, stream_factory):
        """Deve rifiutare reverse: 'auto'"""
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': 'auto'}
            })
    
    def test_reject_integer(self, stream_factory):
        """Deve rifiutare reverse: 1"""
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': 1}
            })
    
    def test_accept_none(self, stream_factory):
        """Deve accettare reverse: (None)"""
        stream = stream_factory({
            'stream_id': 'valid',
            'onset': 0.0,
            'duration': 0.1,
            'grain': {'reverse': None}
        })
        assert stream.grain_reverse_mode is True
    
    def test_accept_absent(self, stream_factory):
        """Deve accettare chiave assente"""
        stream = stream_factory({
            'stream_id': 'valid',
            'onset': 0.0,
            'duration': 0.1,
            'grain': {'duration': 0.05}
        })
        assert stream.grain_reverse_mode == 'auto'


# =============================================================================
# PARTE 4: TEST INTEGRAZIONE COMPLETA
# =============================================================================

class TestIntegrationScenarios:
    """
    Test scenari realistici che combinano tutte le feature.
    """
    
    @pytest.fixture
    def stream_factory(self):
        """Factory per creare stream."""
        def _factory(params):
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            return Stream(params, sample_dur_sec=1.0, time_mode='absolute')
        return _factory
    
    def test_auto_mode_with_varying_speed(self, stream_factory):
        """
        Auto mode con speed envelope che cambia segno.
        """
        stream = stream_factory({
            'stream_id': 'varying_speed',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.2},
            'pointer': {
                'speed': [[0, 1.0], [1.0, -1.0]]  # +1 → -1
            }
        })
        
        stream.generate_grains()
        
        # Primi grani: False (speed >0)
        early = [g for g in stream.grains if g.onset < 0.5]
        if early:
            assert all(g.grain_reverse is False for g in early)
        
        # Ultimi grani: True (speed <0)
        late = [g for g in stream.grains if g.onset > 1.5]
        if late:
            assert all(g.grain_reverse is True for g in late)
    
    def test_forced_reverse_with_dynamic_probability(self, stream_factory):
        """
        Reverse forzato con probabilità crescente nel tempo.
        """
        random.seed(999)
        
        stream = stream_factory({
            'stream_id': 'dynamic_prob',
            'onset': 0.0,
            'duration': 4.0,
            'sample': 'test.wav',
            'grain': {
                'duration': 0.1,
                'reverse': None  # Forzato True
            },
            'pointer': {'speed': 1.0},  # Ignorato
            'dephase': {
                'pc_rand_reverse': [[0, 0], [4, 100]]  # 0% → 100%
            }
        })
        
        stream.generate_grains()
        
        # Primi grani: tutti True (prob~0, no flip)
        early = [g for g in stream.grains if g.onset < 1.0]
        early_true = sum(1 for g in early if g.grain_reverse is True)
        assert early_true / len(early) > 0.8  # >80% True
        
        # Ultimi grani: tutti False (prob~100, sempre flip)
        late = [g for g in stream.grains if g.onset > 3.0]
        late_false = sum(1 for g in late if g.grain_reverse is False)
        assert late_false / len(late) > 0.8  # >80% False


