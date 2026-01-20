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
    default_jitter: float = 0.0


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

    # Probabilità di default per il sistema dephase (1%)
    # Usato quando 'dephase:' è presente ma la probabilità specifica non è definita
    DEFAULT_DEPHASE_PROB = 1.0

    # =========================================================================
    # BOUNDS CENTRALIZZATI
    # =========================================================================
    # Tutti i limiti di sicurezza in un unico posto.
    # Per aggiungere un nuovo parametro: aggiungi una riga qui.
    # 
    # Formato: 'nome_parametro': ParameterBounds(min, max, min_range, max_range)
    # =========================================================================
    
@dataclass(frozen=True)
class ParameterBounds:
    """
    Definisce i limiti di sicurezza per un parametro.
    
    Attributes:
        min_val: valore minimo ammesso
        max_val: valore massimo ammesso
        min_range: minimo per il parametro _range associato (default 0)
        max_range: massimo per il parametro _range associato (default 0)
        default_jitter: jitter di fallback quando dephase attivo ma range=0
    """
    min_val: float
    max_val: float
    min_range: float = 0.0
    max_range: float = 0.0
    default_jitter: float = 0.0  # ← NUOVO


class ParameterEvaluator:
    """
    Gestisce parsing, valutazione e validazione dei parametri granulari.
    
    Centralizza tutte le costanti STREAM_MIN/MAX_* in un unico dizionario,
    rendendo facile aggiungere nuovi parametri o modificare i bounds.
    """
    
    # =========================================================================
    # COSTANTI DI SISTEMA
    # =========================================================================
    
    # Probabilità di default per il sistema dephase (1%)
    # Usato quando 'dephase:' è presente ma la probabilità specifica non è definita
    DEFAULT_DEPHASE_PROB = 1.0
    
    # =========================================================================
    # BOUNDS CENTRALIZZATI
    # =========================================================================
    # Tutti i limiti di sicurezza in un unico posto.
    # Per aggiungere un nuovo parametro: aggiungi una riga qui.
    # 
    # Formato: 'nome_parametro': ParameterBounds(
    #     min_val, max_val, min_range, max_range, default_jitter
    # )
    # =========================================================================
    
    BOUNDS: Dict[str, ParameterBounds] = {
        # =====================================================================
        # DENSITY
        # =====================================================================
        'density': ParameterBounds(
            min_val=0.1,
            max_val=4000.0,
            min_range=0.0,
            max_range=100.0,
            default_jitter=50.0  # ~50 grani/s di variazione implicita
        ),
        'fill_factor': ParameterBounds(
            min_val=0.001,
            max_val=50.0,
            min_range=0.0,
            max_range=10.0
        ),
        'distribution': ParameterBounds(
            min_val=0.0,
            max_val=1.0
        ),
        'effective_density': ParameterBounds(
            min_val=0.1,
            max_val=4000.0
        ),
        
        # =====================================================================
        # GRAIN
        # =====================================================================
        'grain_duration': ParameterBounds(
            min_val=0.0001,
            max_val=10.0,
            min_range=0.0,
            max_range=1.0,
            default_jitter=0.01  # 10ms di variazione implicita
        ),
        
        # =====================================================================
        # PITCH
        # =====================================================================
        'pitch_semitones': ParameterBounds(
            min_val=-36.0,
            max_val=36.0,
            min_range=0.0,
            max_range=36.0,
            default_jitter=0.5  # ~mezzo semitono di microtuning
        ),
        'pitch_ratio': ParameterBounds(
            min_val=0.125,
            max_val=8.0,
            min_range=0.0,
            max_range=2.0,
            default_jitter=0.02  # ~2% variazione ratio
        ),
        
        # =====================================================================
        # POINTER
        # =====================================================================
        'pointer_speed': ParameterBounds(
            min_val=-100.0,
            max_val=100.0
        ),
        'pointer_jitter': ParameterBounds(
            min_val=0.0,
            max_val=10.0
        ),
        'pointer_offset_range': ParameterBounds(
            min_val=0.0,
            max_val=1.0
        ),
        
        # =====================================================================
        # OUTPUT (Volume, Pan)
        # =====================================================================
        'volume': ParameterBounds(
            min_val=-120.0,
            max_val=12.0,
            min_range=0.0,
            max_range=24.0,
            default_jitter=1.5  # ±0.75 dB di variazione implicita
        ),
        'pan': ParameterBounds(
            min_val=-3600.0,
            max_val=3600.0,
            min_range=0.0,
            max_range=360.0,
            default_jitter=15.0  # ±7.5° di variazione implicita
        ),
        
        # =====================================================================
        # VOICES
        # =====================================================================
        'num_voices': ParameterBounds(
            min_val=1.0,
            max_val=20.0
        ),
        'voice_pitch_offset': ParameterBounds(
            min_val=0.0,
            max_val=24.0
        ),
        'voice_pointer_offset': ParameterBounds(
            min_val=0.0,
            max_val=1.0  # Normalizzato, scalato runtime con sample_dur
        ),
        'voice_pointer_range': ParameterBounds(
            min_val=0.0,
            max_val=1.0  # Normalizzato, scalato runtime con sample_dur
        ),
        
        # =====================================================================
        # DEPHASE / REVERSE
        # =====================================================================
        'dephase_prob': ParameterBounds(
            min_val=0.0,
            max_val=100.0
        ),
        
        # =====================================================================
        # LOOP
        # =====================================================================
        'loop_dur': ParameterBounds(
            min_val=0.001,
            max_val=100.0  # Max dipende da sample, gestito runtime
        ),
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

    def parse_dephase_param(self, value) -> Union[float, Envelope]:
        """
        Parsa un parametro dephase, applicando DEFAULT_DEPHASE_PROB se non specificato.
        
        Centralizza la logica:
        - Se value è definito → parse normale con bounds 'dephase_prob'
        - Se value è None → ritorna DEFAULT_DEPHASE_PROB
        
        Args:
            value: valore dal YAML (numero, lista breakpoints, o None)
            
        Returns:
            float o Envelope: probabilità parsata o default
            
        Example:
            # Nel YAML: pc_rand_volume: 50
            prob = evaluator.parse_dephase_param(50)  # → 50.0
            
            # Nel YAML: pc_rand_volume non presente
            prob = evaluator.parse_dephase_param(None)  # → 1.0 (default)
            
            # Nel YAML: pc_rand_volume: [[0, 0], [10, 100]]
            prob = evaluator.parse_dephase_param([[0, 0], [10, 100]])  # → Envelope
        """
        if value is not None:
            return self.parse(value, 'dephase_prob')
        return self.DEFAULT_DEPHASE_PROB

    def evaluate_gated_stochastic(self, 
                                base_param, 
                                range_param, 
                                prob_param, 
                                time: float, 
                                param_name: str) -> float:
        """
        Valuta un parametro combinando Range e Dephase Probabilistico.
        
        Logica (Scenari):
        A. Dephase MANCANTE (None) -> Applica sempre il Range
        B. Dephase PRESENTE, Range == 0 -> Usa default_jitter dai BOUNDS
        C. Dephase PRESENTE, Range > 0 -> Usa Range come gate probabilistico
        
        Args:
            base_param: valore base (numero o Envelope)
            range_param: range di variazione (numero o Envelope)
            prob_param: probabilità dephase 0-100 (numero, Envelope, o None)
            time: tempo in secondi
            param_name: nome parametro per lookup BOUNDS
            
        Returns:
            float: valore finale clippato ai bounds
            
        Raises:
            ValueError: se param_name non ha bounds definiti
        """
        # 1. Recupera i bounds (che ora contengono tutto)
        bounds = self.BOUNDS.get(param_name)
        if bounds is None:
            raise ValueError(f"Bounds non definiti per '{param_name}'")
        
        # 2. Valuta Base
        base_value = self.evaluate(base_param, time, param_name)
        
        # 3. Valuta Range
        is_range_env = isinstance(range_param, Envelope)
        range_val = range_param.evaluate(time) if is_range_env else float(range_param)
        range_val = max(bounds.min_range, min(bounds.max_range, range_val))
        
        # 4. Logica Gated
        should_apply_variation = False
        
        if prob_param is None:
            # SCENARIO A: Dephase non definito -> Range sempre attivo
            should_apply_variation = True
        else:
            # SCENARIO B/C: Dephase definito -> Check probabilità
            prob_val = self.evaluate(prob_param, time, 'dephase_prob')
            if random_percent(prob_val):
                should_apply_variation = True
                
                # SCENARIO B: Gate aperto ma Range 0 -> Jitter dai bounds
                if range_val == 0.0:
                    range_val = bounds.default_jitter
        
        # 5. Applicazione variazione
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