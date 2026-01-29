# variation_registry.py
"""
Registry e Factory per le strategie di variazione.
Segue lo stesso pattern di strategy_registry.py per coerenza.
"""

from typing import Dict, Type
from variation_strategy import (
    VariationStrategy,
    AdditiveVariation,
    QuantizedVariation,
    InvertVariation
)

# =============================================================================
# REGISTRY
# =============================================================================

VARIATION_STRATEGIES: Dict[str, Type[VariationStrategy]] = {
    'additive': AdditiveVariation,
    'quantized': QuantizedVariation,
    'invert': InvertVariation,
}


# =============================================================================
# FUNZIONI DI REGISTRAZIONE (per estensibilità futura)
# =============================================================================

def register_variation_strategy(mode_name: str, strategy_class: Type[VariationStrategy]):
    """
    Registra una nuova strategia di variazione.
    
    Esempi futuri:
    - 'logarithmic': LogarithmicVariation
    - 'exponential': ExponentialVariation
    - 'biased_gaussian': BiasedGaussianVariation
    """
    VARIATION_STRATEGIES[mode_name] = strategy_class
    print(f"✅ Registrata nuova strategia variation: {mode_name} -> {strategy_class.__name__}")


# =============================================================================
# FACTORY
# =============================================================================

class VariationFactory:
    """Crea strategie di variazione basate sul variation_mode."""
    
    @staticmethod
    def create(variation_mode: str) -> VariationStrategy:
        """
        Crea una strategia di variazione.
        
        Args:
            variation_mode: nome della modalità ('additive', 'quantized', 'invert')
            
        Returns:
            Istanza della strategia corrispondente
            
        Raises:
            ValueError: se variation_mode non è registrato
        """
        if variation_mode not in VARIATION_STRATEGIES:
            available = ', '.join(VARIATION_STRATEGIES.keys())
            raise ValueError(
                f"Strategia variation non trovata: '{variation_mode}'. "
                f"Strategie disponibili: {available}"
            )
        
        strategy_class = VARIATION_STRATEGIES[variation_mode]
        return strategy_class()