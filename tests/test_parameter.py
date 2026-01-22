# tests/test_parameter.py
"""
Test suite per parameter.py (Smart Parameter con Strategy Pattern).

Verifica:
- Costruzione corretta di Parameter
- Strategie di variazione (additive, quantized, invert)
- Probability gate (dephase)
- Safety clamping
- Integrazione con Envelope

Fixtures utilizzate:
- env_linear (da conftest.py)
- deterministic_random (da conftest.py)
"""

import pytest
import random
from unittest.mock import Mock, patch

from parameter import Parameter, ParamInput
from parameter_definitions import ParameterBounds
from envelope import Envelope


# =============================================================================
# FIXTURES LOCALI
# =============================================================================

@pytest.fixture
def bounds_additive():
    """Bounds standard per parametri additivi (es. volume)."""
    return ParameterBounds(
        min_val=-120.0,
        max_val=12.0,
        min_range=0.0,
        max_range=24.0,
        default_jitter=1.5,
        variation_mode='additive'
    )


@pytest.fixture
def bounds_quantized():
    """Bounds per parametri discreti (es. pitch_semitones)."""
    return ParameterBounds(
        min_val=-36.0,
        max_val=36.0,
        min_range=0.0,
        max_range=36.0,
        default_jitter=0.0,
        variation_mode='quantized'
    )


@pytest.fixture
def bounds_invert():
    """Bounds per parametri booleani (es. reverse)."""
    return ParameterBounds(
        min_val=0,
        max_val=1,
        min_range=0,
        max_range=1,
        default_jitter=0,
        variation_mode='invert'
    )


@pytest.fixture
def param_volume(bounds_additive):
    """Parameter volume standard: base=0dB, range=6dB."""
    return Parameter(
        name='volume',
        value=0.0,
        bounds=bounds_additive,
        mod_range=6.0,
        mod_prob=None,  # Sempre attivo
        owner_id='test_stream'
    )


@pytest.fixture
def param_pitch(bounds_quantized):
    """Parameter pitch in semitoni: base=0, range=4 (±2 semitoni)."""
    return Parameter(
        name='pitch_semitones',
        value=0.0,
        bounds=bounds_quantized,
        mod_range=4.0,
        mod_prob=None,
        owner_id='test_stream'
    )


@pytest.fixture
def param_reverse(bounds_invert):
    """Parameter reverse: base=0 (forward), prob=50%."""
    return Parameter(
        name='reverse',
        value=0.0,
        bounds=bounds_invert,
        mod_range=None,  # Ignorato per invert
        mod_prob=50.0,   # 50% probabilità di flip
        owner_id='test_stream'
    )


# =============================================================================
# 1. TEST COSTRUZIONE
# =============================================================================

class TestParameterConstruction:
    """Test inizializzazione di Parameter."""
    
    def test_basic_construction(self, bounds_additive):
        """Costruzione base con valori minimi."""
        param = Parameter(
            name='test',
            value=10.0,
            bounds=bounds_additive
        )
        
        assert param.name == 'test'
        assert param._value == 10.0
        assert param._bounds == bounds_additive
    
    def test_invalid_variation_mode_raises(self):
        """variation_mode sconosciuto deve sollevare ValueError."""
        bad_bounds = ParameterBounds(
            min_val=0.0,
            max_val=100.0,
            variation_mode='unknown_mode'
        )
        
        with pytest.raises(ValueError) as excinfo:
            Parameter(name='bad', value=50.0, bounds=bad_bounds)
        
        assert 'unknown_mode' in str(excinfo.value)
    
    def test_accepts_envelope_as_value(self, bounds_additive):
        """Deve accettare Envelope come valore."""
        env = Envelope([[0, 0], [10, 100]])
        
        param = Parameter(
            name='test',
            value=env,
            bounds=bounds_additive
        )
        
        assert isinstance(param._value, Envelope)
    
    def test_repr(self, param_volume):
        """__repr__ deve essere informativo."""
        repr_str = repr(param_volume)
        
        assert 'volume' in repr_str
        assert 'additive' in repr_str


# =============================================================================
# 2. TEST STRATEGIA ADDITIVE
# =============================================================================

class TestStrategyAdditive:
    """Test variazione continua (additive)."""
    
    def test_no_variation_when_range_zero(self, bounds_additive):
        """Range=0 → nessuna variazione."""
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds_additive,
            mod_range=0.0
        )
        
        # Chiama più volte, deve sempre restituire 0
        for _ in range(10):
            assert param.get_value(0.0) == 0.0
    
    @patch('parameter.random.uniform', return_value=0.5)
    def test_positive_deviation(self, mock_uniform, bounds_additive):
        """Deviazione positiva: base + 0.5 * range."""
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds_additive,
            mod_range=10.0  # range = 10
        )
        
        # uniform(−0.5, 0.5) = 0.5 → deviation = 0.5 * 10 = 5
        result = param.get_value(0.0)
        assert result == 5.0
    
    @patch('parameter.random.uniform', return_value=-0.5)
    def test_negative_deviation(self, mock_uniform, bounds_additive):
        """Deviazione negativa: base - 0.5 * range."""
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds_additive,
            mod_range=10.0
        )
        
        # uniform(−0.5, 0.5) = -0.5 → deviation = -0.5 * 10 = -5
        result = param.get_value(0.0)
        assert result == -5.0
    
    def test_statistical_distribution(self, bounds_additive):
        """Distribuzione statistica: media ≈ base su molti campioni."""
        random.seed(42)
        
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds_additive,
            mod_range=10.0
        )
        
        samples = [param.get_value(0.0) for _ in range(1000)]
        mean = sum(samples) / len(samples)
        
        # La media dovrebbe essere vicina a 0 (base value)
        assert abs(mean) < 1.0  # Tolleranza ragionevole


