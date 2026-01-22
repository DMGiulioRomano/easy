"""
test_grain_reverse_comprehensive.py

Test completo della logica grain_reverse basato sulla tabella delle possibilità.
Aggiornato per compatibilità con Refactoring Fase 6 (Stream __init__).
"""

import pytest
import random
from unittest.mock import patch
from stream import Stream

# =============================================================================
# PARTE 1: DERIVAZIONE DI BASE_REVERSE
# =============================================================================

class TestBaseReverseDerivation:
    """
    Test derivazione di base_reverse da YAML + pointer_speed.
    """
    
    @pytest.fixture
    def stream_factory(self):
        """Factory per creare stream con parametri custom."""
        def _factory(params):
            # Default params se mancanti
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            if 'time_mode' not in params:
                params['time_mode'] = 'absolute'
            
            # Mockiamo get_sample_duration perché 'test.wav' non esiste e 
            # Stream.__init__ ora prova a leggerlo.
            with patch('stream.get_sample_duration', return_value=1.0):
                # Stream ora accetta SOLO params
                return Stream(params)
        return _factory
    
    def test_case_1_forward_speed_auto_mode(self, stream_factory):
        """CASO 1: Speed positivo + reverse assente → base_reverse = False"""
        stream = stream_factory({
            'stream_id': 'case_1',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {'duration': 0.05},
            # reverse: ASSENTE
            'pointer': {'speed': 1.5}
        })
        
        assert stream.grain_reverse_mode == 'auto'
        assert stream.reverse.value == 0.0 # Parametro raw
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is False
    
    def test_case_2_forward_speed_forced_reverse(self, stream_factory):
        """CASO 2: Speed positivo + reverse: (forzato) → base_reverse = True"""
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
        
        assert stream.grain_reverse_mode is True
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True
    
    def test_case_3_backward_speed_auto_mode(self, stream_factory):
        """CASO 3: Speed negativo + reverse assente → base_reverse = True"""
        stream = stream_factory({
            'stream_id': 'case_3',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {'duration': 0.05},
            'pointer': {'speed': -1.5}
        })
        
        assert stream.grain_reverse_mode == 'auto'
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True
    
    def test_case_4_backward_speed_forced_reverse(self, stream_factory):
        """CASO 4: Speed negativo + reverse: → base_reverse = True"""
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
        
        assert stream.grain_reverse_mode is True
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True
    
    def test_case_5_zero_speed_auto_mode(self, stream_factory):
        """CASO 5: Speed zero + reverse assente → base_reverse = False"""
        stream = stream_factory({
            'stream_id': 'case_5',
            'onset': 0.0,
            'duration': 0.1,
            'sample': 'test.wav',
            'grain': {'duration': 0.05},
            'pointer': {'speed': 0.0}
        })
        
        assert stream.grain_reverse_mode == 'auto'
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is False
    
    def test_case_6_zero_speed_forced_reverse(self, stream_factory):
        """CASO 6: Speed zero + reverse: → base_reverse = True"""
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
        
        assert stream.grain_reverse_mode is True
        base_reverse = stream._calculate_grain_reverse(elapsed_time=0.0)
        assert base_reverse is True


# =============================================================================
# PARTE 2: APPLICAZIONE PROBABILITÀ
# =============================================================================

