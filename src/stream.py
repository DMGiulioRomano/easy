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
        shift_semitones = params['pitch'].get('shift_semitones', 0)
        self.pitch_ratio = pow(2.0, shift_semitones / 12.0)
        # === POINTER ===
        self.pointer_start = params['pointer']['start']
        self.pointer_mode = params['pointer']['mode']
        if self.pointer_mode == 'loop':
            # normalizzati tra 0 e 1.
            self.loopstart = params['pointer'].get('loopstart', 0.0)
            self.loopdur = params['pointer'].get('loopdur', 1.0)
        # pointer_speed può essere un numero fisso o un Envelope
        speed_param = params['pointer'].get('speed', 1.0)

        if isinstance(speed_param, (int, float)):
            # Numero singolo → usa direttamente (efficiente!)
            self.pointer_speed = speed_param
        elif isinstance(speed_param, dict):
            # Dict con 'type' e 'points' → crea Envelope
            self.pointer_speed = Envelope(speed_param)
        elif isinstance(speed_param, list):
            # Lista di breakpoints → Envelope lineare
            self.pointer_speed = Envelope(speed_param)
        else:
            raise ValueError(f"pointer.speed formato non valido: {speed_param}")

        self.pointer_jitter = params['pointer'].get('jitter', 0.0)  
        self.pointer_random_range = params['pointer'].get('random_range', 1.0)
        # === GRAIN PARAMETERS ===
        self.grain_duration = params['grain']['duration']
        self.grain_envelope = params['grain'].get('envelope','hanning')
        # === DENSITY ===
        if 'overlap_factor' in params['grain']:
            overlap_factor = params['grain']['overlap_factor']
            self.density = overlap_factor / self.grain_duration
        else:
            self.density = params['density']
            # Default grain.reverse dipende da pointer.mode
        if 'reverse' in params['grain']:
            # Utente ha specificato esplicitamente → usa quello
            self.grain_reverse = params['grain']['reverse']
        else:
            # AUTO-DEDUZIONE dal pointer mode
            if self.pointer_mode == 'reverse':
                self.grain_reverse = True   # reverse→reverse
            else:
                self.grain_reverse = False  # linear/freeze/loop/random→forward       
        # === OUTPUT ===
        self.volume = params['output']['volume']
        self.pan = params['output']['pan']
        # === AUDIO ===
        self.sample_path = params['sample']
        self.sampleDurSec = get_sample_duration(self.sample_path)
        # === CSOUND REFERENCES (assegnati dal Generator) ===
        self.sample_table_num = None
        self.envelope_table_num = None
        self.estimated_num_grains = int(self.duration * self.density)
        # === STATE ===
        self._cumulative_read_time = 0.0  
        self.grains = []
        self.generated = False  

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
    

    def _calculate_pointer(self, grain_count, current_onset):
        """
        Calcola la posizione di lettura nel sample per questo grano.
        
        Prima usavo un tempo cumulativo basato su inter_onset ma così la posizione del sample è influenzata dalla densità dei grani. 
        Usa il TEMPO REALE trascorso dall'inizio dello stream. 
        Questo garantisce la separazione
        micro/macro di Truax (1994): la posizione nel sample (livello macro)
        è indipendente dalla density dei grani (livello micro).
        
        Formula base (mode linear):
            elapsed_time = current_onset - self.onset
            pointer_position = pointer_start + (elapsed_time × pointer_speed)
        
        Args:
            current_onset: tempo assoluto in secondi di quando parte questo grano
            
        Returns:
            float: posizione in secondi nel sample sorgente
        """        
        elapsed_time = current_onset - self.onset

        # Calcola la distanza percorsa nel sample
        if isinstance(self.pointer_speed, Envelope):
            # Envelope: integra la velocità nel tempo
            sample_position = self.pointer_speed.integrate(0, elapsed_time)
        else:
            # Numero fisso: semplice moltiplicazione (veloce!)
            sample_position = elapsed_time * self.pointer_speed

        if self.pointer_mode == 'freeze':
            base_pos = self.pointer_start
            
        elif self.pointer_mode == 'linear':
            base_pos = self.pointer_start + sample_position
            
        elif self.pointer_mode == 'reverse':
            start = self.pointer_start if grain_count == 0 else 0
            base_pos = (start - sample_position) % self.sampleDurSec
            
        elif self.pointer_mode == 'loop':            
            looped_position = (sample_position % self.loopdur)
            base_pos = self.loopstart + looped_position

        # capire che senso ha valore 1, perché dovrebbe essere in secondi...            
        elif self.pointer_mode == 'random':
            # Random: posizione completamente casuale nel range
            return self.pointer_start + random.uniform(0, self.pointer_random_range)*self.sampleDurSec
            
        else:
            raise NotImplementedError(f"Mode {self.pointer_mode} not implemented")
        
        # APPLICA JITTER alla posizione base (per tutti i mode tranne random)
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
            # Calcola pointer position (dove leggere nel sample)
            pointer_pos = self._calculate_pointer(grain_count, current_onset)
            # Crea il grano
            grain = Grain(
                onset=current_onset,
                duration=self.grain_duration,
                pointer_pos=pointer_pos,
                pitch_ratio=self.pitch_ratio,
                volume=self.volume,
                pan=self.pan,
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

