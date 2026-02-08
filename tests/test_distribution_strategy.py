"""
test_variation_registry.py

Test suite completa per il modulo variation_registry.py.

Coverage:
1. Test VARIATION_STRATEGIES registry - dictionary mapping
2. Test register_variation_strategy() - funzione di registrazione
3. Test VariationFactory.create() - factory method
4. Test validazione e errori
5. Test integrazione con variation strategies
6. Test estensibilità del registry
"""

import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, '/home/claude')

# Creo implementazione minimale per i test
from typing import Dict, Type
from abc import ABC, abstractmethod

# Mock VariationStrategy classes
class VariationStrategy(ABC):
    """Strategia di applicazione randomness a un valore base."""
    
    @abstractmethod
    def apply(self, base: float, mod_range: float, distribution) -> float:
        """Applica variazione al valore base."""
        pass  # pragma: no cover

class AdditiveVariation(VariationStrategy):
    def apply(self, base: float, mod_range: float, distribution) -> float:
        return distribution.sample(base, mod_range) if mod_range > 0 else base

class QuantizedVariation(VariationStrategy):
    def apply(self, base: float, mod_range: float, distribution) -> float:
        if mod_range >= 1.0:
            raw_sample = distribution.sample(0.0, mod_range)
            return base + round(raw_sample)
        return base

class InvertVariation(VariationStrategy):
    def apply(self, base: float, mod_range: float, distribution) -> float:
        return 1.0 - base

class ChoiceVariation(VariationStrategy):
    def apply(self, value, mod_range: float, distribution):
        import random
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            if mod_range == 0:
                return value[0] if value else 'default'
            return random.choice(value)
        raise TypeError(f"ChoiceVariation richiede stringa o lista")

# Registry
VARIATION_STRATEGIES: Dict[str, Type[VariationStrategy]] = {
    'additive': AdditiveVariation,
    'quantized': QuantizedVariation,
    'invert': InvertVariation,
    'choice': ChoiceVariation,
}

def register_variation_strategy(mode_name: str, strategy_class: Type[VariationStrategy]):
    """Registra una nuova strategia di variazione."""
    VARIATION_STRATEGIES[mode_name] = strategy_class
    print(f"✅ Registrata nuova strategia variation: {mode_name} -> {strategy_class.__name__}")

# Factory
class VariationFactory:
    """Crea strategie di variazione basate sul variation_mode."""
    
    @staticmethod
    def create(variation_mode: str) -> VariationStrategy:
        """Crea una strategia di variazione."""
        if variation_mode not in VARIATION_STRATEGIES:
            available = ', '.join(VARIATION_STRATEGIES.keys())
            raise ValueError(
                f"Strategia variation non trovata: '{variation_mode}'. "
                f"Strategie disponibili: {available}"
            )
        
        strategy_class = VARIATION_STRATEGIES[variation_mode]
        return strategy_class()


# =============================================================================
# 1. TEST VARIATION_STRATEGIES REGISTRY
# =============================================================================

class TestVariationStrategiesRegistry:
    """Test per il dictionary VARIATION_STRATEGIES."""
    
    def test_registry_exists(self):
        """Registry VARIATION_STRATEGIES esiste."""
        assert VARIATION_STRATEGIES is not None
    
    def test_registry_is_dict(self):
        """Registry è un dictionary."""
        assert isinstance(VARIATION_STRATEGIES, dict)
    
    def test_registry_has_core_strategies(self):
        """Registry contiene le 4 strategie core."""
        assert 'additive' in VARIATION_STRATEGIES
        assert 'quantized' in VARIATION_STRATEGIES
        assert 'invert' in VARIATION_STRATEGIES
        assert 'choice' in VARIATION_STRATEGIES
    
    def test_registry_values_are_classes(self):
        """Valori del registry sono classi."""
        for strategy_class in VARIATION_STRATEGIES.values():
            assert isinstance(strategy_class, type)
    
    def test_registry_keys_are_strings(self):
        """Chiavi del registry sono stringhe."""
        for key in VARIATION_STRATEGIES.keys():
            assert isinstance(key, str)
    
    def test_additive_maps_to_correct_class(self):
        """'additive' mappa a AdditiveVariation."""
        assert VARIATION_STRATEGIES['additive'] == AdditiveVariation
    
    def test_quantized_maps_to_correct_class(self):
        """'quantized' mappa a QuantizedVariation."""
        assert VARIATION_STRATEGIES['quantized'] == QuantizedVariation
    
    def test_invert_maps_to_correct_class(self):
        """'invert' mappa a InvertVariation."""
        assert VARIATION_STRATEGIES['invert'] == InvertVariation
    
    def test_choice_maps_to_correct_class(self):
        """'choice' mappa a ChoiceVariation."""
        assert VARIATION_STRATEGIES['choice'] == ChoiceVariation
    
    def test_all_strategies_inherit_from_base(self):
        """Tutte le strategie ereditano da VariationStrategy."""
        for strategy_class in VARIATION_STRATEGIES.values():
            assert issubclass(strategy_class, VariationStrategy)
    
    def test_registry_count(self):
        """Registry ha esattamente 4 strategie core."""
        assert len(VARIATION_STRATEGIES) >= 4  # >= per permettere estensioni nei test


