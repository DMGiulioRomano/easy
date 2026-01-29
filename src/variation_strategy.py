# variation_strategy.py
from abc import ABC, abstractmethod
from distribution_strategy import DistributionStrategy
from typing import Any 
import random 

class VariationStrategy(ABC):
    """Strategia di applicazione randomness a un valore base."""
    
    @abstractmethod
    def apply(self, base: float, mod_range: float, 
              distribution: DistributionStrategy) -> float:
        """Applica variazione al valore base."""
        pass

class AdditiveVariation(VariationStrategy):
    def apply(self, base: float, mod_range: float, 
              distribution: DistributionStrategy) -> float:
        return distribution.sample(base, mod_range) if mod_range > 0 else base

class QuantizedVariation(VariationStrategy):
    def apply(self, base: float, mod_range: float, 
              distribution: DistributionStrategy) -> float:
        if mod_range >= 1.0:
            raw_sample = distribution.sample(0.0, mod_range)
            return base + round(raw_sample)
        return base

class InvertVariation(VariationStrategy):
    def apply(self, base: float, mod_range: float, 
              distribution: DistributionStrategy) -> float:
        return 1.0 - base
    
class ChoiceVariation(VariationStrategy):
    """
    Selezione casuale da lista discreta.
    Usato per envelope, samples, preset values.
    """
    
    def apply(self, value: Any, mod_range: float, mod_prob: float) -> Any:
        """
        Args:
            value: lista di opzioni
            mod_prob: probabilità di variare (0-100)
        
        Returns:
            elemento scelto dalla lista
        """
        if not isinstance(value, list):
            raise TypeError(f"ChoiceVariation richiede lista, ricevuto {type(value)}")
        
        # Probabilità di dephasing
        if random.random() * 100 > mod_prob:
            # Non varia → restituisci primo elemento (default)
            return value[0]
        
        # Varia → scelta random
        return random.choice(value)