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
    """Interfaccia base per tutte le strategie di densità."""
    
    @abstractmethod
    def calculate_inter_onset(self, 
                            elapsed_time: float, 
                            grain_duration: float) -> float:
        """Calcola inter-onset time."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass


class FillFactorStrategy(DensityStrategy):
    """Strategia fill-factor (density = fill_factor / grain_duration)."""
    
    def __init__(self, fill_factor_param: Parameter, distribution_param: Parameter):
        self._fill_factor = fill_factor_param
        self._distribution = distribution_param
    
    def calculate_inter_onset(self, elapsed_time: float, grain_duration: float) -> float:
        fill_factor = self._fill_factor.get_value(elapsed_time)
        effective_density = fill_factor / max(0.0001, grain_duration)
        # ... logica distribution (Truax model)
        return self._calculate_with_distribution(effective_density, elapsed_time)
    
    def _calculate_with_distribution(self, density: float, elapsed_time: float) -> float:
        """Implementa il modello Truax."""
        avg_iot = 1.0 / density
        dist_val = self._distribution.get_value(elapsed_time)
        # ... stessa logica di prima
        return avg_iot
    
    @property
    def name(self) -> str:
        return "fill_factor"


class DirectDensityStrategy(DensityStrategy):
    """Strategia density diretta (grani/secondo)."""
    
    def __init__(self, density_param: Parameter, distribution_param: Parameter):
        self._density = density_param
        self._distribution = distribution_param
    
    def calculate_inter_onset(self, elapsed_time: float, grain_duration: float) -> float:
        density = self._density.get_value(elapsed_time)
        # ... logica distribution
        avg_iot = 1.0 / density
        # ... stessa logica
        return avg_iot
    
    @property
    def name(self) -> str:
        return "density"