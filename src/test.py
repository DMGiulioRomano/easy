import yaml
import random

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
        # === DENSITY ===
        self.density = params['density']  # grains/sec (Hz)
        # === GRAIN ===
        self.grain_duration = params['grain']['duration']
        self.grain_envelope = params['grain']['envelope']
        # === POINTER ===
        self.pointer_start = params['pointer']['start']
        self.pointer_mode = params['pointer']['mode']
        self.pointer_speed_read = params['pointer'].get('speedRead', 1.0)  # ← NUOVO!        # === PLAYBACK ===
        # === PLAYBACK ===
        self.pitch_ratio = params['playback']['pitchRatio']  # ← RINOMINATO da speed
        self.volume = params['playback']['volume']
        # === SPATIAL ===
        self.pan = params['spatial']['pan']
        # === AUDIO ===
        self.sample_path = params['sample']
        # === CSOUND REFERENCES (assegnati dal Generator) ===
        self.sample_table_num = None
        self.envelope_table_num = None
        # === CALCOLI ===
        self.num_grains = int(self.duration / self.grain_duration)
        # === STATE ===
        self.grains = []
        self.generated = False  

    def _calculate_inter_onset_time(self, iteration):
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
    

    def _calculate_pointer(self, grain_index, current_time):
        """Calcola pointer position per grano i-esimo"""
        if self.pointer_mode == 'freeze':
            return self.pointer_start

        elif self.pointer_mode == 'linear':
            # Avanza in base a quanto sample viene letto
            sample_read_per_grain = self.grain_duration * self.pointer_speed_read
            return self.pointer_start + grain_index * sample_read_per_grain
        
       
        elif self.pointer_mode == 'linear':
            # Avanza linearmente in base a quanto sample viene letto
            # speedRead controlla la velocità di avanzamento del pointer
            elapsed_time = current_time - self.onset
            sample_read = elapsed_time * self.pointer_speed_read
            return self.pointer_start + sample_read
                
        elif self.pointer_mode == 'random':
            # Pointer casuale (per granular clouds)
            # TODO: implementare con range definibile
            return self.pointer_start + random.uniform(0, 1.0)
        
        else:
            raise NotImplementedError(f"Mode {self.pointer_mode} not implemented")

    def generate_grains(self):
        """Genera la sequenza di grani (synchronous, sequenziale)"""
        current_onset = self.onset  # punto di partenza dello stream
        
        for i in range(self.num_grains):
            # Calcola pointer position (dove leggere nel sample)
            pointer_pos = self._calculate_pointer(i)
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
            current_onset += self.grain_duration
        self.generated = True
        return self.grains



class GranularGenerator:
    def __init__(self, yaml_path):
        self.yaml_path = yaml_path
        self.data = None
        self.streams = []
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
    
    def create_streams(self):
        """Crea gli oggetti Stream dai dati YAML"""
        if not self.data:
            raise ValueError("Devi chiamare load_yaml() prima!")
        
        for stream_data in self.data['streams']:
            # Crea lo stream
            stream = Stream(stream_data)
            
            # Assegna i numeri delle ftable
            sample_table = self.generate_ftable_for_sample(stream.sample_path)
            envelope_table = self.generate_ftable_for_envelope(stream.grain_envelope)
            
            stream.sample_table_num = sample_table
            stream.envelope_table_num = envelope_table
            
            # Genera i grani
            stream.generate_grains()
            
            self.streams.append(stream)
        
        return self.streams

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
        f.write("; " + "="*77 + "\n")
        f.write("; GRAIN EVENTS\n")
        f.write("; " + "="*77 + "\n\n")
        
        for stream in self.streams:
            f.write(f'; Stream: {stream.stream_id}\n')
            f.write(f'; Grains: {len(stream.grains)}\n')
            f.write(f'; Duration: {stream.duration}s\n\n')
            
            for grain in stream.grains:
                f.write(grain.to_score_line())
            
            f.write('\n')

    def generate_score_file(self, output_path='output.sco'):
        """Genera il file .sco completo"""
        with open(output_path, 'w') as f:
            # Header
            f.write("; " + "="*77 + "\n")
            f.write("; GRANULAR SYNTHESIS SCORE\n")
            f.write(f"; Generated from: {self.yaml_path}\n")
            f.write("; " + "="*77 + "\n\n")
            
            # Function tables
            self.write_score_header(f)
            
            # Grain events
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
        generator = GranularGenerator(yaml_file)
        
        # Carica YAML
        print(f"Caricamento {yaml_file}...")
        generator.load_yaml()
        
        # Crea gli stream e genera i grani
        print("Generazione streams...")
        generator.create_streams()
        
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