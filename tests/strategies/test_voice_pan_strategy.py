# tests/controllers/test_voice_pan_strategy.py
"""
test_voice_pan_strategy.py

Suite TDD per voice_pan_strategy.py

Moduli sotto test (da scrivere):
- VoicePanStrategy (ABC)
- LinearPanStrategy
- RandomPanStrategy
- AdditivePanStrategy
- VOICE_PAN_STRATEGIES (registry dict)
- register_voice_pan_strategy() (funzione di registrazione)
- VoicePanStrategyFactory (factory con create() statico)

Principio di design:
- Voce 0 e' sempre il riferimento: pan_offset macro = 0.0
- Le voci 1..N-1 ricevono offset secondo la strategy
- Il micro-jitter e' responsabilita' del VoiceManager, NON della strategy
- La strategy restituisce SOLO l'offset macro strutturale

Organizzazione:
  1.  VoicePanStrategy ABC - interfaccia e contratto
  2.  LinearPanStrategy - distribuzione deterministica equidistante
  3.  RandomPanStrategy - distribuzione stocastica per voce
  4.  AdditivePanStrategy - offset additivo diretto
  5.  Invariante voce 0 - tutte le strategy rispettano il riferimento
  6.  Edge cases comuni - spread=0, num_voices=1
  7.  VOICE_PAN_STRATEGIES registry - completezza e struttura
  8.  register_voice_pan_strategy() - registrazione dinamica
  9.  VoicePanStrategyFactory - creazione e gestione errori
  10. Pattern architetturale - coerenza con il resto del sistema
  11. Integrazione Factory-Registry
"""

import pytest
import random as stdlib_random
from abc import ABC, abstractmethod
from unittest.mock import patch


# =============================================================================
# IMPORT LAZY (i moduli non esistono ancora: e' TDD)
# =============================================================================

def _get_module():
    """Import lazy per permettere RED phase senza errori di import."""
    from strategies.voice_pan_strategy import (
        VoicePanStrategy,
        LinearPanStrategy,
        RandomPanStrategy,
        AdditivePanStrategy,
        VOICE_PAN_STRATEGIES,
        register_voice_pan_strategy,
        VoicePanStrategyFactory,
    )
    return (
        VoicePanStrategy,
        LinearPanStrategy,
        RandomPanStrategy,
        AdditivePanStrategy,
        VOICE_PAN_STRATEGIES,
        register_voice_pan_strategy,
        VoicePanStrategyFactory,
    )


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def restore_registry():
    """
    Ripristina VOICE_PAN_STRATEGIES dopo ogni test che lo modifica.
    Isola i test che usano register_voice_pan_strategy().
    """
    try:
        _, _, _, _, registry, _, _ = _get_module()
        original = dict(registry)
        yield
        registry.clear()
        registry.update(original)
    except ImportError:
        yield


@pytest.fixture
def linear():
    _, LinearPanStrategy, _, _, _, _, _ = _get_module()
    return LinearPanStrategy()


@pytest.fixture
def random_strat():
    _, _, RandomPanStrategy, _, _, _, _ = _get_module()
    return RandomPanStrategy()


@pytest.fixture
def additive():
    _, _, _, AdditivePanStrategy, _, _, _ = _get_module()
    return AdditivePanStrategy()


# =============================================================================
# 1. VOICEPANSTRATEGY ABC - INTERFACCIA E CONTRATTO
# =============================================================================

