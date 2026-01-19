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

@dataclass(frozen=True)
class ParameterBounds:
    """
    Definisce i limiti di sicurezza per un parametro.
    
    Attributes:
        min_val: valore minimo ammesso
        max_val: valore massimo ammesso
        min_range: minimo per il parametro _range associato (default 0)
        max_range: massimo per il parametro _range associato (default 0)
    """
    min_val: float
    max_val: float
    min_range: float = 0.0
    max_range: float = 0.0


class ParameterEvaluator:
    """
    Gestisce parsing, valutazione e validazione dei parametri granulari.
    
    Centralizza tutte le costanti STREAM_MIN/MAX_* in un unico dizionario,
    rendendo facile aggiungere nuovi parametri o modificare i bounds.
    
    Example:
        evaluator = ParameterEvaluator("stream_1", duration=10.0)
        
        # Parsing da YAML
        density = evaluator.parse(yaml_data['density'], 'density')
        
        # Valutazione al tempo t
        value = evaluator.evaluate(density, elapsed_time=2.5, param_name='density')
        
        # Valutazione stocastica con Dephase (Probability Gate)
        # Applica deviazione +/- range solo se il "tiro di dadi" (probabilità 0-100) ha successo
        volume = evaluator.evaluate_gated_stochastic(
            param=self.volume,
            param_range=self.volume_range,
            prob_param=self.grain_volume_randomness,
            time=2.5,
            param_name='volume'
        )
    """
    
    # =========================================================================
    # BOUNDS CENTRALIZZATI
    # =========================================================================
    # Tutti i limiti di sicurezza in un unico posto.
    # Per aggiungere un nuovo parametro: aggiungi una riga qui.
    # 
    # Formato: 'nome_parametro': ParameterBounds(min, max, min_range, max_range)
    # =========================================================================
    
    BOUNDS: Dict[str, ParameterBounds] = {
        # --- Density ---
        'density': ParameterBounds(0.1, 4000.0, 0.0, 100.0),
        'fill_factor': ParameterBounds(0.001, 50.0, 0.0, 10.0),
        'distribution': ParameterBounds(0.0, 1.0),
        'effective_density': ParameterBounds(0.1, 4000.0),         
        
        # --- Grain ---
        'grain_duration': ParameterBounds(0.0001, 10.0, 0.0, 1.0),
        
        # --- Pitch ---
        'pitch_semitones': ParameterBounds(-36.0, 36.0, 0.0, 36.0),
        'pitch_ratio': ParameterBounds(0.125, 8.0, 0.0, 2.0),
        
        # --- Pointer ---
        'pointer_speed': ParameterBounds(-100.0, 100.0),
        'pointer_jitter': ParameterBounds(0.0, 10.0),
        'pointer_offset_range': ParameterBounds(0.0, 1.0),
        
        # --- Output ---
        'volume': ParameterBounds(-120.0, 12.0, 0.0, 12.0),
        'pan': ParameterBounds(-3600.0, 3600.0, 0.0, 360.0),
        
        # --- Voices ---
        'num_voices': ParameterBounds(1.0, 20.0),
        'voice_pitch_offset': ParameterBounds(0.0, 24.0),
        'voice_pointer_offset': ParameterBounds(0.0, 1.0),  # normalizzato, scalato runtime
        'voice_pointer_range': ParameterBounds(0.0, 1.0),   # normalizzato, scalato runtime

        # --- Dephase/Reverse ---
        'dephase_prob': ParameterBounds(0.0, 100.0),
        # --- Loop ---
        'loop_dur': ParameterBounds(0.001, 100.0),  # max dipende da sample, gestito runtime
    }
    
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
    
    def parse(self, param: Any, param_name: str = "parameter") -> Union[float, int, Envelope]:
        """
        Parsa un parametro da YAML in numero o Envelope.
        
        Gestisce automaticamente:
        - Numeri singoli → ritorna il numero
        - Lista di breakpoints → Envelope lineare
        - Dict con 'type' e 'points' → Envelope del tipo specificato
        - Normalizzazione temporale se time_mode='normalized'
        
        Args:
            param: valore dal YAML (numero, lista, o dict)
            param_name: nome del parametro (per messaggi di errore)
            
        Returns:
            numero o Envelope
            
        Raises:
            ValueError: se il formato non è riconosciuto
            
        Examples:
            >>> evaluator.parse(50, "density")
            50
            
            >>> evaluator.parse([[0, 20], [2, 100]], "density")
            Envelope(type=linear, points=[[0, 20], [2, 100]])
            
            >>> evaluator.parse({'type': 'cubic', 'points': [[0, 10], [1, 50]]}, "volume")
            Envelope(type=cubic, points=[[0, 10], [1, 50]])
        """
        # Caso 1: Numero singolo
        if isinstance(param, (int, float)):
            return param
        
        # Caso 2: Dict con type/points
        if isinstance(param, dict):
            return self._parse_dict_envelope(param, param_name)
        
        # Caso 3: Lista di breakpoints
        if isinstance(param, list):
            return self._parse_list_envelope(param, param_name)
        
        # Caso non gestito
        raise ValueError(
            f"{param_name}: formato non valido. "
            f"Atteso numero, lista, o dict. Ricevuto: {type(param).__name__}"
        )
    
    def _parse_dict_envelope(self, param: dict, param_name: str) -> Envelope:
        """Parsa un envelope da dict con gestione time_mode."""
        local_mode = param.get('time_unit')
        
        # Determina se normalizzare: locale > globale
        should_normalize = (
            local_mode == 'normalized' or 
            (local_mode is None and self.time_mode == 'normalized')
        )
        
        points = param.get('points', [])
        env_type = param.get('type', 'linear')
        
        if should_normalize:
            scaled_points = [[x * self.duration, y] for x, y in points]
            return Envelope({'type': env_type, 'points': scaled_points})
        
        return Envelope(param)
    
    def _parse_list_envelope(self, param: list, param_name: str) -> Envelope:
        """Parsa un envelope da lista con gestione time_mode."""
        if self.time_mode == 'normalized':
            scaled_points = [[x * self.duration, y] for x, y in param]
            return Envelope(scaled_points)
        
        return Envelope(param)

    def evaluate_gated_stochastic(self, 
                                  base_param, 
                                  range_param, 
                                  prob_param, 
                                  default_jitter: float,
                                  time: float, 
                                  param_name: str) -> float:
        """
        Valuta un parametro combinando Range e Dephase Probabilistico.
        
        Logica (Scenari):
        1. Dephase MANCANTE (None) -> Applica sempre il Range (Scenario A).
        2. Dephase PRESENTE:
           - Tira il dado (probabilità). Se fallisce -> Valore Base.
           - Se ha successo:
             a. Range > 0 -> Usa Range definito (Scenario C).
             b. Range == 0 -> Usa default_jitter (Scenario B).
        """
        bounds = self.BOUNDS.get(param_name)
        if bounds is None:
            raise ValueError(f"Bounds non definiti per '{param_name}'")

        # 1. Valuta Base
        base_value = self.evaluate(base_param, time, param_name)
        
        # 2. Valuta Range (serve comunque per capire se è 0)
        is_range_env = isinstance(range_param, Envelope)
        range_val = range_param.evaluate(time) if is_range_env else float(range_param)
        range_val = max(bounds.min_range, min(bounds.max_range, range_val))
        
        # 3. Logica Gated
        should_apply_variation = False
        
        if prob_param is None:
            # SCENARIO A: Dephase non definito -> Range sempre attivo
            should_apply_variation = True
        else:
            # SCENARIO B/C: Dephase definito -> Check probabilità
            # Nota: qui usiamo un nome fittizio per il log/bounds se necessario, 
            # oppure assumiamo bounds 0-100 standard
            prob_val = self.evaluate(prob_param, time, 'dephase_prob')
            if random_percent(prob_val):
                should_apply_variation = True
                
                # SCENARIO B: Gate aperto ma Range 0 -> Jitter automatico
                if range_val == 0.0:
                    range_val = default_jitter

        # 4. Applicazione
        if should_apply_variation and range_val > 0:
            deviation = random.uniform(-0.5, 0.5) * range_val
            final_value = base_value + deviation
            return max(bounds.min_val, min(bounds.max_val, final_value))
        
        return base_value

    def evaluate(self, param: Union[float, int, Envelope], time: float, 
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
    
    def evaluate_scaled(self, param: Union[float, int, Envelope], time: float,
                        param_name: str, scale: float) -> float:
        """
        Valuta un parametro con bounds scalati dinamicamente.
        
        Utile per parametri come voice_pointer_offset dove il max
        dipende dalla durata del sample.
        
        Args:
            param: valore da valutare
            time: tempo in secondi
            param_name: nome parametro per bounds base
            scale: fattore di scala per i bounds
            
        Returns:
            float: valore clippato ai bounds scalati
        """
        bounds = self.BOUNDS.get(param_name)
        if bounds is None:
            raise ValueError(f"Bounds non definiti per '{param_name}'")
        
        # Scala i bounds
        scaled_min = bounds.min_val * scale
        scaled_max = bounds.max_val * scale
        
        # Valuta
        is_envelope = isinstance(param, Envelope)
        value = param.evaluate(time) if is_envelope else float(param)
        
        # Clip
        clamped = max(scaled_min, min(scaled_max, value))
        
        if value != clamped:
            log_clip_warning(
                self.stream_id,
                f"{param_name}_scaled",
                time,
                value,
                clamped,
                scaled_min,
                scaled_max,
                is_envelope
            )
        
        return clamped
    
    def get_bounds(self, param_name: str) -> Optional[ParameterBounds]:
        """
        Ritorna i bounds per un parametro (utile per debug/visualizzazione).
        
        Args:
            param_name: nome del parametro
            
        Returns:
            ParameterBounds o None se non definito
        """
        return self.BOUNDS.get(param_name)
    
    def __repr__(self):
        return (f"ParameterEvaluator(stream_id='{self.stream_id}', "
                f"duration={self.duration}, time_mode='{self.time_mode}')")