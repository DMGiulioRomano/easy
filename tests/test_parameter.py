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

# =============================================================================
# 9. TEST RANGE CLAMPING
# =============================================================================

class TestRangeClamping:
    """
    Test che mod_range venga gestito correttamente rispetto a max_range.
    
    Nota: Il comportamento dipende dall'implementazione in Parameter.
    Se Parameter non clampa internamente, questi test documentano
    il comportamento atteso o evidenziano un gap implementativo.
    """
    
    def test_range_within_bounds_unchanged(self):
        """Range entro max_range rimane invariato."""
        bounds = ParameterBounds(
            min_val=0, max_val=100,
            max_range=10.0
        )
        param = Parameter(
            name='test',
            value=50.0,
            bounds=bounds,
            mod_range=5.0  # Entro max_range
        )
        
        assert param._mod_range == 5.0
    
    def test_range_at_max_boundary(self):
        """Range esattamente uguale a max_range è valido."""
        bounds = ParameterBounds(
            min_val=0, max_val=100,
            max_range=10.0
        )
        param = Parameter(
            name='test',
            value=50.0,
            bounds=bounds,
            mod_range=10.0  # Esattamente max_range
        )
        
        assert param._mod_range == 10.0
    
    @patch('parameter.random.uniform', return_value=0.5)
    def test_variation_respects_value_bounds(self, mock_uniform):
        """
        Anche con range alto, il valore finale rispetta min/max_val.
        
        Questo è già coperto da TestSafetyClamping, ma qui verifichiamo
        esplicitamente lo scenario "range grande + valore vicino ai limiti".
        """
        bounds = ParameterBounds(
            min_val=0, max_val=100,
            max_range=1000  # Permettiamo range grandi
        )
        param = Parameter(
            name='test',
            value=95.0,  # Vicino al max
            bounds=bounds,
            mod_range=50.0  # deviation potenziale = 25
        )
        
        # 95 + 25 = 120, ma clampato a 100
        result = param.get_value(0.0)
        assert result == 100.0


# =============================================================================
# 10. TEST ENVELOPE COME MOD_PROB (unitario)
# =============================================================================

class TestEnvelopeAsModProb:
    """
    Test unitari per Envelope come probabilità di modulazione.
    
    Complementa i test di integrazione in test_dephase_scenarios.py
    con verifiche più granulari sul comportamento di Parameter.
    """
    
    def test_envelope_prob_evaluated_at_time(self):
        """L'Envelope prob viene valutato al tempo corretto."""
        bounds = ParameterBounds(min_val=-100, max_val=100)
        prob_env = Envelope([[0, 0], [10, 100]])
        
        param = Parameter(
            name='test',
            value=0.0,
            bounds=bounds,
            mod_range=10.0,
            mod_prob=prob_env
        )
        
        # Verifica che _mod_prob sia l'envelope
        assert isinstance(param._mod_prob, Envelope)
        assert param._mod_prob.evaluate(0.0) == 0.0
        assert param._mod_prob.evaluate(5.0) == 50.0
        assert param._mod_prob.evaluate(10.0) == 100.0
    
    @patch('parameter.random.uniform')
    def test_envelope_prob_zero_no_variation(self, mock_uniform):
        """Con prob=0 (da envelope), nessuna variazione."""
        mock_uniform.return_value = 50.0  # > 0, gate chiuso

        bounds = ParameterBounds(
            min_val=-100, 
            max_val=100,
            max_range=20.0  # ← AGGIUNTO!
        )
        prob_env = Envelope([[0, 0], [10, 0]])  # Sempre 0%

        param = Parameter(
            name='test',
            value=50.0,
            bounds=bounds,
            mod_range=10.0,
            mod_prob=prob_env
        )

        result = param.get_value(5.0)
        assert result == 50.0

    @patch('parameter.random.uniform')
    def test_envelope_prob_hundred_always_varies(self, mock_uniform):
        """Con prob=100 (da envelope), variazione sempre applicata."""
        bounds = ParameterBounds(
            min_val=-100, 
            max_val=100,
            max_range=20.0  # ← AGGIUNTO! Permette range fino a 20
        )
        prob_env = Envelope([[0, 100], [10, 100]])  # Sempre 100%

        param = Parameter(
            name='test',
            value=50.0,
            bounds=bounds,
            mod_range=10.0,
            mod_prob=prob_env
        )

        # Prima chiamata: gate check (uniform(0, 100) → 0.0 < 100, passa)
        # Seconda chiamata: deviation (uniform(-0.5, 0.5) → 0.25)
        mock_uniform.side_effect = [0.0, 0.25]

        result = param.get_value(5.0)
        assert result == 52.5  # 50 + 0.25 * 10 = 52.5

# =============================================================================
# 11. TEST DEFAULT_JITTER CON STRATEGIA QUANTIZED
# =============================================================================

