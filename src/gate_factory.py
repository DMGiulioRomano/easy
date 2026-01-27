"""
gate_factory.py - Factory isolata per creare ProbabilityGate.
Nessuna dipendenza da ParameterFactory o parser.
"""

from typing import Optional, Any, Union
from probability_gate import *

class GateFactory:
    """
    Factory specializzata per creare ProbabilityGate.
    TOTALMENTE isolata dal sistema Parameter.
    """
    

    @staticmethod
    def create_gate(
        dephase_config: Optional[dict] = None,
        param_key: Optional[str] = None,
        default_prob: float = 0.0,
        has_explicit_range: bool = False  # ← NUOVO!
    ) -> ProbabilityGate:
        # CASO 1: Parametro non supporta dephase
        if param_key is None:
            return NeverGate()

        # CASO 2: Nessuna configurazione dephase
        if dephase_config is None:
            # Se range esplicitato → 100%
            if has_explicit_range:
                return AlwaysGate()
            # Se range NON esplicitato → 0%
            return NeverGate()
            
        # CASO 3: dephase config esiste, cerca chiave        
        if param_key not in dephase_config:
            # Se range esplicitato → 100%
            if has_explicit_range:
                return AlwaysGate()
            # Chiave mancante, range non esplicitato → implicit jitter
            if default_prob > 0:
                return RandomGate(default_prob)
            return NeverGate()
        

        raw_value = dephase_config[param_key]
        
        # CASO 4: Chiave presente ma valore è None → implicit jitter
        if raw_value is None:
            if default_prob > 0:
                return RandomGate(default_prob)
            return NeverGate()
        
        # CASO 5: Valore esplicito
        return GateFactory._parse_raw_value(raw_value)

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
    
    @staticmethod
    def create_implicit_gate() -> ProbabilityGate:
        """
        Crea gate per jitter implicito (Scenario B: dephase presente ma senza range).
        Usa la probabilità di default dal sistema (es. 1%).
        """
        from parameter_definitions import IMPLICIT_JITTER_PROB
        return RandomGate(IMPLICIT_JITTER_PROB)