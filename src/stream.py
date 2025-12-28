import random
import soundfile as sf
from grain import Grain
from envelope import Envelope
PATHSAMPLES='./refs/'

def get_sample_duration(filepath):
    info = sf.info(PATHSAMPLES + filepath)
    return info.duration  # secondi come float

class Stream:
    def __init__(self, params):
        # === IDENTITÀ ===
        self.stream_id = params['stream_id']
        # === TIMING ===
        self.onset = params['onset']
        self.duration = params['duration']
        self.timeScale = params.get('time_scale', 1.0)  # per il futuro per rallentare - velocizzare la cloud.     
        # === DISTRIBUTION (0=sync, 1=async) ===
        self.distribution = params.get('distribution', 0.0)        

        # === PITCH ===
        # Gestisce: assente, vuoto, null, shift_semitones, ratio
        pitch_params = params.get('pitch', {}) or {}  # None → {}
        if 'shift_semitones' in pitch_params:
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
            # Modalità ratio diretta, oppure default a 1.0 (nessun pitch shift)
            self.pitch_ratio = self._parse_envelope_param(
                pitch_params.get('ratio', 1.0), "pitch.ratio"
            )
            self.pitch_semitones_envelope = None
                    
        # === POINTER ===
        self.pointer_start = params['pointer']['start']
        self.pointer_mode = params['pointer'].get('mode', 'linear')
        if self.pointer_mode == 'loop':
            # normalizzati tra 0 e 1.
            self.loopstart = params['pointer'].get('loopstart', 0.0)
            self.loopdur = params['pointer'].get('loopdur', 1.0)
        # pointer_speed può essere un numero fisso o un Envelope
        self.pointer_speed = self._parse_envelope_param(
            params['pointer'].get('speed', 1.0), "pointer.speed"
        )
        self.pointer_jitter = params['pointer'].get('jitter', 0.0)  
        self.pointer_random_range = params['pointer'].get('random_range', 1.0)
        # === GRAIN PARAMETERS ===
        self.grain_duration = self._parse_envelope_param(params['grain']['duration'], "grain.duration")
        self.grain_envelope = params['grain'].get('envelope','hanning')
        # === DENSITY ===
        if 'overlap_factor' in params['grain']:
            overlap_factor = params['grain']['overlap_factor']
            self.density = overlap_factor / self.grain_duration
        else:
            self.density = params['density']
        # Da rivedere!!!!!! pointer_mode non è mai piu reverse !!!
        # === GRAIN REVERSE ===
        if 'reverse' in params['grain']:
            self.grain_reverse = params['grain']['reverse']
        else:
            if self.pointer_mode == 'reverse':
                self.grain_reverse = True   # reverse→reverse
            else:
                self.grain_reverse = False
        # === OUTPUT ===
        self.volume = self._parse_envelope_param(
            params['output']['volume'], "output.volume")
        self.pan = self._parse_envelope_param(
            params['output']['pan'], "output.pan")
        # === AUDIO ===
        self.sample_path = params['sample']
        self.sampleDurSec = get_sample_duration(self.sample_path)
        # === CSOUND REFERENCES (assegnati dal Generator) ===
        self.sample_table_num = None
        self.envelope_table_num = None
        # === STATE ===
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
    
    def _calculate_inter_onset_time(self):
        """
        Calcola l'inter-onset time basato su density e distribution
        
        SYNCHRONOUS (distribution=0):
            inter_onset = 1 / density (fisso)
            
        ASYNCHRONOUS (distribution>0):
            inter_onset = random(0, 2 × avg_inter_onset)
            (Truax 1994: "random value between zero and twice the average")
        
        Args:
            iteration: numero iterazione (per seed random se necessario)
            
        Returns:
            float: tempo in secondi fino al prossimo grano
        """
        avg_inter_onset = 1.0 / self.density
        
        if self.distribution == 0.0:
            # SYNCHRONOUS: inter-onset fisso
            return avg_inter_onset
        
        else:
            # ASYNCHRONOUS: inter-onset randomizzato
            # Range: [0, 2 × average] come da Truax
            max_offset = self.distribution * (2.0 * avg_inter_onset)
            
            # Random uniforme tra 0 e max_offset
            # (distribution=1.0 → full range, distribution=0.5 → mezzo range)
            return random.uniform(0, max_offset)
    

    def _calculate_pointer(self, grain_count, elapsed_time):
        """
        Calcola la posizione di lettura nel sample per questo grano.

        Usa il TEMPO REALE trascorso dall'inizio dello stream. 
        Questo garantisce la separazione micro/macro di Truax (1994): la posizione nel sample (livello macro) è indipendente dalla density dei grani (livello micro).
        
        Args:
            grain_count: numero progressivo del grano (0 = primo)
            elapsed_time: secondi trascorsi dall'onset dello stream
            
        Returns:
            float: posizione in secondi nel sample sorgente
        """        
        # Calcola la distanza percorsa nel sample
        if isinstance(self.pointer_speed, Envelope):
            # Envelope: integra la velocità nel tempo
            sample_position = self.pointer_speed.integrate(0, elapsed_time)
        else:
            # Numero fisso: semplice moltiplicazione (veloce!)
            sample_position = elapsed_time * self.pointer_speed
            
        if self.pointer_mode == 'linear':
            start = self.pointer_start if grain_count == 0 else 0
            base_pos = (start + sample_position) % self.sampleDurSec

        # capire che senso ha valore 1, perché dovrebbe essere in secondi...            
        elif self.pointer_mode == 'random':
            # Random: posizione completamente casuale nel range
            return self.pointer_start + random.uniform(0, self.pointer_random_range)*self.sampleDurSec
        
        if self.pointer_jitter > 0.0:
            jitter_deviation = random.uniform(-self.pointer_jitter, self.pointer_jitter)
            return base_pos + jitter_deviation
        else:
            return base_pos
        
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
            grain_dur = self._safe_evaluate(self.grain_duration,elapsed_time,min_val=0.001,max_val=10.0)
            # Calcola pointer position (dove leggere nel sample)
            pointer_pos = self._calculate_pointer(grain_count, current_onset)
            # PITCH_RATIO (con envelope support + safety)
            if self.pitch_semitones_envelope is not None:
                # Envelope di semitoni → valuta e converti a ratio
                semitones = self._safe_evaluate(self.pitch_semitones_envelope,elapsed_time,-36, 36)  # ±3 ottave in semitoni
                pitch_ratio = pow(2.0, semitones / 12.0)
            else:
                # Numero fisso o envelope di ratio
                pitch_ratio = self._safe_evaluate(self.pitch_ratio,elapsed_time,0.125, 8.0)  # ±3 ottave come ratio
            # VOLUME (con envelope support + safety)
            volume = self._safe_evaluate(self.volume,elapsed_time,-120, 12)  # dB range: da quasi silenzio a +12dB
            # PAN (con envelope support + safety)
            pan = self._safe_evaluate(self.pan,elapsed_time,0.0, 1.0)  # stereo field: 0=left, 1=right

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
                grain_reverse=self.grain_reverse
            )
            self.grains.append(grain)
            # Calcola quando parte il PROSSIMO grano
            inter_onset = self._calculate_inter_onset_time()
            current_onset += inter_onset
            grain_count += 1     
            # Safety check per async (evita loop infiniti)
        self.generated = True
        return self.grains

    def __repr__(self):
        return (f"Stream(id={self.stream_id}, onset={self.onset}, "
                f"dur={self.duration}, grains={len(self.grains)})")