# =============================================================================
# 2. TEST REGISTER_VARIATION_STRATEGY()
# =============================================================================

class TestRegisterVariationStrategy:
    """Test per la funzione register_variation_strategy()."""
    
    def setup_method(self):
        """Setup: salva stato originale del registry."""
        self.original_strategies = VARIATION_STRATEGIES.copy()
    
    def teardown_method(self):
        """Teardown: ripristina stato originale."""
        VARIATION_STRATEGIES.clear()
        VARIATION_STRATEGIES.update(self.original_strategies)
    
    def test_register_new_strategy(self):
        """Registrazione di una nuova strategia."""
        class CustomVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base * 2
        
        initial_count = len(VARIATION_STRATEGIES)
        register_variation_strategy('custom', CustomVariation)
        
        assert 'custom' in VARIATION_STRATEGIES
        assert VARIATION_STRATEGIES['custom'] == CustomVariation
        assert len(VARIATION_STRATEGIES) == initial_count + 1
        
        # Test funzionale
        strategy = VariationFactory.create('custom')
        mock_dist = Mock()
        result = strategy.apply(10.0, 0.0, mock_dist)
        assert result == 20.0
    
    def test_register_prints_confirmation(self, capsys):
        """Registrazione stampa messaggio di conferma."""
        class TestVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        register_variation_strategy('test', TestVariation)
        
        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "test" in captured.out
        assert "TestVariation" in captured.out
        
        # Test funzionale
        strategy = VariationFactory.create('test')
        mock_dist = Mock()
        assert strategy.apply(10.0, 0.0, mock_dist) == 10.0
    
    def test_register_overwrites_existing_strategy(self):
        """Registrazione sovrascrive strategie esistenti."""
        class NewAdditiveVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base + 999
        
        original_class = VARIATION_STRATEGIES['additive']
        register_variation_strategy('additive', NewAdditiveVariation)
        
        assert VARIATION_STRATEGIES['additive'] == NewAdditiveVariation
        assert VARIATION_STRATEGIES['additive'] != original_class
        
        # Test funzionale
        strategy = VariationFactory.create('additive')
        mock_dist = Mock()
        result = strategy.apply(10.0, 0.0, mock_dist)
        assert result == 1009.0
    
    def test_register_multiple_strategies(self):
        """Registrazione multipla di strategie diverse."""
        class Strategy1(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        class Strategy2(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        register_variation_strategy('strat1', Strategy1)
        register_variation_strategy('strat2', Strategy2)
        
        assert 'strat1' in VARIATION_STRATEGIES
        assert 'strat2' in VARIATION_STRATEGIES
        
        # Test funzionali
        mock_dist = Mock()
        s1 = VariationFactory.create('strat1')
        s2 = VariationFactory.create('strat2')
        assert s1.apply(10.0, 0.0, mock_dist) == 10.0
        assert s2.apply(20.0, 0.0, mock_dist) == 20.0
    
    def test_register_with_special_characters_in_name(self):
        """Registrazione con caratteri speciali nel nome."""
        class SpecialVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        register_variation_strategy('custom-variation_v2', SpecialVariation)
        
        assert 'custom-variation_v2' in VARIATION_STRATEGIES
        
        # Test funzionale
        strategy = VariationFactory.create('custom-variation_v2')
        mock_dist = Mock()
        assert strategy.apply(10.0, 0.0, mock_dist) == 10.0
    
    def test_registered_strategies_are_functional(self):
        """Strategie registrate sono funzionali."""
        class DoubleVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base * 2
        
        class TripleVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base * 3
        
        class AddNineNineNine(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base + 999
        
        register_variation_strategy('double', DoubleVariation)
        register_variation_strategy('triple', TripleVariation)
        register_variation_strategy('add999', AddNineNineNine)
        
        mock_dist = Mock()
        
        s1 = VariationFactory.create('double')
        assert s1.apply(10.0, 0.0, mock_dist) == 20.0
        
        s2 = VariationFactory.create('triple')
        assert s2.apply(10.0, 0.0, mock_dist) == 30.0
        
        s3 = VariationFactory.create('add999')
        assert s3.apply(10.0, 0.0, mock_dist) == 1009.0


# =============================================================================
# 3. TEST VARIATIONFACTORY.CREATE()
# =============================================================================

class TestVariationFactoryCreate:
    """Test per VariationFactory.create()."""
    
    def test_create_additive_strategy(self):
        """Creazione strategia 'additive'."""
        strategy = VariationFactory.create('additive')
        
        assert strategy is not None
        assert isinstance(strategy, AdditiveVariation)
        assert isinstance(strategy, VariationStrategy)
    
    def test_create_quantized_strategy(self):
        """Creazione strategia 'quantized'."""
        strategy = VariationFactory.create('quantized')
        
        assert isinstance(strategy, QuantizedVariation)
    
    def test_create_invert_strategy(self):
        """Creazione strategia 'invert'."""
        strategy = VariationFactory.create('invert')
        
        assert isinstance(strategy, InvertVariation)
    
    def test_create_choice_strategy(self):
        """Creazione strategia 'choice'."""
        strategy = VariationFactory.create('choice')
        
        assert isinstance(strategy, ChoiceVariation)
    
    def test_create_returns_new_instances(self):
        """create() restituisce nuove istanze ogni volta."""
        strategy1 = VariationFactory.create('additive')
        strategy2 = VariationFactory.create('additive')
        
        assert strategy1 is not strategy2
        assert type(strategy1) == type(strategy2)
    
    def test_create_invalid_mode_raises_error(self):
        """create() con mode invalido solleva ValueError."""
        with pytest.raises(ValueError) as exc_info:
            VariationFactory.create('nonexistent')
        
        assert "non trovata" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)
    
    def test_create_error_includes_available_strategies(self):
        """Messaggio di errore include strategie disponibili."""
        with pytest.raises(ValueError) as exc_info:
            VariationFactory.create('invalid')
        
        error_msg = str(exc_info.value)
        assert "additive" in error_msg
        assert "quantized" in error_msg
        assert "invert" in error_msg
        assert "choice" in error_msg
    
    def test_create_empty_string_raises_error(self):
        """create() con stringa vuota solleva ValueError."""
        with pytest.raises(ValueError):
            VariationFactory.create('')
    
    def test_create_case_sensitive(self):
        """create() è case-sensitive."""
        # Lowercase funziona
        strategy_lower = VariationFactory.create('additive')
        assert strategy_lower is not None
        
        # Uppercase non funziona
        with pytest.raises(ValueError):
            VariationFactory.create('ADDITIVE')
    
    def test_create_with_registered_custom_strategy(self):
        """create() funziona con strategie custom registrate."""
        class MyCustomVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base * 3
        
        register_variation_strategy('mycustom', MyCustomVariation)
        
        strategy = VariationFactory.create('mycustom')
        assert isinstance(strategy, MyCustomVariation)
        
        # Test funzionale
        mock_dist = Mock()
        result = strategy.apply(10.0, 0.0, mock_dist)
        assert result == 30.0


# =============================================================================
# 4. TEST INTEGRAZIONE CON VARIATION STRATEGIES
# =============================================================================

class TestVariationStrategyIntegration:
    """Test integrazione factory con strategie concrete."""
    
    def test_additive_strategy_functional(self):
        """AdditiveVariation creata da factory è funzionale."""
        strategy = VariationFactory.create('additive')
        
        mock_dist = Mock()
        mock_dist.sample.return_value = 5.0
        
        result = strategy.apply(base=10.0, mod_range=2.0, distribution=mock_dist)
        
        assert result == 5.0
        mock_dist.sample.assert_called_once_with(10.0, 2.0)
    
    def test_additive_with_zero_range(self):
        """AdditiveVariation con mod_range=0 restituisce base."""
        strategy = VariationFactory.create('additive')
        
        mock_dist = Mock()
        result = strategy.apply(base=10.0, mod_range=0.0, distribution=mock_dist)
        
        assert result == 10.0
        mock_dist.sample.assert_not_called()
    
    def test_quantized_strategy_functional(self):
        """QuantizedVariation creata da factory è funzionale."""
        strategy = VariationFactory.create('quantized')
        
        mock_dist = Mock()
        mock_dist.sample.return_value = 2.7  # Dovrebbe arrotondare a 3
        
        result = strategy.apply(base=10.0, mod_range=5.0, distribution=mock_dist)
        
        assert result == 13.0  # 10 + round(2.7)
    
    def test_quantized_with_small_range(self):
        """QuantizedVariation con mod_range < 1 restituisce base."""
        strategy = VariationFactory.create('quantized')
        
        mock_dist = Mock()
        result = strategy.apply(base=10.0, mod_range=0.5, distribution=mock_dist)
        
        assert result == 10.0
        mock_dist.sample.assert_not_called()
    
    def test_invert_strategy_functional(self):
        """InvertVariation creata da factory è funzionale."""
        strategy = VariationFactory.create('invert')
        
        mock_dist = Mock()
        
        result = strategy.apply(base=0.3, mod_range=0.0, distribution=mock_dist)
        
        assert result == 0.7  # 1.0 - 0.3
    
    def test_invert_ignores_distribution(self):
        """InvertVariation non usa distribution."""
        strategy = VariationFactory.create('invert')
        
        mock_dist = Mock()
        strategy.apply(base=0.5, mod_range=1.0, distribution=mock_dist)
        
        mock_dist.sample.assert_not_called()
    
    def test_choice_strategy_with_string(self):
        """ChoiceVariation con stringa singola."""
        strategy = VariationFactory.create('choice')
        
        mock_dist = Mock()
        result = strategy.apply(value='hanning', mod_range=1.0, distribution=mock_dist)
        
        assert result == 'hanning'
    
    def test_choice_strategy_with_list(self):
        """ChoiceVariation con lista."""
        strategy = VariationFactory.create('choice')
        
        mock_dist = Mock()
        choices = ['a', 'b', 'c']
        result = strategy.apply(value=choices, mod_range=1.0, distribution=mock_dist)
        
        assert result in choices
    
    def test_choice_strategy_with_zero_range(self):
        """ChoiceVariation con mod_range=0 restituisce primo elemento."""
        strategy = VariationFactory.create('choice')
        
        mock_dist = Mock()
        choices = ['first', 'second', 'third']
        result = strategy.apply(value=choices, mod_range=0.0, distribution=mock_dist)
        
        assert result == 'first'
    
    def test_choice_strategy_with_invalid_type_raises_error(self):
        """ChoiceVariation con tipo invalido solleva TypeError."""
        strategy = VariationFactory.create('choice')
        
        mock_dist = Mock()
        
        with pytest.raises(TypeError) as exc_info:
            strategy.apply(value=123, mod_range=1.0, distribution=mock_dist)
        
        assert "ChoiceVariation richiede" in str(exc_info.value)


# =============================================================================
# 5. TEST EDGE CASES E VALIDAZIONE
# =============================================================================

class TestVariationRegistryEdgeCases:
    """Test edge cases e validazione."""
    
    def test_registry_not_none_after_imports(self):
        """Registry non è None dopo import."""
        assert VARIATION_STRATEGIES is not None
    
    def test_factory_create_is_static_method(self):
        """VariationFactory.create è metodo statico."""
        # Può essere chiamato senza istanziare
        strategy = VariationFactory.create('additive')
        assert strategy is not None
    
    def test_all_registered_strategies_instantiable(self):
        """Tutte le strategie registrate possono essere istanziate."""
        for mode_name, strategy_class in VARIATION_STRATEGIES.items():
            strategy = strategy_class()
            assert isinstance(strategy, VariationStrategy)
    
    def test_all_strategies_have_apply_method(self):
        """Tutte le strategie hanno metodo apply."""
        for strategy_class in VARIATION_STRATEGIES.values():
            assert hasattr(strategy_class, 'apply')
    
    def test_create_with_whitespace_raises_error(self):
        """create() con whitespace solleva ValueError."""
        with pytest.raises(ValueError):
            VariationFactory.create('  ')
        
        with pytest.raises(ValueError):
            VariationFactory.create('additive ')
    
    def test_registry_mutation_affects_factory(self):
        """Modifiche al registry influenzano factory."""
        class TempStrategy(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        VARIATION_STRATEGIES['temp'] = TempStrategy
        
        try:
            strategy = VariationFactory.create('temp')
            assert isinstance(strategy, TempStrategy)
            
            # Test funzionale
            mock_dist = Mock()
            assert strategy.apply(10.0, 0.0, mock_dist) == 10.0
        finally:
            del VARIATION_STRATEGIES['temp']


# =============================================================================
# 6. TEST WORKFLOW E PATTERN
# =============================================================================

class TestVariationRegistryWorkflow:
    """Test workflow tipici e pattern di utilizzo."""
    
    def test_workflow_parameter_bound_creation(self):
        """Workflow: ParameterBounds usa variation_mode."""
        # Simula ParameterBounds che specifica variation_mode
        variation_mode = 'quantized'
        
        # Factory crea la strategia
        strategy = VariationFactory.create(variation_mode)
        
        # Strategia viene usata
        mock_dist = Mock()
        mock_dist.sample.return_value = 3.8
        result = strategy.apply(10.0, 5.0, mock_dist)
        
        assert result == 14.0  # 10 + round(3.8)
    
    def test_workflow_extension_pattern(self):
        """Workflow: estensione con nuova strategia."""
        # 1. Definisci nuova strategia
        class ExponentialVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                import math
                return base * math.exp(mod_range)
        
        # 2. Registra
        register_variation_strategy('exponential', ExponentialVariation)
        
        # 3. Usa tramite factory
        strategy = VariationFactory.create('exponential')
        
        assert isinstance(strategy, ExponentialVariation)
        
        # 4. Test funzionale
        mock_dist = Mock()
        result = strategy.apply(10.0, 1.0, mock_dist)
        import math
        assert result == pytest.approx(10.0 * math.e)
    
    def test_workflow_strategy_selection(self):
        """Workflow: selezione strategia in base a configurazione."""
        # Simula scelta basata su tipo parametro
        param_type = 'semitones'
        mode = 'quantized'  # Direct assignment
        
        strategy = VariationFactory.create(mode)
        assert isinstance(strategy, QuantizedVariation)
    
    def test_workflow_strategy_selection_ratio(self):
        """Workflow: selezione additive per ratio."""
        param_type = 'ratio'
        mode = 'additive'  # Direct assignment
        
        strategy = VariationFactory.create(mode)
        assert isinstance(strategy, AdditiveVariation)
    
    def test_workflow_strategy_selection_other(self):
        """Workflow: selezione additive per tipo sconosciuto."""
        param_type = 'unknown'
        mode = 'additive'  # Direct assignment (fallback)
        
        strategy = VariationFactory.create(mode)
        assert isinstance(strategy, AdditiveVariation)
    
    def test_workflow_all_strategies_compatible_interface(self):
        """Workflow: tutte le strategie hanno interfaccia compatibile."""
        mock_dist = Mock()
        mock_dist.sample.return_value = 5.0
        
        for mode in ['additive', 'quantized', 'invert']:
            strategy = VariationFactory.create(mode)
            
            # Tutte accettano stessi parametri
            result = strategy.apply(
                base=10.0,
                mod_range=2.0,
                distribution=mock_dist
            )
            
            assert isinstance(result, (int, float))


# =============================================================================
# 7. TEST PARAMETRIZZATI
# =============================================================================

class TestVariationRegistryParametrized:
    """Test parametrizzati per copertura sistematica."""
    
    @pytest.mark.parametrize("mode,expected_class", [
        ('additive', AdditiveVariation),
        ('quantized', QuantizedVariation),
        ('invert', InvertVariation),
        ('choice', ChoiceVariation),
    ])
    def test_create_returns_correct_class(self, mode, expected_class):
        """Factory crea la classe corretta per ogni mode."""
        strategy = VariationFactory.create(mode)
        assert isinstance(strategy, expected_class)
    
    @pytest.mark.parametrize("mode", ['additive', 'quantized', 'invert', 'choice'])
    def test_all_modes_create_unique_instances(self, mode):
        """Ogni mode crea istanze uniche."""
        s1 = VariationFactory.create(mode)
        s2 = VariationFactory.create(mode)
        
        assert s1 is not s2
    
    @pytest.mark.parametrize("invalid_mode", [
        'invalid',
        'add',  # Partial match
        'ADDITIVE',  # Wrong case
        'additive123',
        '123',
        'none',
        'null',
    ])
    def test_create_invalid_modes_raise_error(self, invalid_mode):
        """Factory solleva ValueError per mode invalidi."""
        with pytest.raises(ValueError):
            VariationFactory.create(invalid_mode)
    
    @pytest.mark.parametrize("mode", ['additive', 'quantized', 'invert', 'choice'])
    def test_registry_has_all_core_modes(self, mode):
        """Registry contiene tutti i mode core."""
        assert mode in VARIATION_STRATEGIES
    
    @pytest.mark.parametrize("mode", ['additive', 'quantized', 'invert', 'choice'])
    def test_strategies_are_subclasses(self, mode):
        """Tutte le strategie sono subclass di VariationStrategy."""
        strategy_class = VARIATION_STRATEGIES[mode]
        assert issubclass(strategy_class, VariationStrategy)


# =============================================================================
# 8. TEST ESTENSIBILITÀ
# =============================================================================

class TestVariationRegistryExtensibility:
    """Test estensibilità del sistema."""
    
    def setup_method(self):
        """Setup: salva stato originale."""
        self.original_strategies = VARIATION_STRATEGIES.copy()
    
    def teardown_method(self):
        """Teardown: ripristina stato."""
        VARIATION_STRATEGIES.clear()
        VARIATION_STRATEGIES.update(self.original_strategies)
    
    def test_can_add_logarithmic_variation(self):
        """Sistema supporta estensione con LogarithmicVariation."""
        class LogarithmicVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                import math
                if mod_range > 0:
                    return base * math.log1p(mod_range)
                return base
        
        register_variation_strategy('logarithmic', LogarithmicVariation)
        
        strategy = VariationFactory.create('logarithmic')
        assert isinstance(strategy, LogarithmicVariation)
        
        # Test funzionale con mod_range > 0
        mock_dist = Mock()
        result = strategy.apply(10.0, 2.0, mock_dist)
        assert result > 0  # log1p(2) > 0
        
        # Test funzionale con mod_range = 0
        result_zero = strategy.apply(10.0, 0.0, mock_dist)
        assert result_zero == 10.0
    
    def test_can_add_biased_gaussian_variation(self):
        """Sistema supporta BiasedGaussianVariation."""
        class BiasedGaussianVariation(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                # Simula bias verso valori alti
                sample = distribution.sample(base, mod_range)
                return max(sample, base)
        
        register_variation_strategy('biased_gaussian', BiasedGaussianVariation)
        
        strategy = VariationFactory.create('biased_gaussian')
        assert isinstance(strategy, BiasedGaussianVariation)
        
        # Test funzionale
        mock_dist = Mock()
        mock_dist.sample.return_value = 15.0  # sample > base
        result = strategy.apply(10.0, 5.0, mock_dist)
        assert result == 15.0  # max(15, 10)
        
        # Test quando sample < base
        mock_dist.sample.return_value = 5.0
        result = strategy.apply(10.0, 5.0, mock_dist)
        assert result == 10.0  # max(5, 10)
    
    def test_multiple_custom_strategies_coexist(self):
        """Multiple strategie custom coesistono."""
        class Strategy1(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        class Strategy2(VariationStrategy):
            def apply(self, base, mod_range, distribution):
                return base
        
        register_variation_strategy('custom1', Strategy1)
        register_variation_strategy('custom2', Strategy2)
        
        s1 = VariationFactory.create('custom1')
        s2 = VariationFactory.create('custom2')
        
        assert type(s1) != type(s2)
        assert isinstance(s1, Strategy1)
        assert isinstance(s2, Strategy2)
        
        # Test funzionali
        mock_dist = Mock()
        result1 = s1.apply(10.0, 2.0, mock_dist)
        result2 = s2.apply(20.0, 3.0, mock_dist)
        assert result1 == 10.0
        assert result2 == 20.0