class TestProbabilisticFlip:
    """
    Test applicazione probabilità su base_reverse.
    """
    
    @pytest.fixture
    def stream_factory(self):
        def _factory(params):
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            if 'time_mode' not in params:
                params['time_mode'] = 'absolute'
            
            with patch('stream.get_sample_duration', return_value=1.0):
                return Stream(params)
        return _factory
    
    # ... I test qui sotto rimangono identici nella logica, cambia solo la factory usata ...

    def test_case_1_false_none(self, stream_factory):
        """CASO 1: base=False, prob=None → gate chiuso → False"""
        stream = stream_factory({
            'stream_id': 'prob_1',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': 1.0}
        })
        stream.generate_grains()
        for grain in stream.grains:
            assert grain.grain_reverse is False
    
    def test_case_2_false_zero(self, stream_factory):
        """CASO 2: base=False, prob=0 → gate chiuso → False"""
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
        for grain in stream.grains:
            assert grain.grain_reverse is False
    
    def test_case_3_false_fifty(self, stream_factory):
        """CASO 3: base=False, prob=50 → 50% flip → circa 50% True"""
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'prob_3',
            'onset': 0.0,
            'duration': 5.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': 1.0},
            'dephase': {'pc_rand_reverse': 50}
        })
        stream.generate_grains()
        true_count = sum(1 for g in stream.grains if g.grain_reverse is True)
        total = len(stream.grains)
        ratio = true_count / total
        assert 0.3 < ratio < 0.7, f"Atteso ~50% True, trovato {ratio*100:.1f}%"
    
    def test_case_4_false_hundred(self, stream_factory):
        """CASO 4: base=False, prob=100 → flip sempre → True"""
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
        for grain in stream.grains:
            assert grain.grain_reverse is True
    
    def test_case_5_true_none(self, stream_factory):
        """CASO 5: base=True, prob=None → gate chiuso → True"""
        stream = stream_factory({
            'stream_id': 'prob_5',
            'onset': 0.0,
            'duration': 0.5,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': -1.0}
        })
        stream.generate_grains()
        for grain in stream.grains:
            assert grain.grain_reverse is True
    
    def test_case_6_true_zero(self, stream_factory):
        """CASO 6: base=True, prob=0 → gate chiuso → True"""
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
        for grain in stream.grains:
            assert grain.grain_reverse is True
    
    def test_case_7_true_fifty(self, stream_factory):
        """CASO 7: base=True, prob=50 → 50% flip → circa 50% False"""
        random.seed(123)
        stream = stream_factory({
            'stream_id': 'prob_7',
            'onset': 0.0,
            'duration': 5.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.1},
            'pointer': {'speed': -1.0},
            'dephase': {'pc_rand_reverse': 50}
        })
        stream.generate_grains()
        false_count = sum(1 for g in stream.grains if g.grain_reverse is False)
        total = len(stream.grains)
        ratio = false_count / total
        assert 0.3 < ratio < 0.7, f"Atteso ~50% False, trovato {ratio*100:.1f}%"
    
    def test_case_8_true_hundred(self, stream_factory):
        """CASO 8: base=True, prob=100 → flip sempre → False"""
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
        for grain in stream.grains:
            assert grain.grain_reverse is False


# =============================================================================
# PARTE 3: VALIDAZIONE SINTASSI YAML
# =============================================================================

class TestYamlValidation:
    """Test che la sintassi YAML ristretta venga rispettata."""
    
    @pytest.fixture
    def stream_factory(self):
        def _factory(params):
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            if 'time_mode' not in params:
                params['time_mode'] = 'absolute'
            
            with patch('stream.get_sample_duration', return_value=1.0):
                return Stream(params)
        return _factory
    
    def test_reject_explicit_true(self, stream_factory):
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': True}
            })
    
    def test_reject_explicit_false(self, stream_factory):
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': False}
            })
    
    def test_reject_string_auto(self, stream_factory):
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': 'auto'}
            })
    
    def test_reject_integer(self, stream_factory):
        with pytest.raises(ValueError, match="grain.reverse deve essere lasciato vuoto"):
            stream_factory({
                'stream_id': 'invalid',
                'onset': 0.0,
                'duration': 0.1,
                'grain': {'reverse': 1}
            })
    
    def test_accept_none(self, stream_factory):
        stream = stream_factory({
            'stream_id': 'valid',
            'onset': 0.0,
            'duration': 0.1,
            'grain': {'reverse': None}
        })
        assert stream.grain_reverse_mode is True
    
    def test_accept_absent(self, stream_factory):
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
    """Test scenari realistici che combinano tutte le feature."""
    
    @pytest.fixture
    def stream_factory(self):
        def _factory(params):
            if 'sample' not in params:
                params['sample'] = 'test.wav'
            if 'time_mode' not in params:
                params['time_mode'] = 'absolute'
            
            with patch('stream.get_sample_duration', return_value=1.0):
                return Stream(params)
        return _factory
    
    def test_auto_mode_with_varying_speed(self, stream_factory):
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
        
        early = [g for g in stream.grains if g.onset < 0.5]
        if early:
            assert all(g.grain_reverse is False for g in early)
        
        late = [g for g in stream.grains if g.onset > 1.5]
        if late:
            assert all(g.grain_reverse is True for g in late)
    
    def test_forced_reverse_with_dynamic_probability(self, stream_factory):
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
            'pointer': {'speed': 1.0},
            'dephase': {
                'pc_rand_reverse': [[0, 0], [4, 100]]
            }
        })
        stream.generate_grains()
        
        early = [g for g in stream.grains if g.onset < 1.0]
        early_true = sum(1 for g in early if g.grain_reverse is True)
        assert early_true / len(early) > 0.8
        
        late = [g for g in stream.grains if g.onset > 3.0]
        late_false = sum(1 for g in late if g.grain_reverse is False)
        assert late_false / len(late) > 0.8