import random
import soundfile as sf
from grain import Grain
from envelope import Envelope
PATHSAMPLES='./refs/'

# parametri density
STREAM_MIN_FILLFACTOR=0.001
STREAM_MAX_FILLFACTOR=50
STREAM_MIN_DENSITY=0.1
STREAM_MAX_DENSITY=4000
# parametri grain_duration (in secondi)
STREAM_MIN_GRAIN_DURATION=0.0001
STREAM_MAX_GRAIN_DURATION=10.0
# parametri pitch
STREAM_MIN_SEMITONES=-36
STREAM_MAX_SEMITONES=36
STREAM_MIN_PITCH_RATIO=0.125
STREAM_MAX_PITCH_RATIO=8.0
# parametri output
STREAM_MIN_VOLUME=-120
STREAM_MAX_VOLUME=12
STREAM_MIN_PANDEGREE=-360*10
STREAM_MAX_PANDEGREE=360*10
# parametri altri
STREAM_MIN_JITTER=0.00001
STREAM_MAX_JITTER=10.0
STREAM_MIN_OFFSET_RANGE=0.0
STREAM_MAX_OFFSET_RANGE=1.0

# ============================================================================= 
# SAFETY LIMITS - Range parameters (deviazioni)
# =============================================================================
STREAM_MIN_PITCH_RANGE_SEMITONES = 0.0
STREAM_MAX_PITCH_RANGE_SEMITONES = 36.0
STREAM_MIN_PITCH_RANGE_RATIO = 0.0
STREAM_MAX_PITCH_RANGE_RATIO = 2.0
# Nuovi range per grain_duration (in secondi)
STREAM_MIN_GRAIN_DURATION_RANGE = 0.0
STREAM_MAX_GRAIN_DURATION_RANGE = 1.0
# Nuovi range per volume (in dB)
STREAM_MIN_VOLUME_RANGE = 0.0
STREAM_MAX_VOLUME_RANGE = 12.0  # ±12dB massimo consigliato
# Nuovi range per pan (in gradi)
STREAM_MIN_PAN_RANGE = 0.0
STREAM_MAX_PAN_RANGE = 360.0
# Nuovi range per density (grani/sec)
STREAM_MIN_DENSITY_RANGE = 0.0
STREAM_MAX_DENSITY_RANGE = 100.0
# Nuovi range per fill_factor
STREAM_MIN_FILLFACTOR_RANGE = 0.0
STREAM_MAX_FILLFACTOR_RANGE = 10.0


def get_sample_duration(filepath):
    info = sf.info(PATHSAMPLES + filepath)
    return info.duration  # secondi come float

