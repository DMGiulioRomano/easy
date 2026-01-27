"""
DensityController - Gestione densità e distribuzione temporale dei grani.

Implementa il modello Truax per la distribuzione temporale:
- SYNCHRONOUS (distribution=0): inter-onset fisso
- ASYNCHRONOUS (distribution=1): random(0, 2×avg)
- INTERPOLAZIONE: blend lineare tra i due
"""

import random
from typing import Optional, Union
from parameter_schema import DENSITY_PARAMETER_SCHEMA
from strategy_registry import StrategyFactory
from parameter_definitions import get_parameter_definition
from parameter_orchestrator import ParameterOrchestrator
from orchestration_config import OrchestrationConfig

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
        params: dict,                      # 1. Dati specifici
        config: OrchestrationConfig,       # 2. Regole processo
        stream_id: str,                    # 3. Context identità
        duration: float,                   # 4. Context timing
        time_mode: str = 'absolute'        # 6. Context mode
    ):
        """
        Inizializza il controller di densità.
        """
                
        # Create orchestrator
        self._orchestrator = ParameterOrchestrator(
            stream_id=stream_id,
            duration=duration,
            time_mode=time_mode,
            config=config
        )

        # Create parameters
        self._params = self._orchestrator.create_all_parameters(
            params,
            schema=DENSITY_PARAMETER_SCHEMA
        )

        selected_param_name = self._determine_active_param()
        param_obj = self._params[selected_param_name]
        
        self._strategy = StrategyFactory.create_density_strategy(
            selected_param_name,
            param_obj,
            self._params  # Passa tutti i params per accedere a 'distribution'
        )
        self.distribution_param = self._params['distribution']
    
    def _determine_active_param(self) -> str:
        """Priorità: fill_factor > density."""
        if 'fill_factor' in self._params:
            return 'fill_factor'
        return 'density'    


 
    def calculate_inter_onset(
        self,
        elapsed_time: float,
        current_grain_duration: float
    ) -> float:
        """
        Calcola il tempo fino al prossimo onset (IOT) basandosi sul modello Truax.
        """
        # 1. STRATEGY: Calcola density (con context per grain_duration)
        density = self._strategy.calculate_density(
            elapsed_time,
            grain_duration=current_grain_duration
        )
    # devo pensare a un modo per centralizzare le evaluations. una sta qui
    # una sta nel parser e una nei parameter. Forse bisogna riutilizzare
    # la classe parameterEvaluator per dargli 
        density_bounds = get_parameter_definition('density')        
        density_bounded = max(
                density_bounds.min_val, 
                min(density_bounds.max_val, density)
            )


        # 3. CONTROLLER: Calcola average IOT
        avg_iot = 1.0 / density_bounded
        
        # 4. CONTROLLER: Applica distribuzione Truax
        return self._apply_truax_distribution(avg_iot, elapsed_time)

    def _apply_truax_distribution(self, avg_iot: float, elapsed_time: float) -> float:
        """
        Implementa il modello Truax per la distribuzione temporale.
        
        - distribution = 0.0: Synchronous (metronomo perfetto)
        - distribution = 1.0: Asynchronous (Poisson-like, random 0..2×avg)
        - Valori intermedi: interpolazione lineare
        """
        dist_val = self.distribution_param.get_value(elapsed_time)
        
        if dist_val <= 0.0:
            # Sync: IOT costante
            return avg_iot
        else:
            # Async: random 0..2×avg (simula processo Poisson)
            async_iot = random.uniform(0.0, 2.0 * avg_iot)
            
            # Blend lineare tra sync e async
            return (1.0 - dist_val) * avg_iot + dist_val * async_iot
    
    
    @property
    def mode(self) -> str:
        return self._strategy.name
        
    @property
    def distribution(self):
        """Espone l'oggetto parametro distribution."""
        return self.distribution_param

    @property
    def density(self):
        """Espone l'oggetto parametro distribution."""
        return self._determine_active_param()

    def __repr__(self) -> str:
        active_param = self._determine_active_param()
        return f"<DensityController {self._factory._parser.stream_id} [{self.mode}:{active_param}]>"