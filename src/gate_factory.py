"""
gate_factory.py - Factory isolata per creare ProbabilityGate.
Nessuna dipendenza da ParameterFactory o parser.
"""

from typing import Optional, Any, Union
from probability_gate import *
from enum import Enum


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
        range_always_active: bool = False 
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
                    return GateFactory._parse_raw_value(raw_value)
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
    def _parse_raw_value(raw_value: Any) -> ProbabilityGate:
        """
        Converte un valore grezzo in ProbabilityGate.
        """
        # 4a: Numero (0-100)
        if isinstance(raw_value, (int, float)):
            prob = float(raw_value)
            if prob <= 0:
                return NeverGate()
            if prob >= 100:
                return AlwaysGate()
            return RandomGate(prob)
        
        # 4b: Envelope (lista o dict)
        # NOTA: Qui NON usiamo ParameterFactory! Usiamo direttamente Envelope
        # Se c'è envelope, significa che l'utente vuole variazioni temporali
        try:
            # Import locale per evitare dipendenze circolari
            from envelope import Envelope
            envelope = Envelope(raw_value)
            return EnvelopeGate(envelope)
        except Exception as e:
            # Fallback: se envelope non valido, usiamo 100%
            print(f"⚠️  Envelope invalido per gate: {e}, usando AlwaysGate")
            return AlwaysGate()
    