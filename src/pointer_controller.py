# src/pointer_controller.py
"""
PointerController - Gestione posizionamento testina di lettura

Estratto da Stream come parte del refactoring Fase 2.
Gestisce la posizione di lettura nel sample con:
- Movimento lineare con integrazione envelope
- Loop con phase accumulator per durata dinamica
- Deviazioni stocastiche (jitter, offset_range)

Ispirato al DMX-1000 di Barry Truax (1988)
"""

from typing import Union, Optional, Callable
import random
from envelope import Envelope
from parameter_evaluator import ParameterEvaluator


class PointerController:
    """
    Gestisce il posizionamento della testina di lettura nel sample.
    
    Responsabilità:
    - Parsing parametri pointer da YAML
    - Movimento lineare (velocità costante o envelope)
    - Loop con phase accumulator (gestisce durata dinamica)
    - Deviazioni stocastiche (jitter micro, offset_range macro)
    
    Il controller usa un ParameterEvaluator per:
    - parse(): conversione YAML → numero/Envelope
    - evaluate(): valutazione con bounds safety
    
    Usage:
        evaluator = ParameterEvaluator("stream1", duration, time_mode)
        pointer = PointerController(params['pointer'], evaluator, sample_dur_sec, time_mode)
        
        # Nel loop di generazione grani:
        position = pointer.calculate(elapsed_time)
    """
    
    def __init__(
        self,
        params: dict,
        evaluator: ParameterEvaluator,
        sample_dur_sec: float,
        time_mode: str = 'absolute'
    ):
        """
        Inizializza il controller.
        
        Args:
            params: dict con configurazione pointer da YAML
            evaluator: ParameterEvaluator per parsing e valutazione
            sample_dur_sec: durata del sample in secondi
            time_mode: 'absolute' o 'normalized' (default per envelope)
        """
        self._evaluator = evaluator
        self._sample_dur_sec = sample_dur_sec
        self._time_mode = time_mode
        
        self._init_params(params)
        self._init_loop_state()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def _init_params(self, params: dict) -> None:
        """
        Inizializza parametri pointer dal dict YAML.
        
        Parametri:
        - start: posizione iniziale (secondi)
        - speed: velocità di scansione (supporta Envelope)
        - jitter: micro-variazione bipolare (0.001-0.01 sec tipico)
        - offset_range: macro-variazione bipolare (0-1, normalizzato su durata)
        - loop_start: inizio loop (opzionale, secondi) - FISSO
        - loop_end: fine loop (opzionale) - FISSO (mutualmente esclusivo con loop_dur)
        - loop_dur: durata loop (opzionale) - SUPPORTA ENVELOPE
        """
        # --- Parametri base ---
        self.start = params.get('start', 0.0)
        self.speed = self._evaluator.parse(params.get('speed', 1.0), "pointer.speed")
        self.jitter = self._evaluator.parse(params.get('jitter', 0.0), "pointer.jitter")
        self.offset_range = self._evaluator.parse(params.get('offset_range', 0.0), "pointer.offset_range")
        
        # --- Loop configuration ---
        self._init_loop_params(params)
    
    def _init_loop_params(self, params: dict) -> None:
        """
        Inizializza parametri loop con supporto per normalizzazione.
        
        Modalità:
        1. loop_start + loop_end: bounds fissi (legacy)
        2. loop_start + loop_dur: durata dinamica (può essere Envelope)
        3. loop_start solo: loop fino a fine sample
        """
        raw_start = params.get('loop_start')
        raw_end = params.get('loop_end')
        raw_dur = params.get('loop_dur')
        
        if raw_start is not None:
            # Determina scala per normalizzazione
            loop_mode = params.get('loop_unit') or self._time_mode
            scale = self._sample_dur_sec if loop_mode == 'normalized' else 1.0
            
            # loop_start è SEMPRE fisso
            self.loop_start = raw_start * scale
            
            if raw_end is not None:
                # Modalità loop_end FISSO (legacy)
                self.loop_end = raw_end * scale
                self.loop_dur = None
                
            elif raw_dur is not None:
                # Modalità loop_dur (può essere Envelope!)
                self.loop_end = None
                self.loop_dur = self._parse_scaled_loop_dur(raw_dur, scale, loop_mode)
                
            else:
                # Solo loop_start → loop fino a fine sample
                self.loop_end = self._sample_dur_sec
                self.loop_dur = None
            
            self.has_loop = True
        else:
            # Nessun loop configurato
            self.loop_start = None
            self.loop_end = None
            self.loop_dur = None
            self.has_loop = False
    
    def _parse_scaled_loop_dur(
        self,
        raw_dur,
        scale: float,
        loop_mode: str
    ) -> Union[float, Envelope]:
        """
        Parsa loop_dur con scaling per modalità normalizzata.
        
        Se loop_dur è un Envelope e loop_mode è 'normalized',
        scala i valori Y dei breakpoints.
        """
        if isinstance(raw_dur, (int, float)):
            return raw_dur * scale
        
        # È un envelope/lista - scala i valori Y se normalized
        if loop_mode == 'normalized':
            if isinstance(raw_dur, dict):
                scaled_points = [[x, y * scale] for x, y in raw_dur['points']]
                raw_dur = {
                    'type': raw_dur.get('type', 'linear'),
                    'points': scaled_points
                }
            elif isinstance(raw_dur, list):
                raw_dur = [[x, y * scale] for x, y in raw_dur]
        
        return self._evaluator.parse(raw_dur, "pointer.loop_dur")
    
    def _init_loop_state(self) -> None:
        """Inizializza stato del phase accumulator per loop."""
        self._in_loop = False
        self._loop_phase = 0.0           # Fase nel loop (0.0 - 1.0)
        self._last_linear_pos = None     # Per calcolare delta movimento
    
    # =========================================================================
    # MAIN CALCULATION
    # =========================================================================
    
    def calculate(self, elapsed_time: float) -> float:
        """
        Calcola la posizione di lettura nel sample per questo grano.
        
        Usa Phase Accumulator per loop con durata dinamica (envelope).
        La fase si accumula incrementalmente, evitando salti quando
        loop_length cambia.
        
        Args:
            elapsed_time: secondi trascorsi dall'onset dello stream
            
        Returns:
            float: posizione in secondi nel sample sorgente
        """
        # 1. Calcola movimento lineare (da speed)
        linear_pos = self._calculate_linear_position(elapsed_time)
        
        # 2. Applica loop se configurato
        if self.has_loop:
            base_pos, context_length, wrap_fn = self._apply_loop(linear_pos, elapsed_time)
        else:
            # Nessun loop: wrap semplice sul buffer
            base_pos = linear_pos % self._sample_dur_sec
            context_length = self._sample_dur_sec
            wrap_fn = lambda p: p % self._sample_dur_sec
        
        # 3. Deviazioni stocastiche
        final_pos = self._apply_stochastic_deviations(
            base_pos, context_length, elapsed_time, wrap_fn
        )
        
        return final_pos
    
    def _calculate_linear_position(self, elapsed_time: float) -> float:
        """
        Calcola posizione lineare da speed (con integrazione per envelope).
        
        Se speed è un Envelope, integra per ottenere la posizione.
        Altrimenti: position = start + time * speed
        """
        if isinstance(self.speed, Envelope):
            sample_position = self.speed.integrate(0, elapsed_time)
        else:
            sample_position = elapsed_time * self.speed
        
        return self.start + sample_position
    

    def _apply_loop(
        self,
        linear_pos: float,
        elapsed_time: float
    ) -> tuple[float, float, Callable[[float], float]]:
        """
        Applica logica loop con phase accumulator.
        
        Returns:
            tuple: (base_pos, context_length, wrap_function)
        """
        # Calcola loop bounds correnti
        current_loop_start = self.loop_start
        
        if self.loop_dur is not None:
            # loop_dur dinamico (può essere Envelope)
            current_loop_dur = self._evaluator.evaluate(
                self.loop_dur, elapsed_time, 'loop_dur'
            )
            # Limita al massimo della durata del sample
            current_loop_dur = min(current_loop_dur, self._sample_dur_sec)
        else:
            # loop_end fisso (legacy)
            current_loop_dur = self.loop_end - self.loop_start
        
        current_loop_end = min(current_loop_start + current_loop_dur, self._sample_dur_sec)
        loop_length = max(current_loop_end - current_loop_start, 0.001)
        
        # Phase accumulator logic
        if not self._in_loop:
            # Check entrata nel loop
            check_pos = linear_pos % self._sample_dur_sec
            if current_loop_start <= check_pos < current_loop_end:
                self._in_loop = True
                # Inizializza fase: posizione relativa nel loop (0-1)
                self._loop_phase = (check_pos - current_loop_start) / loop_length
                self._last_linear_pos = linear_pos
        
        if self._in_loop:
            # Calcola delta movimento dall'ultimo grano
            if self._last_linear_pos is not None:
                delta_pos = linear_pos - self._last_linear_pos
                # Converti in incremento di fase (normalizzato su loop corrente)
                delta_phase = delta_pos / loop_length
                self._loop_phase += delta_phase
                
                # Wrap fase (gestisce anche speed negativi e multi-giri)
                self._loop_phase = self._loop_phase % 1.0
            
            self._last_linear_pos = linear_pos
            
            # Converti fase in posizione assoluta
            base_pos = current_loop_start + self._loop_phase * loop_length
            context_length = loop_length
            
            # Wrap function per deviazioni stocastiche
            def wrap_fn(pos: float) -> float:
                rel = pos - current_loop_start
                return current_loop_start + (rel % loop_length)
        else:
            # Prima del loop: wrap sul buffer intero
            base_pos = linear_pos % self._sample_dur_sec
            context_length = self._sample_dur_sec
            wrap_fn = lambda p: p % self._sample_dur_sec
        
        return base_pos, context_length, wrap_fn
    
    def _apply_stochastic_deviations(
        self,
        base_pos: float,
        context_length: float,
        elapsed_time: float,
        wrap_fn: Callable[[float], float]
    ) -> float:
        """
        Applica deviazioni stocastiche (jitter + offset_range).
        
        - jitter: micro-variazione bipolare in secondi
        - offset_range: macro-variazione normalizzata su context_length
        """
        jitter_amount = self._evaluator.evaluate(
            self.jitter, elapsed_time, 'pointer_jitter'
        )
        offset_range_amount = self._evaluator.evaluate(
            self.offset_range, elapsed_time, 'pointer_offset_range'
        )
        
        jitter_deviation = random.uniform(-jitter_amount, jitter_amount)
        offset_deviation = random.uniform(-0.5, 0.5) * offset_range_amount * context_length
        
        # Posizione finale con wrap
        final_pos = base_pos + jitter_deviation + offset_deviation
        return wrap_fn(final_pos)
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def reset(self) -> None:
        """Resetta lo stato del loop (per riuso del controller)."""
        self._init_loop_state()

    def get_speed(self, elapsed_time: float) -> float:
        """
        Ritorna la velocità istantanea al tempo specificato.
        Utile per determinare la direzione (reverse) in Stream.
        """
        if isinstance(self.speed, Envelope):
            return self.speed.evaluate(elapsed_time)
        return float(self.speed)
    
    # =========================================================================
    # PROPERTIES (Read-only access)
    # =========================================================================
    
    @property
    def sample_dur_sec(self) -> float:
        """Durata del sample in secondi."""
        return self._sample_dur_sec
    
    @property
    def in_loop(self) -> bool:
        """True se attualmente nel loop."""
        return self._in_loop
    
    @property
    def loop_phase(self) -> float:
        """Fase corrente nel loop (0.0 - 1.0)."""
        return self._loop_phase
    
    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        loop_info = f", loop={self.loop_start:.3f}-{self.loop_end or 'dynamic'}" if self.has_loop else ""
        return f"PointerController(start={self.start}, speed={self.speed}{loop_info})"