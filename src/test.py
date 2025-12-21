import yaml
import random

# Aggiungi questa classe in test.py

class Testina:
    """
    Testina di lettura semplice (tape recorder head)
    Legge un file audio in modo lineare senza granulazione
    """
    def __init__(self, params):
        # === IDENTITÀ ===
        self.testina_id = params['testina_id']
        
        # === TIMING ===
        self.onset = params['onset']
        self.duration = params['duration']
        
        # === PLAYBACK ===
        self.sample_path = params['sample']
        self.start_position = params.get('start_position', 0.0)  # secondi
        self.speed = params.get('speed', 1.0)  # 1.0 = normale
        
        # === LOOP (opzionale) ===
        self.loop = params.get('loop', False)
        self.loop_start = params.get('loop_start', 0.0)
        self.loop_end = params.get('loop_end', None)  # None = fine file
                
        # === OUTPUT ===
        self.volume = params.get('volume', 0.0)  # dB
        self.pan = params.get('pan', 0.5)  # 0=L, 0.5=C, 1=R
        
        # === CSOUND REFERENCE ===
        self.sample_table_num = None  # verrà assegnato dal Generator
    
    def to_score_line(self):
        """Genera la linea di score per Csound"""
        # i "TapeRecorder" onset duration start speed pitch volume pan loop sample_table
        loop_flag = 1 if self.loop else 0

        loop_start_val = self.loop_start if self.loop_start is not None else -1
        loop_end_val = self.loop_end if self.loop_end is not None else -1

        return (f'i "TapeRecorder" {self.onset:.6f} {self.duration:.6f} '
                f'{self.start_position:.6f} {self.speed:.6f} '
                f'{self.volume:.2f} {self.pan:.3f} '
                f'{loop_flag} {loop_start_val:.6f} {loop_end_val:.6f} '
                f'{self.sample_table_num}\n')
    
    def __repr__(self):
        return (f"Testina(id={self.testina_id}, onset={self.onset}, "
                f"dur={self.duration}, speed={self.speed})")
    
class Grain:
    def __init__(self, onset, duration, pointer_pos, pitch_ratio, volume, pan, sample_table, envelope_table):
        self.onset = onset         
        self.duration = duration   
        self.pointer_pos = pointer_pos
        self.pitch_ratio = pitch_ratio
        self.volume = volume
        self.pan = pan
        self.sample_table = sample_table
        self.envelope_table = envelope_table

    def to_score_line(self):
        """Genera la linea di score Csound"""
        return f'i "Grain" {self.onset:.6f} {self.duration} {self.pointer_pos:.6f} {self.pitch_ratio} {self.volume} {self.pan} {self.sample_table} {self.envelope_table}\n'


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
        self.density = params['density']  # grains/sec (Hz)
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


# =============================================================================
# GENERATOR (gestisce sia Stream che Testina)
# =============================================================================

