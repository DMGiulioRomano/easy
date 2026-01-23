"""
DensityController - Gestione densità e distribuzione temporale dei grani.

Implementa il modello Truax per la distribuzione temporale:
- SYNCHRONOUS (distribution=0): inter-onset fisso
- ASYNCHRONOUS (distribution=1): random(0, 2×avg)
- INTERPOLAZIONE: blend lineare tra i due
"""

import random
from typing import Optional, Union
from parameter_factory import ParameterFactory
from parameter import Parameter
from parameter_schema import DENSITY_PARAMETER_SCHEMA


class DensityController:
    """
    Controlla la densità granulare e la distribuzione temporale.
    
    Due modalità mutuamente esclusive:
    1. FILL_FACTOR (prioritaria): density = fill_factor / grain_duration
       - La densità si adatta automaticamente alla durata del grano
       
    2. DENSITY diretta: valore fisso o Envelope
       - Controllo esplicito della densità in grani/secondo
    """
    
    def __init__(
        self,
        params: dict,
        stream_id: str,
        duration: float,
        time_mode: str = 'absolute'
    ):
        """
        Inizializza il controller di densità.
        """
        self._factory = ParameterFactory(stream_id, duration, time_mode)
        self._params = self._factory.create_all_parameters(
            params,
            schema=DENSITY_PARAMETER_SCHEMA
        )

        self.distribution_param: Parameter = self._params['distribution']
        # 2. Determina modalità (Fill Factor vs Density)
        self._init_mode()
    
    def _init_mode(self) -> None:
        """
        Determina la modalità operativa e il parametro attivo.
        Priorità: Fill Factor > Density > Default (Fill Factor 2.0).
        """
        ff_param = self._params['fill_factor']
        dens_param = self._params['density']
        
        # Controlliamo il valore 'base' (senza calcolarlo al tempo t) per decidere la strategia
        if ff_param.value is not None:
            self._mode = 'fill_factor'
            self._active_density_param = ff_param
            # Alias per compatibilità
            self.fill_factor = ff_param 
            self.density = None
            
        elif dens_param.value is not None:
            self._mode = 'density'
            self._active_density_param = dens_param
            self.fill_factor = None
            self.density = dens_param
            
        else:
            # Fallback Default: Fill Factor = 2.0
            self._mode = 'fill_factor'
            # Creiamo un parametro default on-the-fly usando la factory per coerenza
            self._active_density_param = self._factory.create_single_parameter(
                'fill_factor', {'fill_factor': 2.0}
            )
            self.fill_factor = self._active_density_param
            self.density = None

    def calculate_inter_onset(
        self,
        elapsed_time: float,
        current_grain_duration: float
    ) -> float:
        """
        Calcola il tempo fino al prossimo onset (IOT) basandosi sul modello Truax.
        
        Args:
            elapsed_time: Tempo corrente nello stream.
            current_grain_duration: Durata del grano corrente (necessaria per Fill Factor).
        """
        # 1. Ottieni il valore di controllo (Density o Fill Factor)
        # Il metodo .get_value() gestisce internamente: Envelope, Jitter, Probabilità, Bounds.
        control_value = self._active_density_param.get_value(elapsed_time)
        
        # 2. Converti in Effective Density (Grani al secondo)
        if self._mode == 'fill_factor':
            # fill_factor = density * grain_dur  =>  density = fill_factor / grain_dur
            safe_dur = max(0.0001, current_grain_duration)
            effective_density = control_value / safe_dur
        else:
            effective_density = control_value
            
        # Hard Safety Clamp (limite fisico del motore audio, es. 4000hz)
        # Nota: effective_density è un valore calcolato, quindi lo clippiamo qui per sicurezza finale
        effective_density = max(0.1, min(4000.0, effective_density))
        
        # 3. Calcola Average Inter-Onset Time (IOT)
        avg_iot = 1.0 / effective_density
        
        # 4. Ottieni valore di Distribuzione (0=Sync, 1=Async)
        dist_val = self.distribution_param.get_value(elapsed_time)
        
        # 5. Applica Modello Truax (Blending temporale)
        if dist_val <= 0.0:
            # Sync: Metronomo perfetto
            return avg_iot
        else:
            # Async: Processo di Poisson approssimato (random 0..2*avg)
            async_iot = random.uniform(0.0, 2.0 * avg_iot)
            
            # Interpolazione lineare tra Sync e Async
            return (1.0 - dist_val) * avg_iot + dist_val * async_iot

    
    @property
    def mode(self) -> str:
        return self._mode
    
    @property
    def distribution(self):
        """Espone l'oggetto parametro distribution."""
        return self.distribution_param

    def get_density_value(self, elapsed_time: float) -> Optional[float]:
        """Per visualizzatore/debug."""
        if self._mode == 'density':
            return self._active_density_param.get_value(elapsed_time)
        return None
    
    def get_fill_factor_value(self, elapsed_time: float) -> Optional[float]:
        """Per visualizzatore/debug."""
        if self._mode == 'fill_factor':
            return self._active_density_param.get_value(elapsed_time)
        return None