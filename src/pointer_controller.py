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
from parameter_factory import ParameterFactory
from parameter import Parameter
from parameter_schema import POINTER_PARAMETER_SCHEMA, get_parameter_spec

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
        stream_id: str,          
        duration: float, 
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
        self._sample_dur_sec = sample_dur_sec
        self._time_mode = time_mode
        self._factory = ParameterFactory(stream_id, duration, time_mode)
        
        self._init_params(params)
        self._init_loop_state()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def _init_params(self, params: dict) -> None:
        """
        Inizializzazione dinamica con mappatura nomi e gestione eccezioni.
        """
        # 1. Carica TUTTO usando lo schema specifico
        # Questo crea: 'pointer_speed', 'pointer_jitter', 'pointer_offset_range', 
        # 'pointer_start', 'loop_dur' (non scalato!)
        all_params = self._factory.create_all_parameters(params, schema=POINTER_PARAMETER_SCHEMA)
        
        # 2. Assegna dinamicamente rimuovendo il prefisso 'pointer_'
        for name, param_obj in all_params.items():
            
            # CASO SPECIALE: loop_dur lo saltiamo qui, lo gestisce _init_loop_params
            if name == 'loop_dur': continue
                
            # Rimuovi prefisso 'pointer_' se presente per avere self.speed invece di self.pointer_speed
            attr_name = name.replace('pointer_', '')
            
            # Assegna (self.speed = param_obj)
            setattr(self, attr_name, param_obj)
            
        # 3. Gestione Loop (che gestisce loop_dur manualmente con lo scaling)
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
                scaled_dur_raw = self._scale_loop_dur_raw(raw_dur, scale, loop_mode)
                # Crea il parametro usando la factory. Passiamo un dict fittizio perché create_single_parameter si aspetta la struttura YAML completa
                # ma noi gli diamo il valore già estratto e scalato.
                # Trucco: create_single_parameter cerca 'loop_dur' nel dict.
                fake_params = {'loop_dur': scaled_dur_raw}
                self.loop_dur = self._factory.create_single_parameter('loop_dur', fake_params)                
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

    def _scale_loop_dur_raw(self, raw_dur, scale: float, loop_mode: str):
        """
        Scala i valori raw di loop_dur PRIMA di creare il Parameter.
        Necessario perché ParameterFactory scala il Tempo (X), ma qui dobbiamo
        scalare il Valore (Y) se siamo in normalized mode su sample duration.
        """
        if scale == 1.0:
            return raw_dur
            
        if isinstance(raw_dur, (int, float)):
            return raw_dur * scale
        
        # Envelope Dict
        if isinstance(raw_dur, dict):
            points = raw_dur.get('points', [])
            scaled_points = [[x, y * scale] for x, y in points]
            # Ritorniamo una copia modificata
            new_dur = raw_dur.copy()
            new_dur['points'] = scaled_points
            return new_dur
            
        # Envelope List
        if isinstance(raw_dur, list):
            return [[x, y * scale] for x, y in raw_dur]
            
        return raw_dur    

    def _init_loop_state(self) -> None:
        """Inizializza stato del phase accumulator per loop."""
        self._in_loop = False
        self._loop_phase = 0.0           # Fase nel loop (0.0 - 1.0)
        self._last_linear_pos = None     # Per calcolare delta movimento
    
    # =========================================================================
    # CALCULATION
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
        
        dev_normalized = self.deviation.get_value(elapsed_time)
        deviation_seconds = dev_normalized * context_length
        final_pos = base_pos + deviation_seconds
        return wrap_fn(final_pos)        
    

    def _calculate_linear_position(self, elapsed_time: float) -> float:
        """
        Calcola posizione lineare da speed (con integrazione per envelope).
        
        Se speed è un Envelope, integra per ottenere la posizione.
        Altrimenti: position = start + time * speed
        """
        internal_val = self.speed.value
        if isinstance(internal_val, Envelope):
            sample_position = internal_val.integrate(0, elapsed_time)
        else:
            sample_position = elapsed_time * float(internal_val)
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
            current_dur = self.loop_dur.get_value(elapsed_time)
            current_loop_dur = min(current_dur, self._sample_dur_sec)
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
            if self._last_linear_pos is not None:
                delta_pos = linear_pos - self._last_linear_pos
                delta_phase = delta_pos / loop_length
                self._loop_phase += delta_phase
                self._loop_phase = self._loop_phase % 1.0
            
            self._last_linear_pos = linear_pos
            base_pos = current_loop_start + self._loop_phase * loop_length
            context_length = loop_length
            
            def wrap_fn(pos: float) -> float:
                rel = pos - current_loop_start
                return current_loop_start + (rel % loop_length)
        else:
            base_pos = linear_pos % self._sample_dur_sec
            context_length = self._sample_dur_sec
            wrap_fn = lambda p: p % self._sample_dur_sec
        
        return base_pos, context_length, wrap_fn
        
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def reset(self) -> None:
        """Resetta lo stato del loop (per riuso del controller)."""
        self._init_loop_state()

    def get_speed(self, elapsed_time: float) -> float:
        """
        Ritorna la velocità istantanea al tempo specificato.
        CORRETTO: Delega al Parameter.
        """
        return self.speed.get_value(elapsed_time)
        
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
        return f"PointerController(start={self.start}, speed={self.speed._value}{loop_info})"