class Stream:
    def __init__(self, params):
        """
        Inizializza uno stream granulare.
        
        La funzione è ora divisa in metodi specifici per area funzionale,
        migliorando leggibilità, testabilità e manutenibilità.
        """
        # === IDENTITÀ & TIMING (sempre necessari, brevi) ===
        self.stream_id = params['stream_id']
        self.onset = params['onset']
        self.duration = params['duration']
        self.timeScale = params.get('time_scale', 1.0)
        self.time_mode = params.get('time_mode', 'absolute')

        self._init_audio(params)
        
        # === PARAMETRI COMPLESSI (metodi dedicati) ===
        self._init_distribution(params)
        self._init_pitch_params(params)
        self._init_pointer_params(params)
        self._init_grain_params(params)
        self._init_density_params(params)
        self._init_grain_reverse(params)
        self._init_output_params(params)
        
        # === AUDIO & STATE (setup finale) ===
        self._init_csound_references()
        self._init_state()

    def _init_distribution(self, params):
        """
        Inizializza il parametro distribution (0=sync, 1=async).
        """
        self.distribution = self._parse_envelope_param(params.get('distribution', 0.0), 'distribution')

    def _init_pitch_params(self, params):
        """
        Gestisce i parametri di pitch con due modalità:
        1. shift_semitones: trasposizione in semitoni (convertita a ratio)
        2. ratio: trasposizione diretta come ratio (default 1.0)
        
        Entrambe supportano numeri fissi o Envelope.
        """
        pitch_params = params.get('pitch', {})
        
        if 'shift_semitones' in pitch_params:
            # Modalità SEMITONI
            shift_param = pitch_params['shift_semitones']

            self.pitch_semitones_envelope = self._parse_envelope_param(shift_param, "pitch.shift_semitones")
            self.pitch_ratio = None  # marker: usa envelope
            self.pitch_range = self._parse_envelope_param(pitch_params.get('range', 0.0), "pitch.range")
            self.pitch_range_mode = 'semitones'
        else:
            # Modalità RATIO diretta (o default a 1.0)
            self.pitch_ratio = self._parse_envelope_param(pitch_params.get('ratio', 1.0), "pitch.ratio")
            self.pitch_semitones_envelope = None
            self.pitch_range = self._parse_envelope_param(pitch_params.get('range', 0.0), "pitch.range")
            self.pitch_range_mode = 'ratio'

    def _init_pointer_params(self, params):
        """
        Gestisce tutti i parametri del pointer (posizionamento nel sample).
        
        Parametri:
        - start: posizione iniziale (secondi)
        - speed: velocità di scansione (supporta Envelope)
        - jitter: micro-variazione bipolare (0.001-0.01 sec tipico)
        - offset_range: macro-variazione bipolare (0-1, normalizzato su durata sample)
        - loop_start: inizio loop (opzionale, secondi) - FISSO
        - loop_end: fine loop (opzionale, secondi) - FISSO (mutualmente esclusivo con loop_dur)
        - loop_dur: durata loop (opzionale) - SUPPORTA ENVELOPE
        """ 
        pointer = params.get('pointer', {})
        
        # Posizione iniziale
        self.pointer_start = pointer.get('start', 0.0)
        self.pointer_speed = self._parse_envelope_param(pointer.get('speed', 1.0), "pointer.speed")
        self.pointer_jitter = self._parse_envelope_param(pointer.get('jitter', 0.0), "pointer.jitter")        
        self.pointer_offset_range = self._parse_envelope_param(pointer.get('offset_range', 0.0), "pointer.offset_range")

        # === LOOP STATE (Phase Accumulator) ===
        self._in_loop = False
        self._loop_phase = 0.0           # Fase nel loop (0.0 - 1.0)
        self._last_linear_pos = None     # Per calcolare delta movimento
        
        raw_start = pointer.get('loop_start')
        raw_end = pointer.get('loop_end')
        raw_dur = pointer.get('loop_dur')

        if raw_start is not None:
            loop_mode = pointer.get('loop_unit') or self.time_mode
            scale = self.sampleDurSec if loop_mode == 'normalized' else 1.0
            
            # loop_start è SEMPRE fisso
            self.loop_start = raw_start * scale
            
            if raw_end is not None:
                # Modalità loop_end FISSO (legacy)
                self.loop_end = raw_end * scale
                self.loop_dur = None
            elif raw_dur is not None:
                # Modalità loop_dur (può essere Envelope!)
                self.loop_end = None
                
                if isinstance(raw_dur, (int, float)):
                    self.loop_dur = raw_dur * scale
                else:
                    # È un envelope/lista - scala i valori Y se normalized
                    if loop_mode == 'normalized':
                        if isinstance(raw_dur, dict):
                            scaled_points = [[x, y * scale] for x, y in raw_dur['points']]
                            raw_dur = {'type': raw_dur.get('type', 'linear'), 'points': scaled_points}
                        elif isinstance(raw_dur, list):
                            raw_dur = [[x, y * scale] for x, y in raw_dur]
                    
                    self.loop_dur = self._parse_envelope_param(raw_dur, "pointer.loop_dur")
            else:
                # Solo loop_start → loop fino a fine sample
                self.loop_end = self.sampleDurSec
                self.loop_dur = None
                
            self.has_loop = True
        else:
            self.loop_start = None
            self.loop_end = None
            self.loop_dur = None
            self.has_loop = False

    def _init_grain_params(self, params):
        """
        Gestisce i parametri base dei singoli grani.
        
        Parametri:
        - duration: durata del grano (supporta Envelope)
        - duration_range: variazione stocastica della durata (±range/2)
        - envelope: tipo di inviluppo (hanning, hamming, etc.)
        """
        grain_params = params.get('grain', {})
        self.grain_duration = self._parse_envelope_param(grain_params['duration'], "grain.duration")        
        self.grain_duration_range = self._parse_envelope_param(grain_params.get('duration_range', 0.0), "grain.duration_range")
        self.grain_envelope = grain_params.get('envelope', 'hanning')
        
    def _init_density_params(self, params):
        """
        Gestisce density con due modalità mutuamente esclusive:
        
        1. FILL_FACTOR (preferito): density = fill_factor / grain_duration
           - La density si adatta automaticamente alla durata del grano
           - Default: 2.0 (Roads: "covered/packed texture")
        
        2. DENSITY diretta: valore fisso o Envelope
           - Controllo esplicito della density
        """
        if 'fill_factor' in params:
            # Modalità FILL_FACTOR esplicita
            self.fill_factor = self._parse_envelope_param(params['fill_factor'], "fill_factor")
            self.density = None
        elif 'density' in params:
            # Modalità DENSITY diretta
            self.fill_factor = None
            self.density = self._parse_envelope_param(params['density'], "density")
        else:
            # DEFAULT: fill_factor = 2.0 (Roads: "covered/packed")
            self.fill_factor = 2.0
            self.density = None

    def _init_grain_reverse(self, params):
        """
        Gestisce la direzione di lettura dei grani.
        
        Modalità:
        - 'auto': segue il segno di pointer_speed (negativo = reverse)
        - True/False: valore esplicito
        """
        if 'reverse' in params['grain']:
            self.grain_reverse_mode = params['grain']['reverse']  # True o False
        else:
            self.grain_reverse_mode = 'auto'  # segui pointer_speed

    def _init_output_params(self, params):
        """
        Gestisce i parametri di output audio.
        
        Parametri:
        - volume: livello in dB (supporta Envelope)
        - volume_range: variazione stocastica volume (±range/2 dB)
        - pan: posizione stereo (gradi, supporta Envelope)
        - pan_range: variazione stocastica pan (±range/2 gradi)
        """
        self.volume = self._parse_envelope_param(params.get('volume', -6.0), "output.volume")
        self.volume_range = self._parse_envelope_param(params.get('volume_range', 0.0), "output.volume_range")
        self.pan = self._parse_envelope_param(params.get('pan', 0.0), "pan")
        self.pan_range = self._parse_envelope_param(params.get('pan_range', 0.0), "pan_range")

    def _init_audio(self, params):
        """
        Gestisce il file audio sorgente.
        """
        self.sample_path = params['sample']
        self.sampleDurSec = get_sample_duration(self.sample_path)

    def _init_csound_references(self):
        """
        Inizializza i riferimenti alle ftable Csound.
        Questi saranno assegnati dal Generator.
        """
        self.sample_table_num = None
        self.envelope_table_num = None

    def _init_state(self):
        """
        Inizializza lo stato interno dello stream.
        """
        self._cumulative_read_time = 0.0
        self.grains = []
        self.generated = False

    def _calculate_inter_onset_time(self, elapsed_time, current_grain_dur):
        """
        Calcola l'inter-onset time basato su density/fill_factor e distribution
        
        Se fill_factor è definito:
            density_effettiva = fill_factor / current_grain_dur
            (la density si adatta dinamicamente alla durata del grano)
        
        Se density è definita direttamente:
            density_effettiva = density (fissa o da envelope)
        
        SYNCHRONOUS (distribution=0):
            inter_onset = 1 / density (fisso)
            
        ASYNCHRONOUS (distribution>0):
            inter_onset = random(0, 2 × avg_inter_onset)
            (Truax 1994: "random value between zero and twice the average")
        
        Args:
            elapsed_time: tempo trascorso dall'onset dello stream
            current_grain_dur: durata del grano corrente (già valutata)
            
        Returns:
            float: tempo in secondi fino al prossimo grano
        """
        # Calcola density effettiva
        if self.fill_factor is not None:
            # Modalità FILL_FACTOR: density = fill_factor / grain_duration
            ff = self._safe_evaluate(self.fill_factor, elapsed_time, STREAM_MIN_FILLFACTOR,STREAM_MAX_FILLFACTOR)
            effective_density = ff / current_grain_dur
        else:
            # Modalità DENSITY diretta
            effective_density = self._safe_evaluate(
                self.density, elapsed_time,
                STREAM_MIN_DENSITY, STREAM_MAX_DENSITY
            )
        
        # Safety: clamp density per evitare problemi
        effective_density = max(0.1, min(4000.0, effective_density))
        
        avg_inter_onset = 1.0 / effective_density
        
        distribution = self._safe_evaluate(self.distribution, elapsed_time,0.0, 1.0)

        if distribution == 0.0:
            # SYNCHRONOUS: inter-onset fisso
            return avg_inter_onset
        else:
            # INTERPOLAZIONE sync → async
            # Preserva la media, aumenta la varianza con distribution
            sync_value = avg_inter_onset
            async_value = random.uniform(0, 2.0 * avg_inter_onset)
            return (1.0 - distribution) * sync_value + distribution * async_value    

    def _calculate_pointer(self, elapsed_time):
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
        if isinstance(self.pointer_speed, Envelope):
            sample_position = self.pointer_speed.integrate(0, elapsed_time)
        else:
            sample_position = elapsed_time * self.pointer_speed

        linear_pos = self.pointer_start + sample_position

        if self.has_loop:
            # === CALCOLA LOOP BOUNDS CORRENTI ===
            current_loop_start = self.loop_start
            
            if self.loop_dur is not None:
                # loop_dur dinamico (può essere Envelope)
                current_loop_dur = self._safe_evaluate(
                    self.loop_dur, elapsed_time, 
                    0.001, self.sampleDurSec
                )
            else:
                # loop_end fisso (legacy)
                current_loop_dur = self.loop_end - self.loop_start
                
            current_loop_end = min(current_loop_start + current_loop_dur, self.sampleDurSec)
            loop_length = max(current_loop_end - current_loop_start, 0.001)

            # === PHASE ACCUMULATOR ===
            if not self._in_loop:
                # Check entrata nel loop
                check_pos = linear_pos % self.sampleDurSec
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
                def wrap_fn(pos):
                    rel = pos - current_loop_start
                    return current_loop_start + (rel % loop_length)
            else:
                # Prima del loop: wrap sul buffer intero
                base_pos = linear_pos % self.sampleDurSec
                context_length = self.sampleDurSec
                wrap_fn = lambda p: p % self.sampleDurSec
        else:
            # Nessun loop: wrap semplice sul buffer
            base_pos = linear_pos % self.sampleDurSec
            context_length = self.sampleDurSec
            wrap_fn = lambda p: p % self.sampleDurSec

        # 4. Deviazioni stocastiche
        jitter_amount = self._safe_evaluate(
            self.pointer_jitter, elapsed_time, STREAM_MIN_JITTER, STREAM_MAX_JITTER
        )
        offset_range = self._safe_evaluate(
            self.pointer_offset_range, elapsed_time, STREAM_MIN_OFFSET_RANGE, STREAM_MAX_OFFSET_RANGE
        )
        
        jitter_deviation = random.uniform(-jitter_amount, jitter_amount)
        offset_deviation = random.uniform(-0.5, 0.5) * offset_range * context_length
        
        # 5. Posizione finale con wrap
        final_pos = base_pos + jitter_deviation + offset_deviation
        return wrap_fn(final_pos)

    def generate_grains(self):
        """
        Genera grani basati su DENSITY, non su duration/grain_duration
        
        ALGORITMO:
        1. Calcola quanti grani servono: duration × density
        2. Per ogni grano:
           a. Calcola inter-onset time (fisso o random)
           b. Avanza current_onset
           c. Calcola pointer position
           d. Crea il grano
        
        Questo permette:
        - Overlap dei grani (normale e desiderato!)
        - Density variabile in futuro
        - Grain duration variabile
        - Async granulation
        """
        current_onset = self.onset  
        stream_end = self.onset + self.duration        
        grain_count = 0
        while current_onset < stream_end:
            elapsed_time = current_onset - self.onset
            grain_dur = self._calculate_parameter_within_range(elapsed_time, self.grain_duration, self.grain_duration_range, STREAM_MIN_GRAIN_DURATION, STREAM_MAX_GRAIN_DURATION, STREAM_MIN_GRAIN_DURATION_RANGE, STREAM_MAX_GRAIN_DURATION_RANGE)
            pointer_pos = self._calculate_pointer(elapsed_time)
            pitch_ratio = self._calculate_pitch_ratio(elapsed_time)
            if self.grain_reverse_mode == 'auto':
                # Calcola la velocità effettiva a questo tempo
                current_speed = self.pointer_speed.evaluate(elapsed_time)
                grain_reverse = (current_speed < 0)
            else:
                # Usa il valore esplicito (True o False)
                grain_reverse = self.grain_reverse_mode
            volume = self._calculate_parameter_within_range(elapsed_time, self.volume, self.volume_range, STREAM_MIN_VOLUME, STREAM_MAX_VOLUME, STREAM_MIN_VOLUME_RANGE, STREAM_MAX_VOLUME_RANGE)
            pan = self._calculate_parameter_within_range(elapsed_time, self.pan, self.pan_range,STREAM_MIN_PANDEGREE, STREAM_MAX_PANDEGREE,STREAM_MIN_PAN_RANGE, STREAM_MAX_PAN_RANGE)

            # CREA IL GRANO
            grain = Grain(
                onset=current_onset,
                duration=grain_dur,
                pointer_pos=pointer_pos,
                pitch_ratio=pitch_ratio,
                volume=volume,
                pan=pan,
                sample_table=self.sample_table_num,
                envelope_table=self.envelope_table_num,
                grain_reverse=grain_reverse
            )
            self.grains.append(grain)
            inter_onset = self._calculate_inter_onset_time(elapsed_time, grain_dur)
            current_onset += inter_onset
            grain_count += 1     
        self.generated = True
        return self.grains

    def _calculate_parameter_within_range(self, elapsed_time, param, param_range, 
                                        min_param, max_param, min_range, max_range):
        """
        Calcola un parametro con variazione stocastica basata su range.
        Args:
            elapsed_time: tempo relativo all'onset dello stream
            param: valore base del parametro (numero o Envelope)
            param_range: ampiezza della variazione (numero o Envelope)  
            min_param: limite minimo del parametro
            max_param: limite massimo del parametro
            min_range: limite minimo del range
            max_range: limite massimo del range
        Returns:
            float: valore del parametro con deviazione stocastica applicata
        """
        base_param = self._safe_evaluate(param, elapsed_time, min_param, max_param)
        range_value = self._safe_evaluate(param_range, elapsed_time, min_range, max_range)
        param_deviation = random.uniform(-0.5, 0.5) * range_value
        final_value = base_param + param_deviation        
        return max(min_param, min(max_param, final_value))

    def _calculate_pitch_ratio(self, elapsed_time):
        """
        Calcola pitch ratio con support per range.
        Estrae la logica di calcolo pitch per pulizia del codice.
        
        Returns:
            float: pitch ratio finale (con deviazione se range != 0)
        """
        if self.pitch_semitones_envelope is not None:
            # Modalità SEMITONI
            base_semitones = self._safe_evaluate(self.pitch_semitones_envelope, elapsed_time, STREAM_MIN_SEMITONES, STREAM_MAX_SEMITONES)
            pitch_range = self._safe_evaluate(self.pitch_range, elapsed_time,STREAM_MIN_PITCH_RANGE_SEMITONES, STREAM_MAX_PITCH_RANGE_SEMITONES)
            pitch_deviation = random.randint(int(-pitch_range*0.5), int(pitch_range*0.5))
            final_semitones = base_semitones + pitch_deviation
            return pow(2.0, final_semitones / 12.0)
        else:
            # Modalità RATIO
            base_ratio = self._safe_evaluate(self.pitch_ratio, elapsed_time, STREAM_MIN_PITCH_RATIO, STREAM_MAX_PITCH_RATIO)
            if self.pitch_range_mode == 'ratio':
                pitch_range = self._safe_evaluate(self.pitch_range, elapsed_time,STREAM_MIN_PITCH_RANGE_RATIO, STREAM_MAX_PITCH_RANGE_RATIO)
                pitch_deviation = random.uniform(-0.5, 0.5) * pitch_range
                return base_ratio + pitch_deviation
            else:
                return base_ratio
            
    def _parse_envelope_param(self, param, param_name="parameter"):
        """
        Helper per parsare parametri che possono essere numeri o Envelope
        
        Args:
            param: numero singolo, lista di breakpoints, o dict con type/points
            param_name: nome del parametro (per messaggi errore informativi)
        
        Returns:
            numero o Envelope
        
        Examples:
            >>> self._parse_envelope_param(50, "density")
            50
            >>> self._parse_envelope_param([[0, 20], [2, 100]], "density")
            Envelope(type=linear, points=[[0, 20], [2, 100]])
            >>> self._parse_envelope_param({'type': 'cubic', 'points': [...]}, "volume")
            Envelope(type=cubic, ...)
        """
        if isinstance(param, (int, float)):
            # Numero singolo → usa direttamente (efficiente!)
            return param
        elif isinstance(param, dict):
            # Determina se normalizzare: locale > globale
            local_mode = param.get('time_unit')  # None, 'normalized', 'absolute'
            should_normalize = (local_mode == 'normalized' or (local_mode is None and self.time_mode == 'normalized'))
            if should_normalize:
                scaled_points = [[x * self.duration, y] for x, y in param['points']]
                return Envelope({'type': param.get('type', 'linear'),'points': scaled_points})
            return Envelope(param)
        elif isinstance(param, list):
            # Lista semplice: rispetta time_mode globale
            if self.time_mode == 'normalized':
                scaled_points = [[x * self.duration, y] for x, y in param]
                return Envelope(scaled_points)
            return Envelope(param)
        else:
            raise ValueError(f"{param_name} formato non valido: {param}")

    def _safe_evaluate(self, param, time, min_val, max_val):
        """
        Valuta un parametro (fisso o Envelope) con safety bounds
        
        Args:
            param: numero o Envelope
            time: tempo relativo all'onset dello stream (elapsed_time)
            min_val: valore minimo ammissibile
            max_val: valore massimo ammissibile
        
        Returns:
            float: valore clippato nei bounds
        """
        value = param.evaluate(time) if isinstance(param, Envelope) else param
        return max(min_val, min(max_val, value))

    def __repr__(self):
        mode = "fill_factor" if self.fill_factor is not None else "density"
        return (f"Stream(id={self.stream_id}, onset={self.onset}, "
                f"dur={self.duration}, mode={mode}, grains={len(self.grains)})")
