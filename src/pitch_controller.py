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

from typing import Union
import random
from envelope import Envelope
from parameter_evaluator import ParameterEvaluator


class PitchController:
    """
    Gestisce la trasposizione del pitch per i grani.
    
    Responsabilità:
    - Parsing parametri pitch da YAML
    - Due modalità: semitoni (shift_semitones) o ratio diretto
    - Deviazione stocastica basata su range
    - Conversione finale in ratio
    
    Il controller usa un ParameterEvaluator per:
    - parse(): conversione YAML → numero/Envelope
    - evaluate(): valutazione con bounds safety
    - evaluate_with_range(): valutazione con deviazione stocastica
    
    Usage:
        evaluator = ParameterEvaluator("stream1", duration, time_mode)
        pitch = PitchController(params['pitch'], evaluator)
        
        # Nel loop di generazione grani:
        ratio = pitch.calculate(elapsed_time)
    """
    
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
            
        Examples:
            >>> PitchController.semitones_to_ratio(0)
            1.0
            >>> PitchController.semitones_to_ratio(12)
            2.0
            >>> PitchController.semitones_to_ratio(-12)
            0.5
        """
        return pow(2.0, semitones / 12.0)
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def __init__(
        self,
        params: dict,
        evaluator: ParameterEvaluator
    ):
        """
        Inizializza il controller.
        
        Args:
            params: dict con configurazione pitch da YAML (sotto 'pitch' key)
            evaluator: ParameterEvaluator per parsing e valutazione
        """
        self._evaluator = evaluator
        self._init_params(params)
    
    def _init_params(self, params: dict) -> None:
        """
        Inizializza parametri pitch dal dict YAML.
        
        Due modalità mutuamente esclusive:
        1. SEMITONI: se 'shift_semitones' presente → converte a ratio alla fine
        2. RATIO: altrimenti → usa ratio direttamente (default 1.0)
        
        In entrambe le modalità, 'range' applica deviazione stocastica.
        """
        if 'shift_semitones' in params:
            # === Modalità SEMITONI ===
            self._mode = 'semitones'
            self._base_semitones = self._evaluator.parse(
                params['shift_semitones'], 
                'pitch.shift_semitones'
            )
            self._base_ratio = None  # marker: usa semitoni
        else:
            # === Modalità RATIO (default) ===
            self._mode = 'ratio'
            self._base_ratio = self._evaluator.parse(
                params.get('ratio', 1.0),
                'pitch.ratio'
            )
            self._base_semitones = None
        
        # Range: sempre presente, interpretazione dipende dalla modalità
        self._range = self._evaluator.parse(
            params.get('range', 0.0),
            'pitch.range'
        )
    
    # =========================================================================
    # CALCULATION
    # =========================================================================
    
    def calculate(self, elapsed_time: float) -> float:
        """
        Calcola pitch ratio al tempo specificato.
        
        Applica la logica appropriata in base alla modalità:
        - Semitoni: valuta semitoni base + range, converte a ratio
        - Ratio: valuta ratio base + range (opzionale conversione semitoni)
        
        Args:
            elapsed_time: tempo relativo all'onset dello stream
            
        Returns:
            float: pitch ratio finale (sempre > 0)
        """
        if self._mode == 'semitones':
            return self._calculate_semitones_mode(elapsed_time)
        else:
            return self._calculate_ratio_mode(elapsed_time)
    
    def _calculate_semitones_mode(self, elapsed_time: float) -> float:
        """
        Calcola pitch in modalità semitoni.
        
        1. Valuta semitoni base dall'envelope
        2. Valuta range (in semitoni)
        3. Applica deviazione stocastica
        4. Converte a ratio
        """
        # Base semitones
        base_semitones = self._evaluator.evaluate(
            self._base_semitones,
            elapsed_time,
            'pitch_semitones'
        )
        
        # Range (in semitoni) - usa i bounds del range semitoni
        # Nota: usiamo i bounds min_range/max_range di pitch_semitones
        bounds = self._evaluator.get_bounds('pitch_semitones')
        is_envelope = isinstance(self._range, Envelope)
        range_value = self._range.evaluate(elapsed_time) if is_envelope else float(self._range)
        range_value = max(bounds.min_range, min(bounds.max_range, range_value))
        
        # Deviazione stocastica (intero per semitoni, come nell'originale)
        pitch_deviation = random.randint(
            int(-range_value * 0.5), 
            int(range_value * 0.5)
        )
        
        final_semitones = base_semitones + pitch_deviation
        return self.semitones_to_ratio(final_semitones)
    
    def _calculate_ratio_mode(self, elapsed_time: float) -> float:
        """
        Calcola pitch in modalità ratio diretta.
        
        1. Valuta ratio base dall'envelope
        2. Se range > 0: applica deviazione (in ratio, non semitoni)
        3. Ritorna ratio finale
        """
        # Base ratio
        base_ratio = self._evaluator.evaluate(
            self._base_ratio,
            elapsed_time,
            'pitch_ratio'
        )
        
        # Range (in ratio)
        bounds = self._evaluator.get_bounds('pitch_ratio')
        is_envelope = isinstance(self._range, Envelope)
        range_value = self._range.evaluate(elapsed_time) if is_envelope else float(self._range)
        range_value = max(bounds.min_range, min(bounds.max_range, range_value))
        
        if range_value > 0:
            pitch_deviation = random.uniform(-0.5, 0.5) * range_value
            return base_ratio + pitch_deviation
        else:
            return base_ratio
    
    # =========================================================================
    # PROPERTIES (Read-only access)
    # =========================================================================
    
    @property
    def mode(self) -> str:
        """Modalità corrente: 'semitones' o 'ratio'."""
        return self._mode
    
    @property
    def base_semitones(self) -> Union[float, Envelope, None]:
        """Valore base semitoni (None se in modalità ratio)."""
        return self._base_semitones
    
    @property
    def base_ratio(self) -> Union[float, Envelope, None]:
        """Valore base ratio (None se in modalità semitoni)."""
        return self._base_ratio
    
    @property
    def range(self) -> Union[float, Envelope]:
        """Valore range per deviazione stocastica."""
        return self._range
    
    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        if self._mode == 'semitones':
            base_info = f"semitones={self._base_semitones}"
        else:
            base_info = f"ratio={self._base_ratio}"
        
        range_info = f", range={self._range}" if self._range != 0 else ""
        return f"PitchController({base_info}{range_info})"