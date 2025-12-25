import random
from grain import Grain

class Stream:
    def __init__(self, params):
        # === IDENTITÀ ===
        self.stream_id = params['stream_id']
        # === TIMING ===
        self.onset = params['onset']
        self.duration = params['duration']
        # === GRAIN PARAMETERS ===
        self.grain_duration = params['grain']['duration']
        self.grain_envelope = params['grain']['envelope']
        # === DENSITY ===
        if 'overlap_factor' in params['grain']:
            overlap_factor = params['grain']['overlap_factor']
            self.density = overlap_factor / self.grain_duration
        else:
            self.density = params['density']

        # === DISTRIBUTION (0=sync, 1=async) ===
        self.distribution = params.get('distribution', 0.0)        
        # === POINTER ===
        self.pointer_start = params['pointer']['start']
        self.pointer_mode = params['pointer']['mode']
        self.pointer_speed = params['pointer'].get('speed', 1.0)
        self.pointer_jitter = params['pointer'].get('jitter', 0.0)  # ← AGGIUNTO
        self.pointer_random_range = params['pointer'].get('random_range', 1.0)  # ← AGGIUNTO (opzionale)        # === PLAYBACK ===
        # Converti semitoni in pitch ratio: 2^(semitones/12)
        shift_semitones = params['pitch'].get('shift_semitones', 0)
        self.pitch_ratio = pow(2.0, shift_semitones / 12.0)
        # === OUTPUT ===
        self.volume = params['output']['volume']
        self.pan = params['output']['pan']
        # === AUDIO ===
        self.sample_path = params['sample']
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
    

    def _calculate_pointer(self):
        """
        Calcola la posizione di lettura nel sample per questo grano
        Args:
            grain_index: indice del grano (per modalità sequenziali)
            current_time: tempo corrente nello stream (per modalità time-based)
        Returns:
            float: posizione in secondi nel sample
        """
        if self.pointer_mode == 'freeze':
            base_pos = self.pointer_start
            
        elif self.pointer_mode == 'linear':
            sample_position = self._cumulative_read_time * self.pointer_speed
            base_pos = self.pointer_start + sample_position
            
        elif self.pointer_mode == 'reverse':
            sample_position = self._cumulative_read_time * self.pointer_speed
            base_pos = self.pointer_start - sample_position
            
        elif self.pointer_mode == 'loop':
            loop_start = self.pointer_params.get('loop_start', 0.0)
            loop_end = self.pointer_params.get('loop_end', 1.0)
            loop_duration = loop_end - loop_start
            
            sample_position = self._cumulative_read_time * self.pointer_speed
            looped_position = (sample_position % loop_duration)
            base_pos = loop_start + looped_position
            
        elif self.pointer_mode == 'random':
            # Random: posizione completamente casuale nel range
            return self.pointer_start + random.uniform(0, self.pointer_random_range)
            
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
        # Numero totale di grani basato su DENSITY
        # (approssimativo per async, ma va bene)
        current_onset = self.onset  # punto di partenza dello stream
        stream_end = self.onset + self.duration        
        grain_count = 0
        while current_onset < stream_end:
            # Calcola pointer position (dove leggere nel sample)
            pointer_pos = self._calculate_pointer()
            # Crea il grano
            grain = Grain(
                onset=current_onset,
                duration=self.grain_duration,
                pointer_pos=pointer_pos,
                pitch_ratio=self.pitch_ratio,
                volume=self.volume,
                pan=self.pan,
                sample_table=self.sample_table_num,
                envelope_table=self.envelope_table_num
            )
            self.grains.append(grain)
            # Calcola quando parte il PROSSIMO grano
            inter_onset = self._calculate_inter_onset_time()
            current_onset += inter_onset
            self._cumulative_read_time += inter_onset
            grain_count += 1     
            # Safety check per async (evita loop infiniti)
            if grain_count > self.estimated_num_grains * 3:
                print(f"⚠️  Warning: {self.stream_id} generò troppi grani, stop at {grain_count}")
                break
        self.generated = True
        # Info debug
        actual_density = len(self.grains) / self.duration
        print(f"  → Stream '{self.stream_id}': {len(self.grains)} grains "
              f"(target density: {self.density:.1f} g/s, "
              f"actual: {actual_density:.1f} g/s)")
        return self.grains

