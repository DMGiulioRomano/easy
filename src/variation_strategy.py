# variation_strategy.py
from abc import ABC, abstractmethod
from distribution_strategy import DistributionStrategy
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