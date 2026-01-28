# strategies.py
"""
Definisce le interfacce Strategy per tutti i controller.
Ogni strategia incapsula completamente il calcolo di un valore.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union
from parameter import Parameter
from envelope import Envelope
# =============================================================================
# STRATEGIE PITCH
# =============================================================================

class PitchStrategy(ABC):
    """Interfaccia base per tutte le strategie di pitch."""
    
    @abstractmethod
    def calculate(self, elapsed_time: float) -> float:
        """Calcola il pitch ratio finale."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome della strategia (per debug)."""
        pass
    
    @property
    @abstractmethod
    def base_value(self) -> Union[float, Envelope, Parameter]:
        """Valore base (per visualizzazione)."""
        pass


class SemitonesStrategy(PitchStrategy):
    """Strategia pitch in semitoni."""
    
    def __init__(self, semitones_param: Parameter):
        self._param = semitones_param
    
    def calculate(self, elapsed_time: float) -> float:
        semitones = self._param.get_value(elapsed_time)
        return 2 ** (semitones / 12.0)
    
    @property
    def name(self) -> str:
        return "semitones"
    
    @property
    def base_value(self):
        return self._param.value


class RatioStrategy(PitchStrategy):
    """Strategia pitch in ratio diretto."""
    
    def __init__(self, ratio_param: Parameter):
        self._param = ratio_param
    
    def calculate(self, elapsed_time: float) -> float:
        return self._param.get_value(elapsed_time)
    
    @property
    def name(self) -> str:
        return "ratio"
    
    @property
    def base_value(self):
        return self._param.value


# =============================================================================
# STRATEGIE DENSITY
# =============================================================================

class DensityStrategy(ABC):
    """Interfaccia base per calcolare la densità."""
    
    @abstractmethod
    def calculate_density(self, elapsed_time: float, **context) -> float:
        """
        Calcola la densità in grani/secondo.
        
        Args:
            elapsed_time: tempo corrente nello stream
            **context: dati contestuali (es. grain_duration per fill_factor)
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

 
class FillFactorStrategy(DensityStrategy):
    """Strategia: density = fill_factor / grain_duration."""
    
    def __init__(self, fill_factor_param: Parameter, distribution_param: Parameter):
        self._fill_factor = fill_factor_param
        # distribution non serve qui, solo nel controller!
    
    def calculate_density(self, elapsed_time: float, **context) -> float:
        if 'grain_duration' not in context:
            raise ValueError(f"{self.__class__.__name__} requires 'grain_duration' in context")
        fill_factor = self._fill_factor.get_value(elapsed_time)
        grain_duration = context['grain_duration']
        return fill_factor / grain_duration
    
    @property
    def name(self) -> str:
        return "fill_factor"

class DirectDensityStrategy(DensityStrategy):
    """Strategia: density diretta dal parametro."""
    
    def __init__(self, density_param: Parameter, distribution_param: Parameter):
        self._density = density_param
    
    def calculate_density(self, elapsed_time: float, **context) -> float:
        return self._density.get_value(elapsed_time)
    
    @property
    def name(self) -> str:
        return "density"