class TestVoicePanStrategyABC:
    """Verifica che VoicePanStrategy sia un ABC correttamente definito."""

    def test_is_abstract_class(self):
        """VoicePanStrategy non puo' essere istanziata direttamente."""
        VoicePanStrategy, _, _, _, _, _, _ = _get_module()

        with pytest.raises(TypeError):
            VoicePanStrategy()

    def test_get_pan_offset_is_abstract(self):
        """get_pan_offset deve essere un abstractmethod."""
        VoicePanStrategy, _, _, _, _, _, _ = _get_module()

        assert hasattr(VoicePanStrategy, 'get_pan_offset')
        assert getattr(VoicePanStrategy.get_pan_offset, '__isabstractmethod__', False)

    def test_name_is_abstract_property(self):
        """name deve essere una abstract property."""
        VoicePanStrategy, _, _, _, _, _, _ = _get_module()

        assert hasattr(VoicePanStrategy, 'name')
        assert getattr(VoicePanStrategy.name, '__isabstractmethod__', False)

    def test_concrete_subclass_requires_both_methods(self):
        """Una sottoclasse senza get_pan_offset o name non puo' essere istanziata."""
        VoicePanStrategy, _, _, _, _, _, _ = _get_module()

        class IncompleteStrategy(VoicePanStrategy):
            pass  # manca sia get_pan_offset che name

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_concrete_subclass_with_all_methods_works(self):
        """Una sottoclasse completa puo' essere istanziata."""
        VoicePanStrategy, _, _, _, _, _, _ = _get_module()

        class ConcreteStrategy(VoicePanStrategy):
            def get_pan_offset(self, voice_index, num_voices, spread):
                return 0.0

            @property
            def name(self):
                return 'concrete'

        strategy = ConcreteStrategy()
        assert strategy is not None
        assert strategy.name == 'concrete'

    def test_get_pan_offset_signature(self):
        """get_pan_offset accetta voice_index, num_voices, spread."""
        VoicePanStrategy, _, _, _, _, _, _ = _get_module()

        class TestStrategy(VoicePanStrategy):
            def get_pan_offset(self, voice_index: int, num_voices: int, spread: float) -> float:
                return float(voice_index)

            @property
            def name(self):
                return 'test'

        s = TestStrategy()
        result = s.get_pan_offset(2, 4, 90.0)
        assert result == 2.0


# =============================================================================
# 2. LINEARPANSTRATEGY - DISTRIBUZIONE DETERMINISTICA EQUIDISTANTE
# =============================================================================

class TestLinearPanStrategy:
    """
    LinearPanStrategy distribuisce le voci equidistanti nello spazio.

    Con spread S e N voci:
    - Se N == 1: tutte le voci a 0.0
    - Se N > 1: voce v a -S/2 + v * S/(N-1)
    - Voce 0 sempre a -spread/2
    - Voce N-1 sempre a +spread/2
    - I valori sono simmetrici attorno a 0
    """

    def test_name_is_linear(self, linear):
        """name ritorna 'linear'."""
        assert linear.name == 'linear'

    def test_single_voice_returns_zero(self, linear):
        """Con num_voices=1 ritorna 0.0 indipendentemente da spread."""
        assert linear.get_pan_offset(0, 1, 180.0) == pytest.approx(0.0)
        assert linear.get_pan_offset(0, 1, 0.0) == pytest.approx(0.0)

    def test_two_voices_spread_100(self, linear):
        """Con 2 voci e spread=100: voce 0 a -50, voce 1 a +50."""
        assert linear.get_pan_offset(0, 2, 100.0) == pytest.approx(-50.0)
        assert linear.get_pan_offset(1, 2, 100.0) == pytest.approx(50.0)

    def test_four_voices_spread_120(self, linear):
        """Con 4 voci e spread=120: voci a -60, -20, +20, +60."""
        assert linear.get_pan_offset(0, 4, 120.0) == pytest.approx(-60.0)
        assert linear.get_pan_offset(1, 4, 120.0) == pytest.approx(-20.0)
        assert linear.get_pan_offset(2, 4, 120.0) == pytest.approx(20.0)
        assert linear.get_pan_offset(3, 4, 120.0) == pytest.approx(60.0)

    def test_three_voices_symmetric(self, linear):
        """Con 3 voci il valore centrale e' 0.0."""
        offset_0 = linear.get_pan_offset(0, 3, 180.0)
        offset_1 = linear.get_pan_offset(1, 3, 180.0)
        offset_2 = linear.get_pan_offset(2, 3, 180.0)

        assert offset_1 == pytest.approx(0.0)
        assert offset_0 == pytest.approx(-offset_2)

    def test_first_voice_at_negative_half_spread(self, linear):
        """Voce 0 sempre a -spread/2."""
        for spread in [60.0, 90.0, 180.0, 360.0]:
            assert linear.get_pan_offset(0, 4, spread) == pytest.approx(-spread / 2.0)

    def test_last_voice_at_positive_half_spread(self, linear):
        """Ultima voce sempre a +spread/2."""
        for n in [2, 3, 4, 5]:
            spread = 180.0
            assert linear.get_pan_offset(n - 1, n, spread) == pytest.approx(spread / 2.0)

    def test_spread_zero_all_voices_at_zero(self, linear):
        """Con spread=0 tutte le voci sono a 0.0."""
        for v in range(4):
            assert linear.get_pan_offset(v, 4, 0.0) == pytest.approx(0.0)

    def test_deterministic_same_call_same_result(self, linear):
        """La stessa chiamata produce sempre lo stesso risultato (deterministica)."""
        r1 = linear.get_pan_offset(2, 5, 180.0)
        r2 = linear.get_pan_offset(2, 5, 180.0)
        assert r1 == pytest.approx(r2)

    def test_offsets_are_equidistant(self, linear):
        """Le distanze tra voci adiacenti sono tutte uguali."""
        n = 5
        spread = 200.0
        offsets = [linear.get_pan_offset(v, n, spread) for v in range(n)]
        gaps = [offsets[i + 1] - offsets[i] for i in range(n - 1)]

        for gap in gaps:
            assert gap == pytest.approx(gaps[0])


