"""
ParameterEvaluator - Gestione centralizzata dei parametri per la sintesi granulare.

Responsabilità:
- Parsing di parametri YAML (numeri, liste breakpoints, dict con type)
- Valutazione di parametri fissi o Envelope al tempo t
- Safety bounds e clipping con logging
- Gestione time_mode normalized/absolute

Questa classe è usata da Stream e da tutti i Controller.
"""

from dataclasses import dataclass
from typing import Union, Optional, Dict, Any
from envelope import Envelope
from logger import log_clip_warning
import random
from utils import *

class Evaluator:
    """
    Gestisce valutazione 
    """

    def __init__(self, stream_id: str, duration: float, time_mode: str = 'absolute'):
        """
        Inizializza l'evaluator per uno stream specifico.
        
        Args:
            stream_id: identificatore dello stream (per logging)
            duration: durata dello stream in secondi (per normalizzazione)
            time_mode: 'absolute' o 'normalized' (default globale per envelope)
        """
        self.stream_id = stream_id
        self.duration = duration
        self.time_mode = time_mode
    
    def _evaluate(self, param: Union[float, int, Envelope], time: float, 
                 param_name: str) -> float:
        """
        Valuta un parametro al tempo dato con safety bounds.
        
        Se il valore è fuori dai bounds definiti in BOUNDS, viene clippato
        e un warning viene loggato.
        
        Args:
            param: numero fisso o Envelope
            time: tempo in secondi (relativo all'onset dello stream)
            param_name: nome del parametro (per bounds lookup e logging)
            
        Returns:
            float: valore clippato nei bounds di sicurezza
            
        Raises:
            ValueError: se param_name non ha bounds definiti
        """
        bounds = self.BOUNDS.get(param_name)
        if bounds is None:
            raise ValueError(
                f"Bounds non definiti per '{param_name}'. "
                f"Aggiungi una entry in ParameterEvaluator.BOUNDS"
            )
        
        # Valuta il parametro
        is_envelope = isinstance(param, Envelope)
        value = param.evaluate(time) if is_envelope else float(param)
        
        # Clip ai bounds
        clamped = max(bounds.min_val, min(bounds.max_val, value))
        
        # Log se clippato
        if value != clamped:
            log_clip_warning(
                self.stream_id, 
                param_name, 
                time,
                value, 
                clamped, 
                bounds.min_val, 
                bounds.max_val, 
                is_envelope
            )
        
        return clamped
    
    def get_bounds(self, param_name: str) -> ParameterBounds:
        """
        Recupera i bounds per un parametro specifico.
        Necessario per VoiceManager e PitchController.
        """
        if param_name not in self.BOUNDS:
            raise ValueError(f"Bounds non definiti per '{param_name}'")
        return self.BOUNDS[param_name]


    def __call__(self, param, time: float, param_name: str) -> float:
        """
        Evaluation semplice: param → valore con bounds.
        
        Per parametri SENZA variazione stocastica:
        - pointer.start
        - loop bounds
        - density base
        - fill_factor
        - ecc.
        """
        return self._evaluate(param, time, param_name)
        
    def __repr__(self):
        return (f"ParameterEvaluator(stream_id='{self.stream_id}', "
                f"duration={self.duration}, time_mode='{self.time_mode}')")