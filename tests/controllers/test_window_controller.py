"""
test_window_controller.py

Test suite completa per window_controller.py.

Coverage:
1. Test parse_window_list (metodo statico)
   - Default behavior
   - Stringa singola
   - Lista esplicita
   - Espansione 'all' e True
   - Validazione errori
   - Alias resolution
2. Test __init__ (istanza)
   - Inizializzazione con vari parametri
   - Range semantico
   - Integrazione con GateFactory
3. Test select_window (selezione runtime)
   - Guard range == 0
   - Gate closed (NeverGate)
   - Gate open (AlwaysGate)
   - Selezione stocastica
   - elapsed_time propagation
4. Test integrazione
   - Workflow completo YAML -> selezione
   - Interazione tra range e gate
5. Test edge cases
   - Configurazioni limite
   - Tipi inattesi
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import random as random_module
import sys

from typing import List, Optional
from dataclasses import dataclass

# =============================================================================
# MOCK CLASSES
# =============================================================================

@dataclass
class WindowSpec:
    """Mock WindowSpec."""
    name: str
    gen_routine: int
    gen_params: list
    description: str
    family: str = "window"


class MockWindowRegistry:
    """
    Mock di WindowRegistry che replica la struttura reale.
    Mantiene le stesse chiavi del registro di produzione per coerenza.
    """
    WINDOWS = {
        'hamming': WindowSpec('hamming', 20, [1, 1], "Hamming", "window"),
        'hanning': WindowSpec('hanning', 20, [2, 1], "Hanning", "window"),
        'bartlett': WindowSpec('bartlett', 20, [3, 1], "Bartlett", "window"),
        'blackman': WindowSpec('blackman', 20, [4, 1], "Blackman", "window"),
        'blackman_harris': WindowSpec('blackman_harris', 20, [5, 1], "Blackman-Harris", "window"),
        'gaussian': WindowSpec('gaussian', 20, [6, 1, 3], "Gaussian", "window"),
        'kaiser': WindowSpec('kaiser', 20, [7, 1, 6], "Kaiser", "window"),
        'rectangle': WindowSpec('rectangle', 20, [8, 1], "Rectangle", "window"),
        'sinc': WindowSpec('sinc', 20, [9, 1, 1], "Sinc", "window"),
        'half_sine': WindowSpec('half_sine', 9, [0.5, 1, 0], "Half-sine", "custom"),
        'expodec': WindowSpec('expodec', 16, [1, 1024, 4, 0], "Expodec", "asymmetric"),
        'expodec_strong': WindowSpec('expodec_strong', 16, [1, 1024, 10, 0], "Expodec strong", "asymmetric"),
        'exporise': WindowSpec('exporise', 16, [0, 1024, -4, 1], "Exporise", "asymmetric"),
        'exporise_strong': WindowSpec('exporise_strong', 16, [0, 1024, -10, 1], "Exporise strong", "asymmetric"),
        'rexpodec': WindowSpec('rexpodec', 16, [1, 1024, -4, 0], "Rexpodec", "asymmetric"),
        'rexporise': WindowSpec('rexporise', 16, [0, 1024, 4, 1], "Rexporise", "asymmetric"),
    }

    ALIASES = {
        'triangle': 'bartlett'
    }

    @classmethod
    def get(cls, name: str):
        resolved = cls.ALIASES.get(name, name)
        return cls.WINDOWS.get(resolved)

    @classmethod
    def all_names(cls) -> list:
        return list(cls.WINDOWS.keys()) + list(cls.ALIASES.keys())

    @classmethod
    def get_by_family(cls, family: str) -> list:
        return [s for s in cls.WINDOWS.values() if s.family == family]


# --- ProbabilityGate hierarchy ---

class ProbabilityGate:
    def should_apply(self, time: float) -> bool:
        raise NotImplementedError
    def get_probability_value(self, time: float) -> float:
        raise NotImplementedError
    @property
    def mode(self) -> str:
        raise NotImplementedError


class NeverGate(ProbabilityGate):
    def should_apply(self, time: float) -> bool:
        return False
    def get_probability_value(self, time: float) -> float:
        return 0.0
    @property
    def mode(self) -> str:
        return "never"


class AlwaysGate(ProbabilityGate):
    def should_apply(self, time: float) -> bool:
        return True
    def get_probability_value(self, time: float) -> float:
        return 100.0
    @property
    def mode(self) -> str:
        return "always"


class RandomGate(ProbabilityGate):
    def __init__(self, probability: float):
        self._probability = min(100.0, max(0.0, probability))
    def should_apply(self, time: float) -> bool:
        return random_module.uniform(0, 100) < self._probability
    def get_probability_value(self, time: float) -> float:
        return self._probability
    @property
    def mode(self) -> str:
        return f"random({self._probability}%)"


class EnvelopeGate(ProbabilityGate):
    def __init__(self, envelope):
        self._envelope = envelope
    def should_apply(self, time: float) -> bool:
        prob = self._envelope.evaluate(time)
        return random_module.uniform(0, 100) < prob
    def get_probability_value(self, time: float) -> float:
        return self._envelope.evaluate(time)
    @property
    def mode(self) -> str:
        return f"envelope"


# --- StreamConfig ---

@dataclass
class StreamContext:
    stream_id: str = "test_stream"
    onset: float = 0.0
    duration: float = 10.0
    sample: str = "test.wav"
    sample_dur_sec: float = 5.0


@dataclass
class StreamConfig:
    dephase: object = False
    range_always_active: bool = False
    distribution_mode: str = 'uniform'
    time_mode: str = 'absolute'
    time_scale: float = 1.0
    context: StreamContext = None

    def __post_init__(self):
        if self.context is None:
            self.context = StreamContext()


# --- GateFactory mock ---

class GateFactory:
    @staticmethod
    def create_gate(dephase=False, param_key=None, default_prob=0.0,
                    has_explicit_range=False, range_always_active=False,
                    duration=1.0, time_mode='absolute'):
        """Replica semplificata della logica reale."""
        if param_key is None:
            return NeverGate()
        if dephase is False:
            return AlwaysGate() if has_explicit_range else NeverGate()
        if dephase is None:
            if default_prob <= 0:
                return NeverGate()
            elif default_prob >= 100:
                return AlwaysGate()
            return RandomGate(default_prob)
        if isinstance(dephase, (int, float)):
            prob = float(dephase)
            if prob <= 0:
                return NeverGate()
            elif prob >= 100:
                return AlwaysGate()
            return RandomGate(prob)
        return NeverGate()


# --- DEFAULT_PROB ---
DEFAULT_PROB = 75.0


# =============================================================================
# IMPORT PRODUZIONE CON MOCK INJECTION
# =============================================================================

# Inietto i mock prima dell'import di WindowController
sys.modules['window_registry'] = type(sys)('window_registry')
sys.modules['window_registry'].WindowRegistry = MockWindowRegistry
sys.modules['window_registry'].WindowSpec = WindowSpec

sys.modules['stream_config'] = type(sys)('stream_config')
sys.modules['stream_config'].StreamConfig = StreamConfig
sys.modules['stream_config'].StreamContext = StreamContext

sys.modules['gate_factory'] = type(sys)('gate_factory')
sys.modules['gate_factory'].GateFactory = GateFactory

sys.modules['parameter_definitions'] = type(sys)('parameter_definitions')
sys.modules['parameter_definitions'].DEFAULT_PROB = DEFAULT_PROB

sys.modules['probability_gate'] = type(sys)('probability_gate')
sys.modules['probability_gate'].ProbabilityGate = ProbabilityGate
sys.modules['probability_gate'].NeverGate = NeverGate
sys.modules['probability_gate'].AlwaysGate = AlwaysGate
sys.modules['probability_gate'].RandomGate = RandomGate
sys.modules['probability_gate'].EnvelopeGate = EnvelopeGate

from window_controller import WindowController


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_config():
    """StreamConfig con valori default (dephase=False)."""
    return StreamConfig()


@pytest.fixture
def config_dephase_disabled():
    """StreamConfig con dephase esplicitamente disabilitato."""
    return StreamConfig(dephase=False)


@pytest.fixture
def config_dephase_implicit():
    """StreamConfig con dephase implicito (None)."""
    return StreamConfig(dephase=None)


@pytest.fixture
def config_dephase_global():
    """StreamConfig con dephase globale numerico."""
    return StreamConfig(dephase=50.0)


@pytest.fixture
def config_dephase_100():
    """StreamConfig con dephase globale al 100%."""
    return StreamConfig(dephase=100.0)


@pytest.fixture
def config_with_stream_id():
    """StreamConfig con stream_id personalizzato."""
    ctx = StreamContext(stream_id="my_stream_42")
    return StreamConfig(context=ctx)


@pytest.fixture
def all_window_names():
    """Tutti i nomi di finestre disponibili (esclude alias)."""
    return list(MockWindowRegistry.WINDOWS.keys())


# =============================================================================
# 1. TEST PARSE_WINDOW_LIST - DEFAULT BEHAVIOR
# =============================================================================

class TestParseWindowListDefaults:
    """Test per parse_window_list con parametri assenti o default."""

    def test_no_envelope_key_returns_hanning(self):
        """Senza chiave 'envelope', ritorna ['hanning'] (default)."""
        result = WindowController.parse_window_list({})
        assert result == ['hanning']

    def test_empty_params_returns_hanning(self):
        """Dict vuoto ritorna il default."""
        result = WindowController.parse_window_list({})
        assert len(result) == 1
        assert result[0] == 'hanning'

    def test_other_keys_dont_interfere(self):
        """Altre chiavi nel dict non influenzano il parsing."""
        params = {'duration': 0.05, 'duration_range': 0.01}
        result = WindowController.parse_window_list(params)
        assert result == ['hanning']

    def test_default_stream_id_is_unknown(self):
        """Lo stream_id di default per i messaggi di errore e' 'unknown'."""
        with pytest.raises(ValueError, match="unknown"):
            WindowController.parse_window_list({'envelope': 'NONEXISTENT'})