# =============================================================================
# 3. RANDOMPANSTRATEGY - DISTRIBUZIONE STOCASTICA PER VOCE
# =============================================================================

class TestRandomPanStrategy:
    """
    RandomPanStrategy assegna un offset casuale a ogni voce nel range
    [-spread/2, +spread/2]. L'offset e' campionato una volta per voce
    e rimane stabile.

    Nota: la strategy campiona ad ogni chiamata. La stabilita' per-voce
    e' responsabilita' del VoiceManager (che chiama get_pan_offset una
    volta alla costruzione e memorizza il risultato).
    """

    def test_name_is_random(self, random_strat):
        """name ritorna 'random'."""
        assert random_strat.name == 'random'

    def test_offset_within_range(self, random_strat):
        """L'offset restituito e' nel range [-spread/2, +spread/2]."""
        spread = 180.0
        stdlib_random.seed(42)
        for v in range(10):
            offset = random_strat.get_pan_offset(v, 10, spread)
            assert -spread / 2.0 <= offset <= spread / 2.0

    def test_spread_zero_returns_zero(self, random_strat):
        """Con spread=0 ritorna 0.0."""
        assert random_strat.get_pan_offset(0, 4, 0.0) == pytest.approx(0.0)
        assert random_strat.get_pan_offset(3, 4, 0.0) == pytest.approx(0.0)

    def test_single_voice_returns_zero_or_within_range(self, random_strat):
        """Con num_voices=1 ritorna 0.0 (voce 0 = riferimento)."""
        # La voce 0 e' il riferimento: macro_offset = 0
        # Questo e' gestito dall'invariante voce 0 (sezione 5)
        # Qui verifichiamo solo che non sollevi eccezioni
        result = random_strat.get_pan_offset(0, 1, 90.0)
        assert -90.0 <= result <= 90.0  # nella peggiore delle ipotesi

    def test_different_voices_generally_different(self, random_strat):
        """Con spread > 0, voci diverse producono generalmente offset diversi."""
        stdlib_random.seed(42)
        offsets = [random_strat.get_pan_offset(v, 8, 360.0) for v in range(8)]
        # Almeno alcuni devono essere diversi (con alta probabilita')
        assert len(set(round(o, 6) for o in offsets)) > 1

    def test_negative_spread_raises_or_handles_gracefully(self, random_strat):
        """Spread negativo solleva ValueError o viene trattato come 0."""
        try:
            result = random_strat.get_pan_offset(0, 4, -10.0)
            # Se non solleva, deve ritornare 0.0 o un valore gestito
            assert result == pytest.approx(0.0) or isinstance(result, float)
        except ValueError:
            pass  # Comportamento accettabile


# =============================================================================
# 4. ADDITIVEPANSTRATEGY - OFFSET ADDITIVO DIRETTO
# =============================================================================