class TestDefaultJitterQuantized:
    """
    Test che default_jitter funzioni correttamente con variation_mode='quantized'.
    
    Per quantized, il jitter dovrebbe produrre step interi.
    """
    
    def test_quantized_uses_default_jitter_as_limit(self):
        """
        Con quantized, default_jitter definisce il limite per randint.
        
        Se default_jitter=4, limit = int(4 * 0.5) = 2, quindi randint(-2, 2).
        """
        bounds = ParameterBounds(
            min_val=-36, max_val=36,
            default_jitter=4.0,  # limit = 2
            variation_mode='quantized'
        )
        
        param = Parameter(
            name='pitch',
            value=0.0,
            bounds=bounds,
            mod_range=None,  # Usa default_jitter
            mod_prob=100.0   # Sempre attivo
        )
        
        random.seed(42)
        values = [param.get_value(0.0) for _ in range(50)]
        
        # Tutti i valori devono essere interi
        assert all(v == int(v) for v in values)
        
        # Tutti i valori devono essere in [-2, 2] (limit da default_jitter)
        assert all(-2 <= v <= 2 for v in values)
    
    def test_quantized_no_jitter_when_default_zero(self):
        """Con default_jitter=0 e mod_range=None, nessuna variazione quantized."""
        bounds = ParameterBounds(
            min_val=-36, max_val=36,
            default_jitter=0.0,  # Nessun jitter
            variation_mode='quantized'
        )
        
        param = Parameter(
            name='pitch',
            value=5.0,
            bounds=bounds,
            mod_range=None,
            mod_prob=100.0
        )
        
        # Senza jitter, sempre il valore base
        for _ in range(10):
            assert param.get_value(0.0) == 5.0
    
    @patch('parameter.random.randint', return_value=1)
    def test_quantized_default_jitter_step_applied(self, mock_randint):
        """Verifica che lo step venga applicato con default_jitter."""
        bounds = ParameterBounds(
            min_val=-36, max_val=36,
            default_jitter=6.0,  # limit = 3
            variation_mode='quantized'
        )
        
        param = Parameter(
            name='pitch',
            value=0.0,
            bounds=bounds,
            mod_range=None,
            mod_prob=100.0
        )
        
        result = param.get_value(0.0)
        assert result == 1.0  # base (0) + randint (1)
        
        # Verifica che randint sia stato chiamato con i limiti corretti
        mock_randint.assert_called_with(-3, 3)


# =============================================================================
# 12. TEST COMBINAZIONI COMPLESSE
# =============================================================================

class TestComplexCombinations:
    """
    Test di scenari complessi con multiple Envelope e interazioni.
    """
    
    def test_triple_envelope_all_dynamic(self):
        """Value, range e prob sono TUTTI Envelope che evolvono."""
        bounds = ParameterBounds(min_val=-100, max_val=100, max_range=50)
        
        value_env = Envelope([[0, 0], [10, 50]])      # 0 → 50
        range_env = Envelope([[0, 0], [10, 20]])      # 0 → 20
        prob_env = Envelope([[0, 100], [10, 100]])    # Sempre 100%
        
        param = Parameter(
            name='test',
            value=value_env,
            bounds=bounds,
            mod_range=range_env,
            mod_prob=prob_env
        )
        
        assert isinstance(param._value, Envelope)
        assert isinstance(param._mod_range, Envelope)
        assert isinstance(param._mod_prob, Envelope)
    
    @patch('parameter.random.uniform', return_value=0.0)
    def test_triple_envelope_evaluation_at_start(self, mock_uniform):
        """A t=0: value=0, range=0 → risultato=0."""
        bounds = ParameterBounds(min_val=-100, max_val=100, max_range=50)
        
        param = Parameter(
            name='test',
            value=Envelope([[0, 0], [10, 50]]),
            bounds=bounds,
            mod_range=Envelope([[0, 0], [10, 20]]),
            mod_prob=Envelope([[0, 100], [10, 100]])
        )
        
        # A t=0: base=0, range=0 → deviation=0
        result = param.get_value(0.0)
        assert result == 0.0
    
    @patch('parameter.random.uniform', return_value=0.5)
    def test_triple_envelope_evaluation_at_end(self, mock_uniform):
        """A t=10: value=50, range=20, deviation=+10 → risultato=60."""
        bounds = ParameterBounds(min_val=-100, max_val=100, max_range=50)
        
        param = Parameter(
            name='test',
            value=Envelope([[0, 0], [10, 50]]),
            bounds=bounds,
            mod_range=Envelope([[0, 0], [10, 20]]),
            mod_prob=100.0  # Semplifichiamo con prob fisso
        )
        
        # A t=10: base=50, range=20, uniform=0.5 → deviation=0.5*20=10
        result = param.get_value(10.0)
        assert result == 60.0
    
    def test_invert_with_envelope_prob(self):
        """
        Strategia invert con probabilità come Envelope.
        
        Scenario: reverse che inizia mai-flippato e finisce sempre-flippato.
        """
        bounds = ParameterBounds(
            min_val=0, max_val=1,
            variation_mode='invert'
        )
        prob_env = Envelope([[0, 0], [10, 100]])  # 0% → 100%
        
        param = Parameter(
            name='reverse',
            value=0.0,  # Forward
            bounds=bounds,
            mod_prob=prob_env
        )
        
        # A t=0, prob=0% → mai flip
        with patch('parameter.random.uniform', return_value=50.0):
            assert param.get_value(0.0) == 0.0  # 50 > 0, no flip
        
        # A t=10, prob=100% → sempre flip
        with patch('parameter.random.uniform', return_value=50.0):
            assert param.get_value(10.0) == 1.0  # 50 < 100, flip!
    
    def test_value_envelope_near_bounds_with_variation(self):
        """
        Envelope che porta il valore vicino ai bounds + variazione.
        
        Verifica che il clamping funzioni correttamente in scenari dinamici.
        """
        bounds = ParameterBounds(min_val=0, max_val=100, max_range=50)
        
        # Envelope che va da 10 a 95 (vicino al max)
        value_env = Envelope([[0, 10], [10, 95]])
        
        param = Parameter(
            name='test',
            value=value_env,
            bounds=bounds,
            mod_range=20.0,  # Potenziale +10
            mod_prob=100.0
        )
        
        with patch('parameter.random.uniform', return_value=0.5):
            # A t=10: base=95, deviation=+10 → 105, clampato a 100
            result = param.get_value(10.0)
            assert result == 100.0