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
            params: dict con configurazione pitch da YAML (sotto 'pitch' key)
        """
        self._factory = ParameterFactory(stream_id, duration, time_mode)
        self._loaded_params = self._factory.create_all_parameters(
            params, 
            schema=PITCH_PARAMETER_SCHEMA
        )
    
        # Determinazione modalità (SEMPLICE!)
        if 'pitch_semitones' in self._loaded_params:
            self._mode = 'semitones'
            self._active_param = self._loaded_params['pitch_semitones']
        else:
            self._mode = 'ratio'
            self._active_param = self._loaded_params['pitch_ratio']
        # Backward compatibility
        self._base_semitones = self._active_param.value if self._mode == 'semitones' else None
        self._base_ratio = self._active_param.value if self._mode == 'ratio' else None

        
    def calculate(self, elapsed_time: float) -> float:
        """
        Calcola il pitch ratio finale al tempo t.
        
        Il metodo .get_value() del parametro gestisce internamente:
        - Valore base (fisso o Envelope)
        - Range stocastico (Additive o Quantized)
        - Dephase probability
        - Clipping ai bounds di sicurezza
        """
        # 1. Ottieni il valore "sporco" (base + jitter)
        raw_val = self._active_param.get_value(elapsed_time)
        
        # 2. Adatta il valore al dominio richiesto (Ratio)
        if self._mode == 'semitones':
            return self.semitones_to_ratio(raw_val)
        else:
            return raw_val
        
    # =========================================================================
    # STATIC METHODS
    # =========================================================================
    
    @staticmethod
    def semitones_to_ratio(semitones: float) -> float:
        """
        Converte semitoni in ratio di frequenza.
        
        Formula: ratio = 2^(semitones/12)
        
        Args:
            semitones: trasposizione in semitoni (positivi = up, negativi = down)
            
        Returns:
            float: ratio di frequenza
        """
        return pow(2.0, semitones / 12.0)

    # =========================================================================
    # PROPERTIES (Read-only access)
    # =========================================================================
    
    @property
    def mode(self) -> str:
        return self._mode
    
    @property
    def base_semitones(self):
        """Valore base semitoni (o Envelope) senza jitter."""
        return self._base_semitones
    
    @property
    def base_ratio(self):
        """Valore base ratio (o Envelope) senza jitter."""
        return self._base_ratio

    @property
    def range(self):
        """
        Valore del range (o Envelope). 
        Attenzione: questo è il valore raw, non l'oggetto Parameter.
        """
        # Ricostruiamo un parametro dummy se serve il valore calcolato, 
        # oppure ritorniamo il raw value/envelope.
        # Per semplicità ritorniamo l'oggetto Envelope o il float.
        if hasattr(self._active_param, '_mod_range') and self._active_param._mod_range is not None:
             return self._active_param._mod_range
        return 0.0

    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        return f"PitchController(mode={self._mode}, param='{self._active_param.name}')"    
