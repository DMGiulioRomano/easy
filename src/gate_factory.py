"""
gate_factory.py - Factory isolata per creare ProbabilityGate.
Nessuna dipendenza da ParameterFactory o parser.
"""

from typing import Optional, Any, Union
from probability_gate import *
from enum import Enum
from envelope import Envelope, create_scaled_envelope

class DephaseMode(Enum):
    """Stati semantici di dephase."""
    DISABLED = "disabled"      # False - solo range espliciti
    IMPLICIT = "implicit"      # None - usa IMPLICIT_JITTER_PROB
    GLOBAL = "global"          # numero - probabilità globale
    SPECIFIC = "specific"      # dict - probabilità per chiave


class GateFactory:
    """
    Factory specializzata per creare ProbabilityGate.
    TOTALMENTE isolata dal sistema Parameter.
    """
    
    @staticmethod
    def _classify_dephase(dephase) -> DephaseMode:
        """Determina lo stato semantico di dephase."""
        if dephase is False:
            return DephaseMode.DISABLED
        elif dephase is None:
            return DephaseMode.IMPLICIT
        elif isinstance(dephase, (int, float)):
            return DephaseMode.GLOBAL
        elif isinstance(dephase, dict):
            return DephaseMode.SPECIFIC
        else:
            raise ValueError(f"dephase tipo invalido: {type(dephase)}")

    @staticmethod
    def create_gate(
        dephase: Optional[Union[dict, bool, int, float]] = False,
        param_key: Optional[str] = None,
        default_prob: float = 0.0,
        has_explicit_range: bool = False,
        range_always_active: bool = False,
        duration: float = 1.0,       
        time_mode: str = 'absolute'         
    ) -> ProbabilityGate:

        if param_key is None:
            return NeverGate()
        
        if has_explicit_range and range_always_active is None:
            return AlwaysGate()
        
        # Classifica lo stato
        mode = GateFactory._classify_dephase(dephase)
        
        # Logica basata sullo stato
        if mode == DephaseMode.DISABLED:
            return AlwaysGate() if has_explicit_range else NeverGate()
        
        elif mode == DephaseMode.IMPLICIT:
            return GateFactory._create_probability_gate(default_prob)
        
        elif mode == DephaseMode.GLOBAL:
            return GateFactory._create_probability_gate(float(dephase))
        
        elif mode == DephaseMode.SPECIFIC:
            if param_key in dephase:
                raw_value = dephase[param_key]
                if raw_value is None:
                    return GateFactory._create_probability_gate(default_prob)
                else:
                    return GateFactory._parse_raw_value(raw_value, duration, time_mode)
            else:
                return GateFactory._create_probability_gate(default_prob)
        
        return NeverGate()

    @staticmethod
    def _create_probability_gate(probability: float) -> ProbabilityGate:
        """
        Helper per creare gate da valore numerico.
        
        Evita di ripetere la logica 0→Never, 100→Always, altro→Random.
        """
        if probability <= 0:
            return NeverGate()
        elif probability >= 100:
            return AlwaysGate()
        else:
            return RandomGate(probability)

    @staticmethod
    def _parse_raw_value(raw_value: Any, duration: float, time_mode: str) -> ProbabilityGate:
        """..."""
        # Numero
        if isinstance(raw_value, (int, float)):
            prob = float(raw_value)
            if prob <= 0:
                return NeverGate()
            elif prob >= 100:
                return AlwaysGate()
            else:
                return RandomGate(prob)
        
        # Envelope (con gestione errori)
        if isinstance(raw_value, (list, dict)):
            try:
                from envelope import create_scaled_envelope
                envelope = create_scaled_envelope(raw_value, duration, time_mode)
                return EnvelopeGate(envelope)
            except Exception as e:
                # Envelope malformato - fallback con logging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Envelope dephase invalido: {raw_value}. "
                    f"Errore: {e}. Usando AlwaysGate (probabilità 100%) come fallback."
                )
                return AlwaysGate()
        
        # Tipo completamente sbagliato
        raise ValueError(
            f"Valore invalido per dephase: {raw_value} (tipo: {type(raw_value).__name__}). "
            f"Atteso numero (0-100), lista di punti [[t,v],...], o dict envelope."
        )