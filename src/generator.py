# =============================================================================
# GENERATOR (gestisce sia Stream che Testina)
# =============================================================================
import yaml
from stream import Stream
from testina import Testina

class Generator:
    def __init__(self, yaml_path):
        self.yaml_path = yaml_path
        self.data = None
        self.streams = []      # Stream granulari
        self.testine = []      # Testine tape recorder
        self.ftables = {}  # {table_num: (type, path/params)}
        self.next_table_num = 1


    def _eval_math_expressions(self, obj):
        """Valuta espressioni matematiche nei valori YAML"""
        import re
        import math
        
        if isinstance(obj, dict):
            return {k: self._eval_math_expressions(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._eval_math_expressions(item) for item in obj]
        elif isinstance(obj, str):
            pattern = r'\(([0-9+\-*/.() ]+)\)'
            def evaluate_match(match):
                expr = match.group(1)
                try:
                    safe_dict = {
                        'abs': abs, 'int': int, 'float': float,
                        'min': min, 'max': max, 'pow': pow,
                        'pi': math.pi, 'e': math.e
                    }
                    result = eval(expr, {"__builtins__": {}}, safe_dict)
                    return str(result)
                except Exception as e:
                    print(f"⚠️  Warning: impossibile valutare '{expr}': {e}")
                    return match.group(0)
            
            evaluated = re.sub(pattern, evaluate_match, obj)
            try:
                return float(evaluated) if '.' in evaluated else int(evaluated)
            except ValueError:
                return evaluated
        else:
            return obj
        
    def load_yaml(self):
        """Carica e parsa il file YAML"""
        with open(self.yaml_path, 'r') as f:
            raw_data = yaml.safe_load(f)
        self.data = self._eval_math_expressions(raw_data)
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
                # GEN20 windows
                if param == 'hamming':
                    f.write(f'f {num} 0 1024 20 1 1\n\n')
                elif param == 'hanning':
                    f.write(f'f {num} 0 1024 20 2 1\n\n')
                elif param == 'bartlett' or param == 'triangle':
                    f.write(f'f {num} 0 1024 20 3 1\n\n')
                elif param == 'blackman':
                    f.write(f'f {num} 0 1024 20 4 1\n\n')
                elif param == 'blackman_harris':
                    f.write(f'f {num} 0 1024 20 5 1\n\n')
                elif param == 'gaussian':
                    # opt=3 è un buon default (più stretto = valori più alti)
                    f.write(f'f {num} 0 1024 20 6 1 3\n\n')
                elif param == 'kaiser':
                    # opt=6 è un buon compromesso
                    f.write(f'f {num} 0 1024 20 7 1 6\n\n')
                elif param == 'rectangle':
                    f.write(f'f {num} 0 1024 20 8 1\n\n')
                elif param == 'sinc':
                    f.write(f'f {num} 0 1024 20 9 1 1\n\n')
                # GEN09 per half_sine (non è in GEN20)
                elif param == 'half_sine':
                    f.write(f'f {num} 0 1024 9 0.5 1 0\n\n')
                # === GEN16 per curve asimmetriche (expodec/exporise) ===
                elif param == 'expodec':
                    # 1 → 0, decay esponenziale (concavo)
                    f.write(f'f {num} 0 1024 16 1 1024 4 0\n\n')
                elif param == 'expodec_strong':
                    # decay più aggressivo
                    f.write(f'f {num} 0 1024 16 1 1024 10 0\n\n')
                elif param == 'exporise':
                    # 0 → 1, rise esponenziale (convesso)
                    f.write(f'f {num} 0 1024 16 0 1024 -4 1\n\n')
                elif param == 'exporise_strong':
                    # rise più aggressivo
                    f.write(f'f {num} 0 1024 16 0 1024 -10 1\n\n')
                elif param == 'rexpodec':
                    # "reverse expodec" - decay lento poi veloce (convesso)
                    f.write(f'f {num} 0 1024 16 1 1024 -4 0\n\n')
                elif param == 'rexporise':
                    # "reverse exporise" - rise veloce poi lento (concavo)
                    f.write(f'f {num} 0 1024 16 0 1024 4 1\n\n')
                # Default: hanning
                else:
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