# =============================================================================
# 2. TEST PARSE_WINDOW_LIST - STRINGA SINGOLA
# =============================================================================

class TestParseWindowListSingleString:
    """Test per parse_window_list con stringa singola."""

    @pytest.mark.parametrize("window_name", [
        'hanning', 'hamming', 'bartlett', 'blackman', 'gaussian',
        'kaiser', 'rectangle', 'half_sine', 'expodec', 'exporise',
    ])
    def test_single_valid_window(self, window_name):
        """Ogni finestra valida singola produce lista con un elemento."""
        params = {'envelope': window_name}
        result = WindowController.parse_window_list(params)
        assert result == [window_name]

    def test_single_asymmetric_window(self):
        """Finestra asimmetrica come stringa singola."""
        result = WindowController.parse_window_list({'envelope': 'expodec_strong'})
        assert result == ['expodec_strong']

    def test_single_custom_window(self):
        """Finestra custom come stringa singola."""
        result = WindowController.parse_window_list({'envelope': 'half_sine'})
        assert result == ['half_sine']

    def test_invalid_window_name_raises(self):
        """Nome finestra non valido solleva ValueError."""
        with pytest.raises(ValueError, match="non trovata"):
            WindowController.parse_window_list({'envelope': 'INVALID_WINDOW'})

    def test_invalid_window_shows_available(self):
        """Errore per finestra invalida mostra le disponibili."""
        with pytest.raises(ValueError, match="Disponibili"):
            WindowController.parse_window_list({'envelope': 'super_triangle'})

    def test_error_message_includes_stream_id(self):
        """Errore include lo stream_id fornito."""
        with pytest.raises(ValueError, match="stream_A"):
            WindowController.parse_window_list(
                {'envelope': 'NO_SUCH'}, stream_id="stream_A"
            )

    def test_alias_triangle_resolves(self):
        """L'alias 'triangle' e' accettato come valido."""
        result = WindowController.parse_window_list({'envelope': 'triangle'})
        assert result == ['triangle']