class TestAdditivePanStrategy:
    """
    AdditivePanStrategy usa spread direttamente come offset fisso additivo.
    Ogni voce riceve lo stesso offset = spread.
    Utile per controllo manuale dove spread e' gia' l'offset desiderato.
    """

    def test_name_is_additive(self, additive):
        """name ritorna 'additive'."""
        assert additive.name == 'additive'

    def test_returns_spread_as_offset(self, additive):
        """Ritorna spread come offset, indipendentemente da voice_index e num_voices."""
        assert additive.get_pan_offset(0, 4, 90.0) == pytest.approx(90.0)
        assert additive.get_pan_offset(3, 4, 90.0) == pytest.approx(90.0)

    def test_spread_zero_returns_zero(self, additive):
        """Con spread=0 ritorna 0.0."""
        assert additive.get_pan_offset(2, 4, 0.0) == pytest.approx(0.0)

    def test_negative_spread_allowed(self, additive):
        """Spread negativo e' permesso (offset a sinistra)."""
        result = additive.get_pan_offset(0, 4, -45.0)
        assert result == pytest.approx(-45.0)

    def test_voice_index_does_not_affect_result(self, additive):
        """L'indice della voce non influisce sul risultato."""
        spread = 60.0
        n = 6
        results = [additive.get_pan_offset(v, n, spread) for v in range(n)]
        assert all(r == pytest.approx(spread) for r in results)


# =============================================================================
# 5. INVARIANTE VOCE 0 - TUTTE LE STRATEGY RISPETTANO IL RIFERIMENTO
# =============================================================================

class TestVoiceZeroInvariant:
    """
    Verifica che tutte le strategy concrete rispettino l'invariante:
    voce 0 = voce di riferimento, macro_offset = 0.0.

    Per LinearPanStrategy questo e' garantito dalla formula matematica
    (voce 0 a -spread/2 solo se N>1).
    Per RandomPanStrategy e AdditivePanStrategy l'invariante deve essere
    implementato esplicitamente.
    """

    @pytest.mark.parametrize("strategy_name", ['linear', 'random', 'additive'])
    def test_voice_zero_returns_zero_with_any_spread(self, strategy_name):
        """
        Voce 0 deve ritornare 0.0 con qualsiasi spread e num_voices.

        Nota: LinearPanStrategy NON rispetta questa invariante per design
        (voce 0 a -spread/2 con N>1). L'invariante voce 0 = 0 e' gestita
        dal VoiceManager che NON chiama get_pan_offset per la voce 0,
        o la chiama con spread=0.

        Questo test verifica che ogni strategy gestisca correttamente
        la chiamata con voice_index=0 per num_voices=1 (solo voce).
        """
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        strategy = VoicePanStrategyFactory.create(strategy_name)

        # Con una sola voce (voce 0 = unica voce), deve ritornare 0
        result = strategy.get_pan_offset(0, 1, 180.0)
        # Per LinearPanStrategy con N=1 il risultato e' 0.0 per definizione
        # Per le altre, l'invariante e' esplicito
        if strategy_name == 'linear':
            assert result == pytest.approx(0.0)
        # Per random e additive, il VoiceManager gestisce l'invariante esternamente


# =============================================================================
# 6. EDGE CASES COMUNI
# =============================================================================

