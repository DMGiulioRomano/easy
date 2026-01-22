"""
parameter.py

Definisce la classe Smart Parameter (Model).
Questa classe incapsula il valore (statico o Envelope), i bounds di sicurezza
e la logica di variazione stocastica (Randomness).

Utilizza un approccio 'Functional Strategy' (Dispatch Dictionary) per gestire 
le diverse modalità di variazione ('additive', 'quantized', 'invert') senza 
usare catene di if/elif, garantendo estensibilità e pulizia.
"""

import random
from typing import Union, Optional, Callable, Dict
from envelope import Envelope
from parameter_definitions import ParameterBounds
from logger import log_clip_warning

# Definiamo un tipo alias per chiarezza: l'input può essere un numero o un Envelope
ParamInput = Union[float, int, Envelope]

class Parameter:
    """
    Rappresenta un parametro granulare "intelligente".
    
    Sa calcolare il proprio valore al tempo T, gestendo automaticamente:
    1. Interpolazione Envelope (se presente)
    2. Variazione Stocastica (Range/Jitter) con diverse strategie
    3. Probabilità di attivazione (Dephase)
    4. Safety Clamping (rispetto ai Bounds)
    """

    def __init__(
        self,
        name: str,                       # Identità del parametro (obbligatorio)
        value: ParamInput,               # Valore base (numero o Envelope)
        bounds: ParameterBounds,         # Regole di validazione (Schema)
        mod_range: Optional[ParamInput] = None,  # Ampiezza random
        mod_prob: Optional[ParamInput] = None,   # Probabilità random (0-100)
        owner_id: str = "unknown"        # ID dello stream per i log
    ):
        self.name = name
        self.owner_id = owner_id
        
        self._value = value
        self._bounds = bounds
        self._mod_range = mod_range
        self._mod_prob = mod_prob
        
        # Strategy Map: Collega la modalità di variazione alla funzione corrispondente.
        # Questo elimina l'if/elif nel metodo get_value.
        self._strategies: Dict[str, Callable[[float, float], float]] = {
            'additive': self._strategy_additive,
            'quantized': self._strategy_quantized,
            'invert': self._strategy_invert
        }
        
        # Validazione immediata della configurazione (Fail Fast)
        if self._bounds.variation_mode not in self._strategies:
            raise ValueError(
                f"Parametro '{self.name}': Unknown variation_mode '{self._bounds.variation_mode}' "
                f"definito in parameter_definitions.py"
            )

    def get_value(self, time: float) -> float:
        """
        Calcola il valore finale del parametro al tempo specificato.
        Questo è l'unico metodo che il mondo esterno deve chiamare.
        """
        
        # 1. Valuta il valore base (Base Signal)
        base_val = self._evaluate_input(self._value, time)

        # 2. Check Probabilità (Gate)
        # Se il gate è chiuso, restituisci subito il base value (clippato)
        if not self._check_probability(time):
            return self._clamp(base_val, time)

        # 3. Calcola il Range di variazione (Modulation Depth)
        current_range = self._calculate_range(time)

        # 4. Esegui la Strategia di Variazione (Dispatch)
        # Seleziona la funzione giusta in base alla configurazione (es. 'quantized' per semitoni)
        strategy_func = self._strategies[self._bounds.variation_mode]
        final_val = strategy_func(base_val, current_range)

        # 5. Safety Clamp e Ritorno
        return self._clamp(final_val, time)

    # =========================================================================
    # STRATEGIE DI VARIAZIONE (Private)
    # =========================================================================

    def _strategy_additive(self, base: float, rng: float) -> float:
        """
        Variazione continua: base ± random(rng/2).
        Usata per: Volume, Pan, Duration, Density, Ratio.
        """
        if rng > 0:
            return base + random.uniform(-0.5, 0.5) * rng
        return base

    def _strategy_quantized(self, base: float, rng: float) -> float:
        """
        Variazione discreta (interi): base ± randint(rng/2).
        Usata per: Pitch Semitones, Voices, Sample Select.
        """
        if rng >= 1.0:
            limit = int(rng * 0.5)
            if limit > 0:
                # randint è inclusivo [-limit, limit]
                return base + random.randint(-limit, limit)
        return base

    def _strategy_invert(self, base: float, rng: float) -> float:
        """
        Variazione booleana: inverte 0.0 <-> 1.0.
        Usata per: Reverse.
        Ignora il parametro 'rng' perché comandata solo dalla probabilità.
        """
        return 1.0 - base

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _evaluate_input(self, param: Optional[ParamInput], time: float) -> float:
        """Helper: Estrae il valore numerico da un numero o da un Envelope."""
        if param is None:
            return 0.0
        if isinstance(param, Envelope):
            return param.evaluate(time)
        return float(param)

    def _check_probability(self, time: float) -> bool:
        """
        Verifica se applicare la variazione (Gate probabilistico).
        Ritorna True se la variazione DEVE essere applicata.
        """
        # Se mod_prob non è definito nello YAML:
        if self._mod_prob is None:
            # Per 'invert' (Reverse): Default è OFF (False) -> non invertire.
            if self._bounds.variation_mode == 'invert':
                return False
            # Per 'additive'/'quantized': Default è ON (True) -> applica sempre il range.
            return True
        
        # Se mod_prob è definito, valuta la probabilità (0-100)
        prob_val = self._evaluate_input(self._mod_prob, time)
        return random.uniform(0, 100) < prob_val

    def _calculate_range(self, time: float) -> float:
        """Calcola l'ampiezza della variazione."""
        # Scenario B: Se l'utente non ha messo range, usa il default (Jitter implicito)
        if self._mod_range is None:
            return self._bounds.default_jitter
        
        val = self._evaluate_input(self._mod_range, time)
        
        # Limita il range stesso ai bounds di validità definiti per il range
        return max(self._bounds.min_range, min(self._bounds.max_range, val))

    def _clamp(self, value: float, time: float) -> float:
        """Applica i limiti di sicurezza (Min/Max) e logga se taglia."""
        clamped = max(self._bounds.min_val, min(self._bounds.max_val, value))
        
        if clamped != value:
            # Logga il warning usando il logger configurato
            log_clip_warning(
                stream_id=self.owner_id,
                param_name=self.name,
                time=time,
                raw_value=value,
                clipped_value=clamped,
                min_val=self._bounds.min_val,
                max_val=self._bounds.max_val,
                is_envelope=isinstance(self._value, Envelope)
            )
        
        return clamped

    @property
    def value(self):
        """
        Restituisce il valore base grezzo (float o Envelope).
        Utile per ispezione o logica condizionale (es. integrazione analitica).
        """
        return self._value

    def __repr__(self):
        """Rappresentazione stringa per debug."""
        val_str = "Env" if isinstance(self._value, Envelope) else f"{self._value:.2f}"
        return f"<Param '{self.name}': {val_str} (Mode: {self._bounds.variation_mode})>"