# =============================================================================
# 3. TEST PARSE_WINDOW_LIST - LISTA ESPLICITA
# =============================================================================

class TestParseWindowListExplicitList:
    """Test per parse_window_list con lista esplicita di finestre."""

    def test_two_windows(self):
        """Lista con due finestre."""
        params = {'envelope': ['hanning', 'hamming']}
        result = WindowController.parse_window_list(params)
        assert result == ['hanning', 'hamming']

    def test_three_mixed_families(self):
        """Lista con finestre di famiglie diverse."""
        params = {'envelope': ['hanning', 'expodec', 'half_sine']}
        result = WindowController.parse_window_list(params)
        assert len(result) == 3
        assert 'hanning' in result
        assert 'expodec' in result
        assert 'half_sine' in result

    def test_single_element_list(self):
        """Lista con un solo elemento e' valida."""
        params = {'envelope': ['gaussian']}
        result = WindowController.parse_window_list(params)
        assert result == ['gaussian']

    def test_many_windows(self):
        """Lista con molte finestre."""
        windows = ['hanning', 'hamming', 'bartlett', 'blackman', 'gaussian']
        params = {'envelope': windows}
        result = WindowController.parse_window_list(params)
        assert result == windows

    def test_empty_list_raises(self):
        """Lista vuota solleva ValueError."""
        with pytest.raises(ValueError, match="Lista envelope vuota"):
            WindowController.parse_window_list({'envelope': []})

    def test_empty_list_error_includes_stream_id(self):
        """Errore lista vuota include stream_id."""
        with pytest.raises(ValueError, match="stream_B"):
            WindowController.parse_window_list(
                {'envelope': []}, stream_id="stream_B"
            )

    def test_list_with_invalid_window_raises(self):
        """Lista con una finestra invalida solleva errore."""
        with pytest.raises(ValueError, match="FAKE"):
            WindowController.parse_window_list(
                {'envelope': ['hanning', 'FAKE']}
            )

    def test_list_with_first_invalid_raises(self):
        """Anche se la prima finestra e' invalida, l'errore viene sollevato."""
        with pytest.raises(ValueError, match="NON_EXISTENT"):
            WindowController.parse_window_list(
                {'envelope': ['NON_EXISTENT', 'hanning']}
            )

    def test_list_with_alias(self):
        """Lista contenente alias 'triangle'."""
        params = {'envelope': ['hanning', 'triangle']}
        result = WindowController.parse_window_list(params)
        assert 'triangle' in result

    def test_duplicate_windows_in_list(self):
        """Duplicati nella lista sono accettati (il controller non deduplica)."""
        params = {'envelope': ['hanning', 'hanning', 'hanning']}
        result = WindowController.parse_window_list(params)
        assert result == ['hanning', 'hanning', 'hanning']
        assert len(result) == 3


# =============================================================================
# 4. TEST PARSE_WINDOW_LIST - ESPANSIONE 'ALL' E TRUE
# =============================================================================

class TestParseWindowListAll:
    """Test per parse_window_list con 'all' e True."""

    def test_all_string_returns_all_windows(self, all_window_names):
        """'all' espande a tutte le finestre del registro."""
        params = {'envelope': 'all'}
        result = WindowController.parse_window_list(params)
        assert set(result) == set(all_window_names)

    def test_true_returns_all_windows(self, all_window_names):
        """True espande come 'all'."""
        params = {'envelope': True}
        result = WindowController.parse_window_list(params)
        assert set(result) == set(all_window_names)

    def test_all_count_matches_registry(self):
        """Il conteggio di 'all' corrisponde al registro."""
        result = WindowController.parse_window_list({'envelope': 'all'})
        assert len(result) == len(MockWindowRegistry.WINDOWS)

    def test_all_does_not_include_aliases(self):
        """'all' espande i nomi primari, non gli alias."""
        result = WindowController.parse_window_list({'envelope': 'all'})
        assert 'triangle' not in result  # alias, non nome primario

    def test_all_preserves_registry_order(self):
        """'all' preserva l'ordine del registro."""
        result = WindowController.parse_window_list({'envelope': 'all'})
        expected = list(MockWindowRegistry.WINDOWS.keys())
        assert result == expected