# =============================================================================
# 3. TEST STRATEGIA QUANTIZED
# =============================================================================

class TestStrategyQuantized:
    """Test variazione discreta (quantized)."""
    
    def test_returns_integers(self, param_pitch):
        """I valori devono essere interi (o base + intero)."""
        random.seed(42)
        
        for _ in range(20):
            result = param_pitch.get_value(0.0)
            # result = base (0) + randint(-2, 2)
            assert result == int(result), f"Non intero: {result}"
    
    @patch('parameter.random.randint', return_value=2)
    def test_positive_step(self, mock_randint, bounds_quantized):
        """Step positivo: base + randint."""
        param = Parameter(
            name='pitch',
            value=0.0,
            bounds=bounds_quantized,
            mod_range=4.0  # limit = int(4 * 0.5) = 2
        )
        
        result = param.get_value(0.0)
        assert result == 2.0
    
    def test_no_variation_when_range_less_than_one(self, bounds_quantized):
        """Range < 1 → nessuna variazione (limit = 0)."""
        param = Parameter(
            name='pitch',
            value=5.0,
            bounds=bounds_quantized,
            mod_range=0.5  # limit = int(0.5 * 0.5) = 0
        )
        
        for _ in range(10):
            assert param.get_value(0.0) == 5.0


# =============================================================================
# 4. TEST STRATEGIA INVERT
# =============================================================================

class TestStrategyInvert:
    """Test flip booleano (invert)."""
    
    @patch('parameter.random.uniform', return_value=25.0)  # < 50, gate aperto
    def test_flip_zero_to_one(self, mock_uniform, param_reverse):
        """0 → 1 quando il gate si apre."""
        result = param_reverse.get_value(0.0)
        assert result == 1.0
    
    @patch('parameter.random.uniform', return_value=25.0)
    def test_flip_one_to_zero(self, mock_uniform, bounds_invert):
        """1 → 0 quando il gate si apre."""
        param = Parameter(
            name='reverse',
            value=1.0,
            bounds=bounds_invert,
            mod_prob=50.0
        )
        
        result = param.get_value(0.0)
        assert result == 0.0
    
    @patch('parameter.random.uniform', return_value=75.0)  # > 50, gate chiuso
    def test_no_flip_when_gate_closed(self, mock_uniform, param_reverse):
        """Nessun flip quando probabilità non scatta."""
        result = param_reverse.get_value(0.0)
        assert result == 0.0  # Rimane il valore base
    
    def test_invert_ignores_range(self, bounds_invert):
        """La strategia invert ignora mod_range."""
        param = Parameter(
            name='reverse',
            value=0.0,
            bounds=bounds_invert,
            mod_range=999.0,  # Dovrebbe essere ignorato
            mod_prob=100.0    # Sempre flip
        )
        
        result = param.get_value(0.0)
        assert result == 1.0  # Flip, non 0 + 999


# =============================================================================
# 5. TEST PROBABILITY GATE
# =============================================================================

class TestProbabilityGate:
    """Test del gate probabilistico (dephase)."""
    
    def test_none_prob_always_active_for_additive(self, bounds_additive):
        """mod_prob=None per additive → variazione SEMPRE applicata."""
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds_additive,
            mod_range=10.0,
            mod_prob=None  # Default: sempre attivo
        )
        
        random.seed(42)
        values = [param.get_value(0.0) for _ in range(10)]
        
        # Almeno alcuni valori dovrebbero essere != 0
        assert any(v != 0.0 for v in values)
    
    def test_none_prob_never_active_for_invert(self, bounds_invert):
        """mod_prob=None per invert → flip MAI applicato."""
        param = Parameter(
            name='reverse',
            value=0.0,
            bounds=bounds_invert,
            mod_range=None,
            mod_prob=None  # Default per invert: mai flip
        )
        
        for _ in range(10):
            assert param.get_value(0.0) == 0.0
    
    def test_zero_prob_never_triggers(self, bounds_additive):
        """mod_prob=0 → variazione MAI applicata."""
        param = Parameter(
            name='test',
            value=10.0,
            bounds=bounds_additive,
            mod_range=100.0,
            mod_prob=0.0
        )
        
        for _ in range(10):
            assert param.get_value(0.0) == 10.0
    
    def test_hundred_prob_always_triggers(self, bounds_additive):
        """mod_prob=100 → variazione SEMPRE applicata."""
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds_additive,
            mod_range=10.0,
            mod_prob=100.0
        )
        
        random.seed(42)
        values = [param.get_value(0.0) for _ in range(10)]
        
        # Tutti i valori dovrebbero essere diversi da 0 (statisticamente)
        assert any(v != 0.0 for v in values)


