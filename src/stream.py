import random
import soundfile as sf
from grain import Grain
from envelope import Envelope
PATHSAMPLES='./refs/'

STREAM_MIN_FILLFACTOR=0.001
STREAM_MAX_FILLFACTOR=50
STREAM_MIN_DENSITY=0.1
STREAM_MAX_DENSITY=4000
STREAM_MIN_GRAIN_DURATION=0.001
STREAM_MAX_GRAIN_DURATION=10.0
STREAM_MIN_SEMITONES=-36
STREAM_MAX_SEMITONES=36
STREAM_MIN_PITCH_RATIO=0.125
STREAM_MAX_PITCH_RATIO=8.0
STREAM_MIN_VOLUME=-120
STREAM_MAX_VOLUME=12
STREAM_MIN_PANDEGREE=-360*10
STREAM_MAX_PANDEGREE=360*10
STREAM_MIN_JITTER=0.00001
STREAM_MAX_JITTER=10.0
STREAM_MIN_OFFSET_RANGE=0.0
STREAM_MAX_OFFSET_RANGE=1.0

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
            if isinstance(shift_param, (int, float)):
                # Numero singolo → converti subito a ratio
                self.pitch_ratio = pow(2.0, shift_param / 12.0)
                self.pitch_semitones_envelope = None
            else:
                # Envelope di semitoni → salva envelope, conversione per-grano
                self.pitch_semitones_envelope = self._parse_envelope_param(
                    shift_param, "pitch.shift_semitones"
                )
                self.pitch_ratio = None  # marker: usa envelope
        else:
            # Modalità RATIO diretta (o default a 1.0)
            self.pitch_ratio = self._parse_envelope_param(
                pitch_params.get('ratio', 1.0), "pitch.ratio"
            )
            self.pitch_semitones_envelope = None


    def _init_pointer_params(self, params):
        """
        Gestisce tutti i parametri del pointer (posizionamento nel sample).
        
        Parametri:
        - start: posizione iniziale (secondi)
        - speed: velocità di scansione (supporta Envelope)
        - jitter: micro-variazione bipolare (0.001-0.01 sec tipico)
        - offset_range: macro-variazione bipolare (0-1, normalizzato su durata sample)
        - loop_start: inizio loop (opzionale, secondi)
        - loop_end: fine loop (opzionale, secondi) - esclusivo
        - loop_dur: alternativa a loop_end (opzionale, secondi)
        """ 
        pointer = params.get('pointer', {})
        
        # Posizione iniziale
        self.pointer_start = pointer.get('start', 0.0)
        # Speed (supporta Envelope)
        self.pointer_speed = self._parse_envelope_param(pointer.get('speed', 1.0), "pointer.speed")
        # Jitter: micro-variazione (supporta Envelope)
        self.pointer_jitter = self._parse_envelope_param(pointer.get('jitter', 0.0), "pointer.jitter")        
        # Offset range: macro-variazione (supporta Envelope)
        self.pointer_offset_range = self._parse_envelope_param(pointer.get('offset_range', 0.0), "pointer.offset_range")
        self._in_loop = False
        self.loop_start = pointer.get('loop_start')
        self.loop_end = pointer.get('loop_end')
        loop_dur = pointer.get('loop_dur')

        # Determina se il loop è attivo e calcola i bounds
        if self.loop_start is not None:
            if self.loop_end is None:
                if loop_dur is not None:
                    self.loop_end = self.loop_start + loop_dur
                else:
                    self.loop_end = self.sampleDurSec
            self.has_loop = True
        else:
            self.has_loop = False
            
    def _init_grain_params(self, params):
        """
        Gestisce i parametri base dei singoli grani.
        
        Parametri:
        - duration: durata del grano (supporta Envelope)
        - envelope: tipo di inviluppo (hanning, hamming, etc.)
        """
        self.grain_duration = self._parse_envelope_param(
            params['grain']['duration'], "grain.duration"
        )
        self.grain_envelope = params['grain'].get('envelope', 'hanning')

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
            self.fill_factor = self._parse_envelope_param(
                params['fill_factor'], "fill_factor"
            )
            self.density = None
        elif 'density' in params:
            # Modalità DENSITY diretta
            self.fill_factor = None
            self.density = self._parse_envelope_param(
                params['density'], "density"
            )
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
        - pan: posizione stereo 0-1 (supporta Envelope)
        """
        self.volume = self._parse_envelope_param(
            params.get('volume', -6.0), "output.volume"
        )
        self.pan = self._parse_envelope_param(
            params.get('pan', 0.0), "pan"
        )

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
            # Dict con 'type' e 'points' → crea Envelope
            return Envelope(param)
        elif isinstance(param, list):
            # Lista di breakpoints → Envelope lineare
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
        if isinstance(param, Envelope):
            value = param.evaluate(time)
        else:
            value = param
        return max(min_val, min(max_val, value))

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




    def _calculate_pointer(self, grain_count, elapsed_time):
        """
        Calcola la posizione di lettura nel sample per questo grano.
        
        Modello unificato (Truax 1994):
        - Posizione base = start + movimento da speed
        - Jitter = micro-variazione bipolare (millisecondi)
        - Offset range = macro-variazione bipolare (proporzione del sample)
        
        Args:
            grain_count: numero progressivo del grano
            elapsed_time: secondi trascorsi dall'onset dello stream
            
        Returns:
            float: posizione in secondi nel sample sorgente
        """
        # 1. Calcola la distanza percorsa nel sample (da speed)
        if isinstance(self.pointer_speed, Envelope):
            sample_position = self.pointer_speed.integrate(0, elapsed_time)
        else:
            sample_position = elapsed_time * self.pointer_speed

        # 2. Posizione grezza con wrap sul buffer
        raw_pos = (self.pointer_start + sample_position) % self.sampleDurSec

        # 3. Check entrata nel loop: [loop_start, loop_end)
        if self.has_loop and not self._in_loop:
            if self.loop_start <= raw_pos < self.loop_end:
                self._in_loop = True
    
        # 4. Determina contesto (loop attivo vs buffer intero)
        if self.has_loop and self._in_loop:
            base_pos = self._wrap_to_loop(raw_pos)
            context_length = self.loop_end - self.loop_start
            wrap_fn = self._wrap_to_loop
        else:
            base_pos = raw_pos
            context_length = self.sampleDurSec
            wrap_fn = lambda p: p % self.sampleDurSec

        # 5. Jitter (micro) e Offset range (macro)
        jitter_amount = self._safe_evaluate(self.pointer_jitter, elapsed_time,STREAM_MIN_JITTER, STREAM_MAX_JITTER)
        offset_range = self._safe_evaluate(self.pointer_offset_range, elapsed_time, STREAM_MIN_OFFSET_RANGE, STREAM_MAX_OFFSET_RANGE)
        # 6. calcolo delle deviazioni stocastiche
        jitter_deviation = random.uniform(-jitter_amount, jitter_amount)
        offset_deviation = random.uniform(-0.5, 0.5) * offset_range * context_length    
        # 7. Posizione finale con deviazioni e wrap
        final_pos = (base_pos + jitter_deviation + offset_deviation)
        return wrap_fn(final_pos)
    
    def _wrap_to_loop(self, pos):
        loop_length = self.loop_end - self.loop_start
        pos_relative = pos - self.loop_start
        return self.loop_start + (pos_relative % loop_length)
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
            grain_dur = self._safe_evaluate(self.grain_duration,elapsed_time, STREAM_MIN_GRAIN_DURATION, STREAM_MAX_GRAIN_DURATION)
            # Calcola pointer position (dove leggere nel sample)
            pointer_pos = self._calculate_pointer(grain_count, elapsed_time)
            # PITCH_RATIO (con envelope support + safety)
            if self.pitch_semitones_envelope is not None:
                # Envelope di semitoni → valuta e converti a ratio
                semitones = self._safe_evaluate(self.pitch_semitones_envelope,elapsed_time, STREAM_MIN_SEMITONES, STREAM_MAX_SEMITONES)
                pitch_ratio = pow(2.0, semitones / 12.0)
            else:
                # Numero fisso o envelope di ratio
                pitch_ratio = self._safe_evaluate(self.pitch_ratio,elapsed_time, STREAM_MIN_PITCH_RATIO, STREAM_MAX_PITCH_RATIO)
            if self.grain_reverse_mode == 'auto':
                # Calcola la velocità effettiva a questo tempo
                if isinstance(self.pointer_speed, Envelope):
                    current_speed = self.pointer_speed.evaluate(elapsed_time)
                else:
                    current_speed = self.pointer_speed
                grain_reverse = (current_speed < 0)
            else:
                # Usa il valore esplicito (True o False)
                grain_reverse = self.grain_reverse_mode
            # VOLUME (con envelope support + safety)
            volume = self._safe_evaluate(self.volume,elapsed_time, STREAM_MIN_VOLUME, STREAM_MAX_VOLUME)
            # PAN (con envelope support + safety)
            pan = self._safe_evaluate(self.pan,elapsed_time, STREAM_MIN_PANDEGREE, STREAM_MAX_PANDEGREE)

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
            # Calcola quando parte il PROSSIMO grano
            inter_onset = self._calculate_inter_onset_time(elapsed_time, grain_dur)
            current_onset += inter_onset
            grain_count += 1     
            # Safety check per async (evita loop infiniti)
        self.generated = True
        return self.grains

    def __repr__(self):
        mode = "fill_factor" if self.fill_factor is not None else "density"
        return (f"Stream(id={self.stream_id}, onset={self.onset}, "
                f"dur={self.duration}, mode={mode}, grains={len(self.grains)})")
