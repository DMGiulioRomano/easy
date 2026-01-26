# src/pitch_controller.py
"""
PitchController - Gestione pitch/trasposizione per sintesi granulare

Estratto da Stream come parte del refactoring Fase 3.
Gestisce la trasposizione con due modalità:
- Semitoni: specificando shift_semitones (convertito a ratio alla fine)
- Ratio: specificando ratio direttamente (default 1.0)

Supporta range stocastico in entrambe le modalità.
Ispirato al DMX-1000 di Barry Truax (1988)
"""

import math
from typing import Union, Optional
from parameter_factory import ParameterFactory
from parameter import Parameter
from parameter_schema import PITCH_PARAMETER_SCHEMA
from strategy_registry import StrategyFactory
from parameter_orchestrator import ParameterOrchestrator


class PitchController:
    """
    Gestisce la trasposizione del pitch per i grani.
    Responsabilità:
    1. Inizializzare i parametri corretti (Ratio vs Semitoni).
    2. Fornire un unico metodo `calculate(t)` che restituisce sempre un Ratio.
    """    
    
    def __init__(
        self,
        params: dict,
        stream_id: str,
        duration: float,
        time_mode: str = 'absolute'
    ):
        """
        Inizializza il controller.
        
        Args:
        """
        # Extract dephase config
        dephase_config = params.get('dephase')
        
        # Create orchestrator
        self._orchestrator = ParameterOrchestrator(
            stream_id=stream_id,
            duration=duration,
            time_mode=time_mode
        )
        self._orchestrator.set_dephase_config(dephase_config)
        
        # Create parameters
        self._loaded_params = self._orchestrator.create_all_parameters(
            params, 
            schema=PITCH_PARAMETER_SCHEMA
        )
    
        selected_param_name = self._determine_active_param()
        param_obj = self._loaded_params[selected_param_name]
        self._strategy = StrategyFactory.create_pitch_strategy(
            selected_param_name, 
            param_obj, 
            self._loaded_params
        )


    def _determine_active_param(self) -> str:
        """Logica di selezione separata e testabile."""
        if 'pitch_semitones' in self._loaded_params:
            return 'pitch_semitones'
        return 'pitch_ratio'
    
    def calculate(self, elapsed_time: float) -> float:
        """Delega COMPLETAMENTE alla strategy."""
        return self._strategy.calculate(elapsed_time)
    
    @property
    def mode(self) -> str:
        return self._strategy.name    

    @property
    def base_semitones(self):
        """Valore base semitoni (o Envelope) senza jitter."""
        if 'pitch_semitones' in self._loaded_params:
            return self._loaded_params['pitch_semitones'].value
        return None
    
    @property
    def base_ratio(self):
        """Valore base ratio (o Envelope) senza jitter."""
        if 'pitch_ratio' in self._loaded_params:
            return self._loaded_params['pitch_ratio'].value
        return None

    @property
    def range(self):
        """Espone il range del parametro attivo."""
        active_param = self._determine_active_param()
        if active_param in self._loaded_params:
            param = self._loaded_params[active_param]
            if hasattr(param, '_mod_range') and param._mod_range is not None:
                return param._mod_range
        return 0.0
    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        return f"PitchController(mode={self._mode}, param='{self._active_param.name}')"    