# =============================================================================
# 6. TEST SAFETY CLAMPING
# =============================================================================

class TestSafetyClamping:
    """Test dei limiti di sicurezza (bounds clipping)."""
    
    def test_clamp_to_min(self, bounds_additive):
        """Valori sotto min_val vengono clippati."""
        param = Parameter(
            name='volume',
            value=-200.0,  # Sotto min_val=-120
            bounds=bounds_additive
        )
        
        result = param.get_value(0.0)
        assert result == -120.0
    
    def test_clamp_to_max(self, bounds_additive):
        """Valori sopra max_val vengono clippati."""
        param = Parameter(
            name='volume',
            value=100.0,  # Sopra max_val=12
            bounds=bounds_additive
        )
        
        result = param.get_value(0.0)
        assert result == 12.0
    
    @patch('parameter.random.uniform', return_value=0.5)
    def test_clamp_after_variation(self, mock_uniform, bounds_additive):
        """Il clipping avviene DOPO la variazione."""
        param = Parameter(
            name='volume',
            value=10.0,  # Vicino a max=12
            bounds=bounds_additive,
            mod_range=10.0  # Deviazione potenziale +5
        )
        
        # 10 + 5 = 15, clippato a 12
        result = param.get_value(0.0)
        assert result == 12.0


# =============================================================================
# 7. TEST ENVELOPE INTEGRATION
# =============================================================================

class TestEnvelopeIntegration:
    """Test con Envelope come valore base."""
    
    def test_envelope_evaluated_at_time(self, bounds_additive):
        """L'Envelope viene valutato al tempo corretto."""
        env = Envelope([[0, 0], [10, 100]])
        
        param = Parameter(
            name='test',
            value=env,
            bounds=bounds_additive,
            mod_range=0.0  # Nessuna variazione
        )
        
        # Nota: i bounds sono -120 to 12, quindi 100 verrà clippato!
        # Usiamo bounds più ampi per questo test
        wide_bounds = ParameterBounds(min_val=-200, max_val=200)
        param_wide = Parameter(name='test', value=env, bounds=wide_bounds, mod_range=0.0)
        
        assert param_wide.get_value(0.0) == 0.0
        assert param_wide.get_value(5.0) == 50.0
        assert param_wide.get_value(10.0) == 100.0
    
    def test_envelope_with_variation(self, bounds_additive):
        """Envelope + variazione funzionano insieme."""
        env = Envelope([[0, 0], [10, 0]])  # Sempre 0
        wide_bounds = ParameterBounds(min_val=-100, max_val=100, max_range=50)
        
        param = Parameter(
            name='test',
            value=env,
            bounds=wide_bounds,
            mod_range=20.0
        )
        
        random.seed(42)
        values = [param.get_value(5.0) for _ in range(10)]
        
        # Base è 0, variazione ±10, quindi valori in [-10, 10]
        assert all(-10 <= v <= 10 for v in values)
    
    def test_envelope_for_mod_range(self, bounds_additive):
        """mod_range può essere un Envelope."""
        range_env = Envelope([[0, 0], [10, 20]])  # Range cresce
        wide_bounds = ParameterBounds(min_val=-100, max_val=100, max_range=50)
        
        param = Parameter(
            name='test',
            value=0.0,
            bounds=wide_bounds,
            mod_range=range_env
        )
        
        random.seed(42)
        
        # A t=0, range=0, nessuna variazione
        values_t0 = [param.get_value(0.0) for _ in range(10)]
        assert all(v == 0.0 for v in values_t0)
        
        # A t=10, range=20, variazione ±10
        values_t10 = [param.get_value(10.0) for _ in range(10)]
        assert any(v != 0.0 for v in values_t10)


# =============================================================================
# 8. TEST DEFAULT JITTER (SCENARIO B)
# =============================================================================

class TestDefaultJitter:
    """Test del jitter implicito quando range=None ma prob definito."""
    
    def test_uses_default_jitter_when_range_none(self):
        """Se mod_range=None e mod_prob definito, usa default_jitter."""
        bounds = ParameterBounds(
            min_val=-100,
            max_val=100,
            default_jitter=5.0,  # Jitter implicito
            variation_mode='additive'
        )
        
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds,
            mod_range=None,
            mod_prob=100.0  # Sempre attivo
        )
        
        random.seed(42)
        values = [param.get_value(0.0) for _ in range(20)]
        
        # Variazione dovrebbe essere ±2.5 (default_jitter/2)
        assert all(-5 <= v <= 5 for v in values)
        assert any(v != 0.0 for v in values)