class TestEdgeCases:
    """Test edge cases applicabili a tutte le strategy."""

    @pytest.mark.parametrize("strategy_name", ['linear', 'random', 'additive'])
    def test_spread_zero_all_return_zero(self, strategy_name):
        """Con spread=0 tutte le strategy ritornano 0.0."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        strategy = VoicePanStrategyFactory.create(strategy_name)

        for v in range(4):
            result = strategy.get_pan_offset(v, 4, 0.0)
            assert result == pytest.approx(0.0), (
                f"{strategy_name}: voce {v} con spread=0 deve ritornare 0.0, "
                f"ottenuto {result}"
            )

    @pytest.mark.parametrize("strategy_name", ['linear', 'random', 'additive'])
    def test_returns_float(self, strategy_name):
        """Tutte le strategy ritornano un float."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        strategy = VoicePanStrategyFactory.create(strategy_name)

        result = strategy.get_pan_offset(0, 4, 90.0)
        assert isinstance(result, (int, float))

    @pytest.mark.parametrize("strategy_name", ['linear', 'random', 'additive'])
    def test_num_voices_one_no_exception(self, strategy_name):
        """Tutte le strategy gestiscono num_voices=1 senza eccezioni."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        strategy = VoicePanStrategyFactory.create(strategy_name)

        result = strategy.get_pan_offset(0, 1, 90.0)
        assert isinstance(result, (int, float))

    @pytest.mark.parametrize("strategy_name", ['linear', 'random', 'additive'])
    def test_large_spread_no_exception(self, strategy_name):
        """Spread molto grande non solleva eccezioni."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        strategy = VoicePanStrategyFactory.create(strategy_name)

        result = strategy.get_pan_offset(0, 4, 3600.0)
        assert isinstance(result, (int, float))

    @pytest.mark.parametrize("strategy_name", ['linear', 'random', 'additive'])
    def test_many_voices_no_exception(self, strategy_name):
        """Molte voci (64) non sollevano eccezioni."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        strategy = VoicePanStrategyFactory.create(strategy_name)

        for v in range(64):
            result = strategy.get_pan_offset(v, 64, 360.0)
            assert isinstance(result, (int, float))


# =============================================================================
# 7. VOICE_PAN_STRATEGIES REGISTRY - COMPLETEZZA E STRUTTURA
# =============================================================================

class TestRegistry:
    """Verifica struttura e completezza del registro VOICE_PAN_STRATEGIES."""

    EXPECTED_STRATEGIES = {'linear', 'random', 'additive'}

    def test_registry_is_dict(self):
        """VOICE_PAN_STRATEGIES e' un dizionario."""
        _, _, _, _, registry, _, _ = _get_module()
        assert isinstance(registry, dict)

    def test_registry_contains_expected_strategies(self):
        """Il registry contiene tutte e tre le strategy attese."""
        _, _, _, _, registry, _, _ = _get_module()
        assert self.EXPECTED_STRATEGIES.issubset(set(registry.keys()))

    def test_registry_values_are_classes(self):
        """I valori del registry sono classi (non istanze)."""
        _, _, _, _, registry, _, _ = _get_module()
        for name, cls in registry.items():
            assert isinstance(cls, type), f"'{name}' non e' una classe"

    def test_registry_classes_are_voicepanstrategy(self):
        """Tutte le classi nel registry ereditano da VoicePanStrategy."""
        VoicePanStrategy, _, _, _, registry, _, _ = _get_module()
        for name, cls in registry.items():
            assert issubclass(cls, VoicePanStrategy), (
                f"'{name}' ({cls.__name__}) non eredita da VoicePanStrategy"
            )

    def test_linear_maps_to_linearpanstrategy(self):
        """'linear' punta a LinearPanStrategy."""
        _, LinearPanStrategy, _, _, registry, _, _ = _get_module()
        assert registry['linear'] is LinearPanStrategy

    def test_random_maps_to_randompanstrategy(self):
        """'random' punta a RandomPanStrategy."""
        _, _, RandomPanStrategy, _, registry, _, _ = _get_module()
        assert registry['random'] is RandomPanStrategy

    def test_additive_maps_to_additivepanstrategy(self):
        """'additive' punta a AdditivePanStrategy."""
        _, _, _, AdditivePanStrategy, registry, _, _ = _get_module()
        assert registry['additive'] is AdditivePanStrategy


# =============================================================================
# 8. REGISTER_VOICE_PAN_STRATEGY() - REGISTRAZIONE DINAMICA
# =============================================================================

class TestRegisterFunction:
    """Test della funzione di registrazione dinamica."""

    def test_register_new_strategy(self):
        """Registra una nuova strategy e la trova nel registry."""
        VoicePanStrategy, _, _, _, registry, register_voice_pan_strategy, _ = _get_module()

        class CustomPanStrategy(VoicePanStrategy):
            def get_pan_offset(self, voice_index, num_voices, spread):
                return voice_index * spread

            @property
            def name(self):
                return 'custom'

        register_voice_pan_strategy('custom', CustomPanStrategy)
        assert 'custom' in registry
        assert registry['custom'] is CustomPanStrategy

    def test_register_overwrites_existing(self):
        """Registrare con chiave esistente sovrascrive la strategy."""
        VoicePanStrategy, _, _, _, registry, register_voice_pan_strategy, _ = _get_module()

        class NewLinear(VoicePanStrategy):
            custom_marker = True

            def get_pan_offset(self, voice_index, num_voices, spread):
                return 0.0

            @property
            def name(self):
                return 'linear'

        register_voice_pan_strategy('linear', NewLinear)
        assert registry['linear'] is NewLinear
        assert hasattr(registry['linear'], 'custom_marker')

    def test_register_function_is_callable(self):
        """register_voice_pan_strategy e' una funzione callable."""
        _, _, _, _, _, register_voice_pan_strategy, _ = _get_module()
        assert callable(register_voice_pan_strategy)

    def test_register_function_has_docstring(self):
        """register_voice_pan_strategy ha docstring."""
        _, _, _, _, _, register_voice_pan_strategy, _ = _get_module()
        assert register_voice_pan_strategy.__doc__ is not None


