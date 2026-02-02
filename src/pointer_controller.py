# src/pointer_controller.py
"""
PointerController - Gestione posizionamento testina di lettura

Gestisce la posizione di lettura nel sample con:
- Movimento lineare con integrazione envelope
- Loop con phase accumulator per durata dinamica
- Deviazioni stocastiche (jitter, offset_range)

Ispirato al DMX-1000 di Barry Truax (1988)
"""

from typing import Callable
from envelope import Envelope
from parameter_schema import POINTER_PARAMETER_SCHEMA
from parameter_orchestrator import ParameterOrchestrator
from stream_config import StreamConfig
from logger import log_config_warning
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
        config: StreamConfig
    ):
        """
        Inizializza il controller.
        
        Args:
            params: dict con configurazione pointer da YAML
            evaluator: ParameterEvaluator per parsing e valutazione
            sample_dur_sec: durata del sample in secondi
            time_mode: 'absolute' o 'normalized' (default per envelope)
        """
        self._config = config
        self._sample_dur_sec = config.context.sample_dur_sec 
        self._orchestrator = ParameterOrchestrator(config=config)
        self._init_params(params)
        self._init_loop_state()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    def _init_params(self, params: dict) -> None:
        # 1. Pre-processing: conversione unita' PRIMA del pipeline
        normalized_params = self._pre_normalize_loop_params(params)

        # 2. Tutto entra nel pipeline standard. Nessun caso speciale.
        all_params = self._orchestrator.create_all_parameters(normalized_params, schema=POINTER_PARAMETER_SCHEMA)
        # 3. Assegnazione uniforme. Nessun 'continue', nessun fake_params.
        for name, param_obj in all_params.items():
            attr_name = name.replace('pointer_', '')
            setattr(self, attr_name, param_obj)

        # 4. has_loop dipende solo dalla presenza di loop_start
        self.has_loop = self.loop_start is not None
        if self.has_loop and self.loop_end is None and self.loop_dur is None:
            self.loop_end = self._sample_dur_sec

    def _pre_normalize_loop_params(self, params: dict) -> dict:
        """
        Conversione di unita' per i parametri loop.
        
        Se loop_unit == 'normalized', scala i valori dei parametri loop
        da [0.0-1.0] a secondi assoluti usando sample_dur_sec dal context.
        
        Questo metodo e' l'unico punto nel sistema che legge 'loop_unit'
        dal dizionario grezzo, ed e' il motivo legittimo: loop_unit e' un
        meta-parametro che controlla l'interpretazione degli altri, non un
        valore sintetizzabile.
        """
        if 'loop_start' not in params:
            return params  # Nessun loop configurato

        loop_unit = params.get('loop_unit') or self._config.time_mode
        if loop_unit != 'normalized':
            return params  # Valori gia' in secondi assoluti

        scale = self._sample_dur_sec

        # Copia superficiale: non modificare il dizionario originale
        scaled = dict(params)
        for key in ('loop_start', 'loop_end', 'loop_dur'):
            if key in scaled and scaled[key] is not None:
                scaled[key] = self._scale_value(scaled[key], scale)
        return scaled

    def _scale_value(self, value, scale: float):
        """
        Scala un valore che può essere scalare, envelope, o dict.
        
        FIXED: Ora gestisce correttamente marker 'cycle' delegando a Envelope.
        """
        if isinstance(value, (int, float)):
            return value * scale
        
        # Envelope-like: usa metodo centralizzato
        if Envelope.is_envelope_like(value):
            return Envelope.scale_envelope_values(value, scale)
        
        # Tipo non riconosciuto, passa invariato
        return value

    def _init_loop_state(self) -> None:
        self._in_loop = False
        self._loop_absolute_pos = None      
        self._last_linear_pos = None
        self._prev_loop_start = None        
        self._prev_loop_end = None          
    
    # =========================================================================
    # CALCULATION
    # =========================================================================
    
    def calculate(
        self,
        elapsed_time: float,
        grain_duration: float = 0.0,
        grain_reverse: bool = False
    ) -> float:
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
        if grain_reverse:
            final_pos+=grain_duration
        return wrap_fn(final_pos)        

    def _apply_loop(
        self,
        linear_pos: float,
        elapsed_time: float
    ) -> tuple[float, float, Callable[[float], float]]:
        """
        Applica logica loop con phase accumulator basato su posizione assoluta.
        
        Strategia:
        - Traccia posizione assoluta nel sample (non fase relativa 0-1)
        - Movimento inerziale: posizione += delta_pos
        - Se loop bounds cambiano e pointer è fuori → RESET a loop_start
        - Se loop bounds stabili e pointer supera loop_end → WRAP modulare
        
        Returns:
            tuple: (base_pos, context_length, wrap_function)
        """
        # =========================================================================
        # STEP 1: Valuta loop bounds CORRENTI (possono essere envelope!)
        # =========================================================================
        current_loop_start = self.loop_start.get_value(elapsed_time)
        
        if self.loop_dur is not None:
            # Modalità loop_dur (dinamica)
            current_dur = self.loop_dur.get_value(elapsed_time)
            current_loop_dur = min(current_dur, self._sample_dur_sec)
        else:
            # Modalità loop_end (può essere dinamica ora!)
            current_loop_end_val = self.loop_end.get_value(elapsed_time)
            current_loop_dur = current_loop_end_val - current_loop_start
        
        current_loop_end = min(current_loop_start + current_loop_dur, self._sample_dur_sec)
        loop_length = max(current_loop_end - current_loop_start, 0.001)
        
        # =========================================================================
        # STEP 2: Check ENTRATA nel loop (se non siamo ancora dentro)
        # =========================================================================
        if not self._in_loop:
            check_pos = linear_pos % self._sample_dur_sec
            if current_loop_start <= check_pos < current_loop_end:
                # ENTRATA nel loop
                self._in_loop = True
                self._loop_absolute_pos = check_pos
                self._last_linear_pos = linear_pos
                self._prev_loop_start = current_loop_start
                self._prev_loop_end = current_loop_end
                
                # Restituisci posizione di entrata
                base_pos = check_pos
                context_length = loop_length
                
                def wrap_fn(pos: float) -> float:
                    rel = pos - current_loop_start
                    return current_loop_start + (rel % loop_length)
                
                return base_pos, context_length, wrap_fn
            else:
                # NON siamo ancora entrati nel loop → comportamento pre-loop
                base_pos = linear_pos % self._sample_dur_sec
                context_length = self._sample_dur_sec
                wrap_fn = lambda p: p % self._sample_dur_sec
                return base_pos, context_length, wrap_fn
        
        # =========================================================================
        # STEP 3: Siamo DENTRO il loop
        # =========================================================================
        # A questo punto self._in_loop è sicuramente True
        # ---------------------------------------------------------------------
        # STEP 3a: Calcola movimento inerziale del pointer
        # ---------------------------------------------------------------------
        if self._last_linear_pos is not None:
            delta_pos = linear_pos - self._last_linear_pos
            self._loop_absolute_pos += delta_pos
        
        self._last_linear_pos = linear_pos
        
        # ---------------------------------------------------------------------
        # STEP 3b: Rileva se i bounds sono cambiati
        # ---------------------------------------------------------------------
        bounds_changed = (
            self._prev_loop_start is not None and (
                self._prev_loop_start != current_loop_start or
                self._prev_loop_end != current_loop_end
            )
        )
        
        # ---------------------------------------------------------------------
        # STEP 3c: Gestisci fuori-bounds
        # ---------------------------------------------------------------------
        if bounds_changed:
            # I bounds sono cambiati
            if not (current_loop_start <= self._loop_absolute_pos < current_loop_end):
                # parametro per logging
                pointer_would_be = self._loop_absolute_pos
                
                # Pointer fuori dai nuovi bounds → RESET a loop_start
                self._loop_absolute_pos = current_loop_start

                # LOG del reset usando log_config_warning
                log_config_warning(
                    stream_id=self._config.context.stream_id,
                    param_name="pointer_position",
                    raw_value=pointer_would_be,
                    clipped_value=current_loop_start,
                    min_val=current_loop_start,
                    max_val=current_loop_end,
                    value_type="loop_reset"
                )
        else:
            # Bounds stabili, wrap ciclico normale
            if self._loop_absolute_pos >= current_loop_end:
                # Wrap modulare: preserva fase relativa
                rel = self._loop_absolute_pos - current_loop_start
                self._loop_absolute_pos = current_loop_start + (rel % loop_length)
            elif self._loop_absolute_pos < current_loop_start:
                # Edge case: pointer è "dietro" loop_start (raro, ma possibile)
                rel = self._loop_absolute_pos - current_loop_start
                self._loop_absolute_pos = current_loop_end + (rel % loop_length)
        
        # ---------------------------------------------------------------------
        # STEP 3d: Aggiorna tracciamento bounds per prossimo frame
        # ---------------------------------------------------------------------
        self._prev_loop_start = current_loop_start
        self._prev_loop_end = current_loop_end
        
        # ---------------------------------------------------------------------
        # STEP 3e: Restituisci risultato
        # ---------------------------------------------------------------------
        base_pos = self._loop_absolute_pos
        context_length = loop_length
        
        def wrap_fn(pos: float) -> float:
            """Wrap function per applicare deviazione dentro i bounds del loop."""
            rel = pos - current_loop_start
            return current_loop_start + (rel % loop_length)
        
        return base_pos, context_length, wrap_fn

    def _calculate_linear_position(self, elapsed_time: float) -> float:
        """
        Calcola posizione lineare da speed (con integrazione per envelope).
        
        Se speed è un Envelope, integra per ottenere la posizione.
        Altrimenti: position = start + time * speed
        """
        internal_val = self.speed_ratio.value
        if isinstance(internal_val, Envelope):
            sample_position = internal_val.integrate(0, elapsed_time)
        else:
            sample_position = elapsed_time * float(internal_val)
        return self.start + sample_position

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
        return self.speed_ratio.get_value(elapsed_time)
        
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
        return f"PointerController(start={self.start}, speed={self.speed_ratio._value}{loop_info})"