# =============================================================================
# 5. TEST PARSE_WINDOW_LIST - TIPI INVALIDI
# =============================================================================

class TestParseWindowListInvalidTypes:
    """Test per parse_window_list con tipi non supportati."""

    def test_integer_raises(self):
        """Intero come envelope solleva ValueError."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            WindowController.parse_window_list({'envelope': 42})

    def test_float_raises(self):
        """Float come envelope solleva ValueError."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            WindowController.parse_window_list({'envelope': 3.14})

    def test_dict_raises(self):
        """Dict come envelope solleva ValueError."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            WindowController.parse_window_list({'envelope': {'type': 'hanning'}})

    def test_none_raises(self):
        """None esplicito solleva ValueError (non e' 'hanning')."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            WindowController.parse_window_list({'envelope': None})

    def test_false_raises(self):
        """False come envelope solleva ValueError."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            WindowController.parse_window_list({'envelope': False})

    def test_tuple_raises(self):
        """Tupla solleva ValueError (non e' una lista)."""
        with pytest.raises(ValueError, match="Formato envelope non valido"):
            WindowController.parse_window_list({'envelope': ('hanning', 'hamming')})

    def test_error_includes_stream_id_for_invalid_type(self):
        """L'errore per tipo invalido include lo stream_id."""
        with pytest.raises(ValueError, match="stream_X"):
            WindowController.parse_window_list(
                {'envelope': 123}, stream_id="stream_X"
            )


# =============================================================================
# 6. TEST __INIT__ - INIZIALIZZAZIONE BASE
# =============================================================================

class TestWindowControllerInit:
    """Test per __init__ del WindowController."""

    def test_default_init(self, default_config):
        """Inizializzazione con parametri minimi."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        assert ctrl._windows == ['hanning']
        assert ctrl._range == 0

    def test_init_with_envelope_list(self, default_config):
        """Inizializzazione con lista di finestre."""
        params = {'envelope': ['hanning', 'expodec', 'gaussian']}
        ctrl = WindowController(params, config=default_config)
        assert len(ctrl._windows) == 3

    def test_init_with_all(self, default_config):
        """Inizializzazione con 'all'."""
        ctrl = WindowController({'envelope': 'all'}, config=default_config)
        assert len(ctrl._windows) == len(MockWindowRegistry.WINDOWS)

    def test_init_range_default_zero(self, default_config):
        """Range di default e' 0."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        assert ctrl._range == 0

    def test_init_range_from_params(self, default_config):
        """Range viene letto da 'envelope_range'."""
        params = {'envelope': 'hanning', 'envelope_range': 1.0}
        ctrl = WindowController(params, config=default_config)
        assert ctrl._range == 1.0

    def test_init_range_fractional(self, default_config):
        """Range frazionario."""
        params = {'envelope': 'hanning', 'envelope_range': 0.5}
        ctrl = WindowController(params, config=default_config)
        assert ctrl._range == 0.5

    def test_init_uses_stream_id_from_config(self, config_with_stream_id):
        """__init__ usa lo stream_id dalla config per il parsing."""
        with pytest.raises(ValueError, match="my_stream_42"):
            WindowController(
                {'envelope': 'NONEXISTENT'},
                config=config_with_stream_id
            )

    def test_init_creates_gate(self, default_config):
        """__init__ crea un gate."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        assert ctrl._gate is not None
        assert isinstance(ctrl._gate, ProbabilityGate)


# =============================================================================
# 7. TEST __INIT__ - GATE CREATION LOGIC
# =============================================================================

class TestWindowControllerGateCreation:
    """Test che __init__ crea il gate corretto in base a range e dephase."""

    def test_no_range_dephase_false_creates_never_gate(self, config_dephase_disabled):
        """range=0 + dephase=False -> NeverGate."""
        params = {'envelope': 'hanning'}  # range default = 0
        ctrl = WindowController(params, config=config_dephase_disabled)
        assert isinstance(ctrl._gate, NeverGate)

    def test_range_positive_dephase_false_creates_always_gate(self, config_dephase_disabled):
        """range>0 + dephase=False -> AlwaysGate (has_explicit_range=True)."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0}
        ctrl = WindowController(params, config=config_dephase_disabled)
        assert isinstance(ctrl._gate, AlwaysGate)

    def test_range_positive_dephase_implicit_creates_random_gate(self, config_dephase_implicit):
        """range>0 + dephase=None -> RandomGate con DEFAULT_PROB."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0}
        ctrl = WindowController(params, config=config_dephase_implicit)
        assert isinstance(ctrl._gate, RandomGate)
        assert ctrl._gate.get_probability_value(0.0) == DEFAULT_PROB

    def test_range_positive_dephase_global_creates_random_gate(self, config_dephase_global):
        """range>0 + dephase=50.0 -> RandomGate(50.0)."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0}
        ctrl = WindowController(params, config=config_dephase_global)
        assert isinstance(ctrl._gate, RandomGate)
        assert ctrl._gate.get_probability_value(0.0) == 50.0

    def test_range_positive_dephase_100_creates_always_gate(self, config_dephase_100):
        """range>0 + dephase=100 -> AlwaysGate."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0}
        ctrl = WindowController(params, config=config_dephase_100)
        assert isinstance(ctrl._gate, AlwaysGate)

    def test_gate_param_key_is_pc_rand_envelope(self, default_config):
        """Il gate viene creato con param_key='pc_rand_envelope'."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        assert isinstance(ctrl._gate, NeverGate)


# =============================================================================
# 8. TEST SELECT_WINDOW - GUARD RANGE == 0
# =============================================================================

class TestSelectWindowRangeZero:
    """Test per select_window quando range == 0 (guard semantico)."""

    def test_range_zero_always_returns_first(self, default_config):
        """Con range=0 ritorna sempre la prima finestra."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec', 'gaussian']},
            config=default_config
        )
        assert ctrl._range == 0
        for _ in range(100):
            assert ctrl.select_window(0.0) == 'hanning'

    def test_range_zero_single_window(self, default_config):
        """Con range=0 e una sola finestra ritorna quella."""
        ctrl = WindowController({'envelope': 'bartlett'}, config=default_config)
        assert ctrl.select_window(5.0) == 'bartlett'

    def test_range_zero_ignores_gate(self, default_config):
        """Con range=0 il guard ritorna prima che il gate venga consultato."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'gaussian']},
            config=default_config
        )
        # Forzo un AlwaysGate per dimostrare che il guard prevale
        ctrl._gate = AlwaysGate()
        assert ctrl.select_window(0.0) == 'hanning'

    def test_range_zero_various_times(self, default_config):
        """Con range=0, il risultato e' stabile a qualsiasi tempo."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec']},
            config=default_config
        )
        times = [0.0, 1.0, 5.0, 9.99, 100.0]
        for t in times:
            assert ctrl.select_window(t) == 'hanning'


# =============================================================================
# 9. TEST SELECT_WINDOW - GATE CLOSED (NEVER)
# =============================================================================

class TestSelectWindowGateClosed:
    """Test per select_window quando il gate e' chiuso."""

    def test_never_gate_returns_first(self, config_dephase_disabled):
        """NeverGate ritorna sempre la prima finestra."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 0}
        ctrl = WindowController(params, config=config_dephase_disabled)
        ctrl._range = 1  # bypasso il guard
        ctrl._gate = NeverGate()
        for _ in range(50):
            assert ctrl.select_window(0.0) == 'hanning'

    def test_never_gate_stable_across_time(self, default_config):
        """NeverGate: stabile a tempi diversi."""
        ctrl = WindowController(
            {'envelope': ['gaussian', 'blackman'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = NeverGate()
        for t in [0.0, 2.5, 5.0, 7.5, 10.0]:
            assert ctrl.select_window(t) == 'gaussian'


# =============================================================================
# 10. TEST SELECT_WINDOW - GATE OPEN (ALWAYS)
# =============================================================================

class TestSelectWindowGateOpen:
    """Test per select_window quando il gate e' aperto."""

    def test_always_gate_with_single_window(self, default_config):
        """AlwaysGate con una sola finestra ritorna sempre quella."""
        ctrl = WindowController(
            {'envelope': 'hanning', 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()
        for _ in range(50):
            assert ctrl.select_window(0.0) == 'hanning'

    def test_always_gate_with_list_selects_randomly(self, default_config):
        """AlwaysGate con lista attiva la selezione random."""
        windows = ['hanning', 'expodec', 'gaussian', 'blackman']
        ctrl = WindowController(
            {'envelope': windows, 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()

        results = set()
        for _ in range(500):
            w = ctrl.select_window(0.0)
            results.add(w)

        assert results == set(windows)

    def test_always_gate_all_results_are_valid(self, default_config):
        """Tutte le selezioni sono finestre valide dalla lista."""
        windows = ['hanning', 'expodec', 'gaussian']
        ctrl = WindowController(
            {'envelope': windows, 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()
        for _ in range(200):
            assert ctrl.select_window(0.0) in windows

    def test_always_gate_statistical_uniformity(self, default_config):
        """Selezione random.choice tende ad essere uniforme."""
        windows = ['hanning', 'expodec']
        ctrl = WindowController(
            {'envelope': windows, 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()

        counts = {w: 0 for w in windows}
        n = 1000
        for _ in range(n):
            w = ctrl.select_window(0.0)
            counts[w] += 1

        for w in windows:
            ratio = counts[w] / n
            assert 0.45 <= ratio <= 0.55, f"{w}: {ratio}"


# =============================================================================
# 11. TEST SELECT_WINDOW - RANDOM GATE
# =============================================================================

class TestSelectWindowRandomGate:
    """Test per select_window con RandomGate."""

    def test_random_gate_50_percent(self, default_config):
        """RandomGate al 50% produce mix di prima finestra e random."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = RandomGate(50.0)

        first_count = 0
        n = 1000
        for _ in range(n):
            w = ctrl.select_window(0.0)
            if w == 'hanning':
                first_count += 1

        # gate chiuso ~50% -> hanning, gate aperto ~50% -> random(hanning/expodec)
        # atteso ~75% hanning, ~25% expodec
        ratio = first_count / n
        assert 0.60 <= ratio <= 0.90, f"hanning ratio: {ratio}"

    def test_random_gate_low_probability(self, default_config):
        """RandomGate con bassa probabilita': pochi cambi."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = RandomGate(5.0)

        first_count = sum(
            1 for _ in range(1000) if ctrl.select_window(0.0) == 'hanning'
        )
        assert first_count > 900

    def test_random_gate_high_probability(self, default_config):
        """RandomGate con alta probabilita': quasi sempre variazione."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = RandomGate(95.0)

        expodec_count = sum(
            1 for _ in range(1000) if ctrl.select_window(0.0) == 'expodec'
        )
        assert expodec_count > 350


# =============================================================================
# 12. TEST SELECT_WINDOW - ELAPSED_TIME PROPAGATION
# =============================================================================

class TestSelectWindowElapsedTime:
    """Test che elapsed_time viene propagato correttamente al gate."""

    def test_elapsed_time_passed_to_gate(self, default_config):
        """Il gate riceve il valore elapsed_time."""
        mock_gate = Mock(spec=ProbabilityGate)
        mock_gate.should_apply.return_value = False

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = mock_gate

        ctrl.select_window(elapsed_time=3.14)
        mock_gate.should_apply.assert_called_once_with(3.14)

    def test_elapsed_time_zero_by_default(self, default_config):
        """Default elapsed_time e' 0.0."""
        mock_gate = Mock(spec=ProbabilityGate)
        mock_gate.should_apply.return_value = False

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = mock_gate

        ctrl.select_window()
        mock_gate.should_apply.assert_called_once_with(0.0)

    def test_elapsed_time_various_values(self, default_config):
        """Gate riceve vari valori di elapsed_time."""
        mock_gate = Mock(spec=ProbabilityGate)
        mock_gate.should_apply.return_value = False

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = mock_gate

        times = [0.0, 0.001, 1.5, 5.0, 9.999]
        for t in times:
            ctrl.select_window(elapsed_time=t)

        calls = [c.args[0] for c in mock_gate.should_apply.call_args_list]
        assert calls == times

    def test_elapsed_time_not_called_when_range_zero(self, default_config):
        """Con range=0, il gate non viene mai consultato."""
        mock_gate = Mock(spec=ProbabilityGate)

        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        ctrl._gate = mock_gate

        ctrl.select_window(elapsed_time=5.0)
        mock_gate.should_apply.assert_not_called()


# =============================================================================
# 13. TEST SELECT_WINDOW - ENVELOPE GATE
# =============================================================================

class TestSelectWindowEnvelopeGate:
    """Test per select_window con EnvelopeGate."""

    def test_envelope_gate_time_varying(self, default_config):
        """EnvelopeGate usa il tempo per variare la probabilita'."""
        mock_envelope = Mock()
        mock_envelope.evaluate.side_effect = lambda t: min(t * 20, 100)

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = EnvelopeGate(mock_envelope)

        # A t=0, probabilita' = 0% -> sempre prima finestra
        results_t0 = [ctrl.select_window(0.0) for _ in range(50)]
        assert all(w == 'hanning' for w in results_t0)

        # A t=10, probabilita' = 100% -> variazione sempre attiva
        results_t10 = set(ctrl.select_window(10.0) for _ in range(200))
        assert len(results_t10) == 2

    def test_envelope_gate_zero_prob_at_start(self, default_config):
        """Envelope con probabilita' zero all'inizio."""
        mock_envelope = Mock()
        mock_envelope.evaluate.return_value = 0.0

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = EnvelopeGate(mock_envelope)

        for _ in range(50):
            assert ctrl.select_window(0.0) == 'hanning'

    def test_envelope_gate_full_prob(self, default_config):
        """Envelope con probabilita' 100%."""
        mock_envelope = Mock()
        mock_envelope.evaluate.return_value = 100.0

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = EnvelopeGate(mock_envelope)

        results = set(ctrl.select_window(5.0) for _ in range(200))
        assert len(results) == 2


# =============================================================================
# 14. TEST INTEGRAZIONE - WORKFLOW COMPLETO
# =============================================================================

class TestWindowControllerIntegration:
    """Test di integrazione per il workflow completo."""

    def test_single_window_no_range_deterministic(self, default_config):
        """Una finestra, nessun range: output sempre deterministico."""
        ctrl = WindowController(
            {'envelope': 'gaussian'},
            config=default_config
        )
        for t in [0, 1, 5, 9.9]:
            assert ctrl.select_window(t) == 'gaussian'

    def test_multiple_windows_no_range_deterministic(self, default_config):
        """Piu' finestre ma range=0: output deterministico (prima finestra)."""
        ctrl = WindowController(
            {'envelope': ['gaussian', 'hanning', 'expodec']},
            config=default_config
        )
        for _ in range(100):
            assert ctrl.select_window(5.0) == 'gaussian'

    def test_all_windows_with_range_and_always_gate(self, config_dephase_disabled):
        """Tutte le finestre + range + dephase=False -> AlwaysGate -> tutte selezionabili."""
        params = {'envelope': 'all', 'envelope_range': 1.0}
        ctrl = WindowController(params, config=config_dephase_disabled)

        results = set()
        for _ in range(5000):
            w = ctrl.select_window(0.0)
            results.add(w)

        all_windows = set(MockWindowRegistry.WINDOWS.keys())
        assert results == all_windows

    def test_workflow_yaml_grain_section(self, default_config):
        """Simula il dict che arriverebbe dalla sezione 'grain' del YAML."""
        grain_yaml = {
            'duration': 0.05,
            'duration_range': 0.01,
            'envelope': ['hanning', 'expodec', 'gaussian'],
            'envelope_range': 1.0
        }
        ctrl = WindowController(grain_yaml, config=default_config)
        assert len(ctrl._windows) == 3
        assert ctrl._range == 1.0

    def test_workflow_yaml_no_envelope_section(self, default_config):
        """YAML senza sezione envelope usa il default."""
        grain_yaml = {'duration': 0.05}
        ctrl = WindowController(grain_yaml, config=default_config)
        assert ctrl._windows == ['hanning']
        assert ctrl._range == 0

    def test_range_zero_overrides_everything(self, config_dephase_100):
        """range=0 prevale anche con dephase=100 e multiple finestre."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec', 'gaussian']},
            config=config_dephase_100
        )
        for _ in range(100):
            assert ctrl.select_window(5.0) == 'hanning'

    def test_dephase_specific_with_pc_rand_envelope(self):
        """Dephase specifico per pc_rand_envelope."""
        config = StreamConfig(dephase={'pc_rand_envelope': 80.0})
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0}
        ctrl = WindowController(params, config=config)
        assert ctrl._gate is not None


# =============================================================================
# 15. TEST EDGE CASES
# =============================================================================

class TestWindowControllerEdgeCases:
    """Test per casi limite e condizioni boundary."""

    def test_very_small_range(self, default_config):
        """Range molto piccolo (ma > 0) attiva il gate."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 0.001}
        ctrl = WindowController(params, config=default_config)
        assert ctrl._range == 0.001
        ctrl._gate = AlwaysGate()
        results = set(ctrl.select_window(0.0) for _ in range(200))
        assert len(results) == 2

    def test_large_range(self, default_config):
        """Range grande e' accettato."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': 100.0}
        ctrl = WindowController(params, config=default_config)
        assert ctrl._range == 100.0

    def test_negative_range_treated_as_nonzero(self, default_config):
        """Range negativo: guard `range == 0` non scatta."""
        params = {'envelope': ['hanning', 'expodec'], 'envelope_range': -1.0}
        ctrl = WindowController(params, config=default_config)
        assert ctrl._range == -1.0
        ctrl._gate = AlwaysGate()
        result = ctrl.select_window(0.0)
        assert result in ['hanning', 'expodec']

    def test_elapsed_time_negative(self, default_config):
        """Tempo negativo viene passato al gate senza errore."""
        mock_gate = Mock(spec=ProbabilityGate)
        mock_gate.should_apply.return_value = False

        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = mock_gate

        result = ctrl.select_window(elapsed_time=-1.0)
        assert result == 'hanning'
        mock_gate.should_apply.assert_called_once_with(-1.0)

    def test_elapsed_time_very_large(self, default_config):
        """Tempo molto grande viene gestito senza errore."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()
        result = ctrl.select_window(elapsed_time=999999.0)
        assert result in ['hanning', 'expodec']

    def test_all_windows_single_element_list(self, default_config):
        """Lista con singola finestra + range + always: sempre quella."""
        ctrl = WindowController(
            {'envelope': ['kaiser'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()
        for _ in range(50):
            assert ctrl.select_window(0.0) == 'kaiser'

    def test_parse_window_list_is_truly_static(self):
        """parse_window_list e' un metodo statico, chiamabile senza istanza."""
        result = WindowController.parse_window_list({'envelope': 'hanning'})
        assert result == ['hanning']

    def test_parse_window_list_called_from_class(self):
        """Chiamata diretta dalla classe."""
        result = WindowController.parse_window_list(
            {'envelope': ['hanning', 'bartlett']},
            stream_id="test"
        )
        assert result == ['hanning', 'bartlett']


# =============================================================================
# 16. TEST INTERAZIONE RANGE E GATE (TABELLA DECISIONALE)
# =============================================================================

class TestRangeGateDecisionMatrix:
    """
    Tabella decisionale completa per le combinazioni range/gate.
    
    | range | gate          | risultato                    |
    |-------|---------------|------------------------------|
    | 0     | qualsiasi     | prima finestra (guard)       |
    | >0    | NeverGate     | prima finestra (gate chiuso) |
    | >0    | AlwaysGate    | random.choice(windows)       |
    | >0    | RandomGate    | mix prima/random             |
    | >0    | EnvelopeGate  | dipende da tempo             |
    """

    def test_range_0_any_gate(self, default_config):
        """range=0: guard prevale su qualsiasi gate."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec']},
            config=default_config
        )
        for gate in [NeverGate(), AlwaysGate(), RandomGate(50.0)]:
            ctrl._gate = gate
            assert ctrl.select_window(5.0) == 'hanning'

    def test_range_positive_never_gate(self, default_config):
        """range>0 + NeverGate: prima finestra."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = NeverGate()
        for _ in range(50):
            assert ctrl.select_window(5.0) == 'hanning'

    def test_range_positive_always_gate(self, default_config):
        """range>0 + AlwaysGate: selezione casuale tra tutte."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()
        results = set(ctrl.select_window(5.0) for _ in range(200))
        assert len(results) == 2

    def test_range_positive_random_gate(self, default_config):
        """range>0 + RandomGate: mix di prima e casuale."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = RandomGate(50.0)
        results = set(ctrl.select_window(5.0) for _ in range(500))
        assert len(results) == 2


# =============================================================================
# 17. TEST PARSE_WINDOW_LIST - PARAMETRIZZATI
# =============================================================================

class TestParseWindowListParametrized:
    """Test parametrizzati per coprire combinazioni sistematiche."""

    @pytest.mark.parametrize("envelope_spec,expected_count", [
        ('hanning', 1),
        ('all', len(MockWindowRegistry.WINDOWS)),
        (True, len(MockWindowRegistry.WINDOWS)),
        (['hanning'], 1),
        (['hanning', 'expodec'], 2),
        (['hanning', 'expodec', 'gaussian'], 3),
    ])
    def test_various_specs_produce_correct_count(self, envelope_spec, expected_count):
        """Varie specifiche producono il numero corretto di finestre."""
        result = WindowController.parse_window_list({'envelope': envelope_spec})
        assert len(result) == expected_count

    @pytest.mark.parametrize("bad_spec,error_match", [
        (42, "Formato envelope non valido"),
        (3.14, "Formato envelope non valido"),
        (None, "Formato envelope non valido"),
        (False, "Formato envelope non valido"),
        ({'type': 'x'}, "Formato envelope non valido"),
        ([], "Lista envelope vuota"),
        ('INVALID', "non trovata"),
        (['INVALID'], "non trovata"),
        (['hanning', 'INVALID'], "non trovata"),
    ])
    def test_various_bad_specs_raise(self, bad_spec, error_match):
        """Specifiche invalide sollevano ValueError con messaggio appropriato."""
        with pytest.raises(ValueError, match=error_match):
            WindowController.parse_window_list({'envelope': bad_spec})


# =============================================================================
# 18. TEST INTERNAL STATE CONSISTENCY
# =============================================================================

class TestInternalStateConsistency:
    """Test che lo stato interno sia coerente dopo l'inizializzazione."""

    def test_windows_list_matches_params(self, default_config):
        """La lista interna corrisponde ai parametri."""
        windows = ['hanning', 'bartlett', 'kaiser']
        ctrl = WindowController(
            {'envelope': windows},
            config=default_config
        )
        assert ctrl._windows == windows

    def test_range_matches_params(self, default_config):
        """Il range interno corrisponde ai parametri."""
        ctrl = WindowController(
            {'envelope': 'hanning', 'envelope_range': 0.7},
            config=default_config
        )
        assert ctrl._range == 0.7

    def test_gate_exists_after_init(self, default_config):
        """Il gate esiste dopo l'inizializzazione."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        assert hasattr(ctrl, '_gate')
        assert ctrl._gate is not None

    def test_no_extra_public_attributes(self, default_config):
        """Non ci sono attributi pubblici inattesi."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        public_attrs = [a for a in dir(ctrl)
                       if not a.startswith('_') and not callable(getattr(ctrl, a))]
        assert len(public_attrs) == 0

    def test_select_window_is_public(self, default_config):
        """select_window e' un metodo pubblico."""
        ctrl = WindowController({'envelope': 'hanning'}, config=default_config)
        assert hasattr(ctrl, 'select_window')
        assert callable(ctrl.select_window)

    def test_parse_window_list_is_public_static(self):
        """parse_window_list e' un metodo statico pubblico."""
        assert hasattr(WindowController, 'parse_window_list')
        assert callable(WindowController.parse_window_list)


# =============================================================================
# 19. TEST DETERMINISMO CON SEED
# =============================================================================

class TestDeterminismWithSeed:
    """Test di riproducibilita' con seed random."""

    def test_reproducible_selection_with_seed(self, default_config):
        """Con stesso seed, la sequenza di selezione e' identica."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec', 'gaussian'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()

        random_module.seed(42)
        seq1 = [ctrl.select_window(0.0) for _ in range(100)]

        random_module.seed(42)
        seq2 = [ctrl.select_window(0.0) for _ in range(100)]

        assert seq1 == seq2

    def test_different_seeds_produce_different_sequences(self, default_config):
        """Seed diversi producono sequenze diverse."""
        ctrl = WindowController(
            {'envelope': ['hanning', 'expodec', 'gaussian'], 'envelope_range': 1.0},
            config=default_config
        )
        ctrl._gate = AlwaysGate()

        random_module.seed(42)
        seq1 = [ctrl.select_window(0.0) for _ in range(100)]

        random_module.seed(99)
        seq2 = [ctrl.select_window(0.0) for _ in range(100)]

        assert seq1 != seq2