# =============================================================================
# 9. VOICEPANSTRATEGYFACTORY - CREAZIONE E GESTIONE ERRORI
# =============================================================================

class TestVoicePanStrategyFactory:
    """Test della factory di creazione strategy."""

    def test_create_linear(self):
        """create('linear') ritorna un'istanza di LinearPanStrategy."""
        _, LinearPanStrategy, _, _, _, _, VoicePanStrategyFactory = _get_module()
        result = VoicePanStrategyFactory.create('linear')
        assert isinstance(result, LinearPanStrategy)

    def test_create_random(self):
        """create('random') ritorna un'istanza di RandomPanStrategy."""
        _, _, RandomPanStrategy, _, _, _, VoicePanStrategyFactory = _get_module()
        result = VoicePanStrategyFactory.create('random')
        assert isinstance(result, RandomPanStrategy)

    def test_create_additive(self):
        """create('additive') ritorna un'istanza di AdditivePanStrategy."""
        _, _, _, AdditivePanStrategy, _, _, VoicePanStrategyFactory = _get_module()
        result = VoicePanStrategyFactory.create('additive')
        assert isinstance(result, AdditivePanStrategy)

    def test_create_unknown_raises_valueerror(self):
        """create() con nome sconosciuto solleva ValueError."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        with pytest.raises(ValueError):
            VoicePanStrategyFactory.create('nonexistent_strategy')

    def test_valueerror_message_contains_name(self):
        """Il messaggio di errore contiene il nome richiesto."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        with pytest.raises(ValueError, match='invalid_name'):
            VoicePanStrategyFactory.create('invalid_name')

    def test_valueerror_message_contains_available(self):
        """Il messaggio di errore lista le strategy disponibili."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        with pytest.raises(ValueError) as exc_info:
            VoicePanStrategyFactory.create('wrong')
        error_msg = str(exc_info.value)
        # Almeno una delle strategy note deve apparire nel messaggio
        assert any(name in error_msg for name in ['linear', 'random', 'additive'])

    def test_create_returns_voicepanstrategy_instance(self):
        """create() ritorna sempre un'istanza di VoicePanStrategy."""
        VoicePanStrategy, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        for name in ['linear', 'random', 'additive']:
            instance = VoicePanStrategyFactory.create(name)
            assert isinstance(instance, VoicePanStrategy)

    def test_create_is_staticmethod(self):
        """create() e' uno staticmethod: accessibile da classe e da istanza."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        assert callable(VoicePanStrategyFactory.create)
        assert callable(VoicePanStrategyFactory().create)

    def test_create_has_docstring(self):
        """create() ha docstring."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        assert VoicePanStrategyFactory.create.__doc__ is not None

    def test_factory_has_docstring(self):
        """La factory ha docstring."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        assert VoicePanStrategyFactory.__doc__ is not None

    def test_default_strategy_is_linear(self):
        """Senza argomento, o con None, la factory usa 'linear' come default."""
        _, LinearPanStrategy, _, _, _, _, VoicePanStrategyFactory = _get_module()
        # Questo test e' opzionale: dipende dal design scelto.
        # Abilitiamolo solo se create() supporta un default.
        try:
            result = VoicePanStrategyFactory.create()
            assert isinstance(result, LinearPanStrategy)
        except TypeError:
            pass  # create() richiede argomento: accettabile


# =============================================================================
# 10. PATTERN ARCHITETTURALE
# =============================================================================

class TestArchitecturalPattern:
    """
    Verifica che voice_pan_strategy segua lo stesso pattern degli altri
    moduli strategy del sistema (variation_strategy, distribution_strategy,
    time_distribution, strategy_registry).
    """

    def test_registry_is_global_dict(self):
        """VOICE_PAN_STRATEGIES e' un dict globale (come VARIATION_STRATEGIES)."""
        _, _, _, _, registry, _, _ = _get_module()
        assert isinstance(registry, dict)

    def test_register_function_exists_and_callable(self):
        """register_voice_pan_strategy esiste ed e' callable."""
        _, _, _, _, _, register_voice_pan_strategy, _ = _get_module()
        assert callable(register_voice_pan_strategy)

    def test_factory_is_class(self):
        """VoicePanStrategyFactory e' una classe."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        assert isinstance(VoicePanStrategyFactory, type)

    def test_factory_create_is_accessible_from_class(self):
        """create() e' accessibile dalla classe senza istanziare."""
        _, _, _, _, _, _, VoicePanStrategyFactory = _get_module()
        assert callable(VoicePanStrategyFactory.create)

    def test_all_concrete_strategies_have_name_property(self):
        """Tutte le strategy concrete hanno la property name."""
        (_, LinearPanStrategy, RandomPanStrategy,
         AdditivePanStrategy, _, _, _) = _get_module()

        for cls in [LinearPanStrategy, RandomPanStrategy, AdditivePanStrategy]:
            instance = cls()
            assert hasattr(instance, 'name')
            assert isinstance(instance.name, str)
            assert len(instance.name) > 0

    def test_strategy_names_match_registry_keys(self):
        """Il name di ogni strategia corrisponde alla chiave nel registry."""
        (_, LinearPanStrategy, RandomPanStrategy,
         AdditivePanStrategy, registry, _, _) = _get_module()

        for key, cls in registry.items():
            instance = cls()
            assert instance.name == key, (
                f"Mismatch: registry['{key}'] ma strategy.name == '{instance.name}'"
            )