class Generator:
    def __init__(self, yaml_path):
        self.yaml_path = yaml_path
        self.data = None
        self.streams = []      # Stream granulari
        self.testine = []      # Testine tape recorder
        self.ftables = {}  # {table_num: (type, path/params)}
        self.next_table_num = 1

    def load_yaml(self):
        """Carica e parsa il file YAML"""
        with open(self.yaml_path, 'r') as f:
            self.data = yaml.safe_load(f)
        return self.data
    
    def generate_ftable_for_sample(self, sample_path):
        """Genera numero ftable per un sample (evita duplicati)"""
        # Controlla se il sample è già stato caricato
        for num, (ftype, param) in self.ftables.items():
            if ftype == 'sample' and param == sample_path:
                return num  # riusa lo stesso numero        
        # Altrimenti crea nuovo
        table_num = self.next_table_num
        self.next_table_num += 1
        self.ftables[table_num] = ('sample', sample_path)
        return table_num
    
    def generate_ftable_for_envelope(self, envelope_type):
        """Genera numero ftable per un envelope (evita duplicati)"""
        # Controlla se l'envelope è già stato creato
        for num, (ftype, param) in self.ftables.items():
            if ftype == 'envelope' and param == envelope_type:
                return num
        
        table_num = self.next_table_num
        self.next_table_num += 1
        self.ftables[table_num] = ('envelope', envelope_type)
        return table_num
    
    def create_elements(self):
        """Crea gli oggetti Stream dai dati YAML"""
        if not self.data:
            raise ValueError("Devi chiamare load_yaml() prima!")

        # Crea STREAMS (granular synthesis)
        if 'streams' in self.data:
            print(f"Creazione di {len(self.data['streams'])} streams granulari...")
            for stream_data in self.data['streams']:
                # Crea lo stream
                stream = Stream(stream_data)
                # Assegna i numeri delle ftable            
                stream.sample_table_num = self.generate_ftable_for_sample(stream.sample_path)
                stream.envelope_table_num = self.generate_ftable_for_envelope(stream.grain_envelope)
                # Genera i grani
                stream.generate_grains()
                self.streams.append(stream)

        # Crea TESTINE (tape recorder)
        if 'testine' in self.data:
            print(f"Creazione di {len(self.data['testine'])} testine tape recorder...")
            for testina_data in self.data['testine']:
                testina = Testina(testina_data)
                testina.sample_table_num = self.generate_ftable_for_sample(testina.sample_path)
                self.testine.append(testina)
                print(f"  → Testina '{testina.testina_id}': {testina}")
        
        return self.streams, self.testine

    def write_score_header(self, f):
        """Scrive header con ftables"""
        f.write("; " + "="*77 + "\n")
        f.write("; FUNCTION TABLES\n")
        f.write("; " + "="*77 + "\n\n")
        
        for num, (ftype, param) in sorted(self.ftables.items()):
            if ftype == 'sample':
                f.write(f'; Sample: {param}\n')
                f.write(f'f {num} 0 0 1 "{param}" 0 0 1\n\n')
            
            elif ftype == 'envelope':
                f.write(f'; Envelope: {param}\n')
                # Mappare envelope_type -> GEN routine
                if param == 'hanning':
                    f.write(f'f {num} 0 1024 20 2 1\n\n')
                elif param == 'half_sine':
                    f.write(f'f {num} 0 1024 9 0.5 1 0\n\n')
                else:
                    # Default: hanning
                    f.write(f'f {num} 0 1024 20 2 1\n\n')

    def write_score_events(self, f):
        """Scrive gli eventi dei grani"""
        # GRANULAR EVENTS
        if self.streams:
            f.write("; " + "="*77 + "\n")
            f.write("; GRANULAR STREAMS\n")
            f.write("; " + "="*77 + "\n\n")
            
            for stream in self.streams:
                f.write(f'; Stream: {stream.stream_id}\n')
                f.write(f'; Density: {stream.density} g/s, Distribution: {stream.distribution}\n')
                f.write(f'; Grain duration: {stream.grain_duration*1000:.1f}ms\n')
                f.write(f'; Total grains: {len(stream.grains)}\n\n')
                
                for grain in stream.grains:
                    f.write(grain.to_score_line())
                f.write('\n')
        
        # TAPE RECORDER EVENTS
        if self.testine:
            f.write("; " + "="*77 + "\n")
            f.write("; TAPE RECORDER TRACKS\n")
            f.write("; " + "="*77 + "\n\n")
            
            for testina in self.testine:
                f.write(f'; Testina: {testina.testina_id}\n')
                f.write(f'; Sample: {testina.sample_path}\n')
                f.write(f'; Speed: {testina.speed}x (resampling)\n')
                f.write(f'; Duration: {testina.duration}s\n\n')
                f.write(testina.to_score_line())
                f.write('\n')

    def generate_score_file(self, output_path='output.sco'):
        """Genera il file .sco completo"""
        with open(output_path, 'w') as f:
            # Header
            f.write("; " + "="*77 + "\n")
            f.write("; CSOUND SCORE\n")
            f.write(f"; Generated from: {self.yaml_path}\n")
            f.write("; " + "="*77 + "\n\n")
            
            # Function tables
            self.write_score_header(f)
            self.write_score_events(f)
            
            # End marker
            f.write('; End of score\n')
            f.write('e\n')
        
        print(f"✓ Score generato: {output_path}")
        print(f"  - {len(self.ftables)} function tables")
        print(f"  - {len(self.streams)} streams")
        total_grains = sum(len(s.grains) for s in self.streams)
        print(f"  - {total_grains} grains totali")

# =============================================================================
# MAIN
# =============================================================================

def main():
    import sys
    
    # Verifica argomenti
    if len(sys.argv) < 2:
        print("Uso: python granular_generator.py <file.yml> [output.sco]")
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.sco'
    
    try:
        # Crea il generatore
        generator = Generator(yaml_file)
        
        # Carica YAML
        print(f"Caricamento {yaml_file}...")
        generator.load_yaml()
        
        # Crea gli stream e genera i grani
        print("Generazione streams...")
        generator.create_elements()
        
        # Genera il file score
        print(f"Scrittura score...")
        generator.generate_score_file(output_file)
        
        print("\n✓ Generazione completata!")
        
    except FileNotFoundError:
        print(f"✗ Errore: file '{yaml_file}' non trovato")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()