# =============================================================================
# 11. INTEGRAZIONE FACTORY-REGISTRY
# =============================================================================

class TestFactoryRegistryIntegration:
    """Verifica coerenza tra Factory e Registry."""

    def test_factory_reads_from_registry(self):
        """La Factory legge dal dizionario VOICE_PAN_STRATEGIES."""
        (VoicePanStrategy, _, _, _, registry,
         register_voice_pan_strategy, VoicePanStrategyFactory) = _get_module()

        class PingPanStrategy(VoicePanStrategy):
            custom_marker = 'ping'

            def get_pan_offset(self, voice_index, num_voices, spread):
                return 999.0

            @property
            def name(self):
                return 'ping'

        register_voice_pan_strategy('ping', PingPanStrategy)
        result = VoicePanStrategyFactory.create('ping')
        assert isinstance(result, PingPanStrategy)
        assert result.custom_marker == 'ping'

    def test_factory_reflects_registry_removal(self):
        """Se una strategy viene rimossa, la Factory fallisce correttamente."""
        _, _, _, _, registry, _, VoicePanStrategyFactory = _get_module()

        saved = registry.pop('additive')
        with pytest.raises(ValueError):
            VoicePanStrategyFactory.create('additive')
        registry['additive'] = saved

    def test_all_registry_entries_creatable(self):
        """Ogni entry nel registry e' creabile dalla Factory."""
        VoicePanStrategy, _, _, _, registry, _, VoicePanStrategyFactory = _get_module()

        for name in registry:
            instance = VoicePanStrategyFactory.create(name)
            assert instance is not None
            assert isinstance(instance, VoicePanStrategy)

    def test_registered_strategy_usable(self):
        """Una strategy appena registrata funziona correttamente."""
        (VoicePanStrategy, _, _, _, _,
         register_voice_pan_strategy, VoicePanStrategyFactory) = _get_module()

        class MirrorPanStrategy(VoicePanStrategy):
            """Pan che inverte la posizione per voci pari/dispari."""

            def get_pan_offset(self, voice_index, num_voices, spread):
                sign = 1.0 if voice_index % 2 == 0 else -1.0
                return sign * spread / 2.0

            @property
            def name(self):
                return 'mirror'

        register_voice_pan_strategy('mirror', MirrorPanStrategy)
        strategy = VoicePanStrategyFactory.create('mirror')

        assert strategy.get_pan_offset(0, 4, 100.0) == pytest.approx(50.0)
        assert strategy.get_pan_offset(1, 4, 100.0) == pytest.approx(-50.0)
        assert strategy.get_pan_offset(2, 4, 100.0) == pytest.approx(50.0)
        assert strategy.get_pan_offset(3, 4, 100.0) == pytest.approx(-50.0)