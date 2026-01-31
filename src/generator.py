# src/generator.py
"""
Generator: orchestratore principale del sistema di sintesi granulare.

Refactored per separare le responsabilità:
- FtableManager: gestione function tables
- ScoreWriter: scrittura file .sco
- Generator: orchestrazione e coordinamento

Mantiene backward compatibility con l'API pubblica esistente.
"""
import yaml
import re
import math
from typing import List, Tuple, Dict, Any

from stream import Stream
from testina import Testina
from ftable_manager import FtableManager
from score_writer import ScoreWriter
from window_controller import WindowController

class Generator:
    """
    Orchestratore principale per generazione score Csound.
    
    Responsabilita:
    - Caricare e preprocessare configurazione YAML
    - Creare Stream e Testine dai dati YAML
    - Coordinare FtableManager e ScoreWriter
    - Applicare logica solo/mute
    
    Public API (backward compatible):
    - load_yaml() -> dict
    - create_elements() -> Tuple[List[Stream], List[Testina]]
    - generate_score_file(output_path: str) -> None
    
    Attributes:
        yaml_path: path file configurazione YAML
        data: dati YAML preprocessati
        streams: lista Stream creati
        testine: lista Testine create
        ftable_manager: gestore function tables
        score_writer: scrittore file score
    """
    
    def __init__(self, yaml_path: str):
        """
        Inizializza il Generator.
        
        Args:
            yaml_path: percorso file YAML di configurazione
        """
        self.yaml_path = yaml_path
        self.data: Dict[str, Any] = None
        self.streams: List[Stream] = []
        self.testine: List[Testina] = []
        
        # Delegati specializzati
        self.ftable_manager = FtableManager(start_num=1)
        self.score_writer = ScoreWriter(self.ftable_manager)
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def load_yaml(self) -> dict:
        """
        Carica e preprocessa il file YAML.
        
        Valuta espressioni matematiche nelle stringhe (e.g., "(pi)", "(10/2)").
        
        Returns:
            dict: dati YAML preprocessati
            
        Raises:
            FileNotFoundError: se il file YAML non esiste
            yaml.YAMLError: se il file YAML è malformato
        """
        with open(self.yaml_path, 'r') as f:
            raw_data = yaml.safe_load(f)
        
        self.data = self._eval_math_expressions(raw_data)
        return self.data
    
    def create_elements(self) -> Tuple[List[Stream], List[Testina]]:
        """
        Crea Stream e Testine dai dati YAML.
        
        Applica logica solo/mute, registra ftables, genera grani.
        
        Returns:
            tuple: (streams, testine)
            
        Raises:
            ValueError: se load_yaml() non è stato chiamato
        """
        if self.data is None:
            raise ValueError("Devi prima caricare il YAML con load_yaml()")
        
        # Estrai e filtra stream
        stream_data_list = self.data.get('streams', [])
        filtered_streams = self._filter_solo_mute(stream_data_list)
        
        # Crea stream (QUI viene chiamato _register_stream_windows)
        self._create_streams(filtered_streams)
        
        # Crea testine
        testina_data_list = self.data.get('testine', [])
        if testina_data_list:
            self._create_testine(testina_data_list)
        
        return self.streams, self.testine


    def generate_score_file(self, output_path: str = 'output.sco'):
        """
        Genera il file score Csound completo.
        
        Delega la scrittura a ScoreWriter.
        
        Args:
            output_path: percorso file .sco output
        """
        self.score_writer.write_score(
            filepath=output_path,
            streams=self.streams,
            testine=self.testine,
            yaml_source=self.yaml_path
        )
    
    # =========================================================================
    # CREAZIONE STREAM
    # =========================================================================
    
    def _create_streams(self, stream_data_list: list):
        """
        Crea gli stream granulari applicando logica solo/mute.
        
        Args:
            stream_data_list: lista dizionari parametri stream da YAML
        """        
        print(f"Creazione di {len(stream_data_list)} stream...")
        
        for stream_data in stream_data_list:
            # 1. Crea stream
            stream = Stream(stream_data)
            
            # 2. Registra ftable sample
            stream.sample_table_num = self.ftable_manager.register_sample(stream.sample)
            
            # 3. Pre-registra tutte le finestre possibili
            # CHIAMATA QUI ↓
            stream.window_table_map = self._register_stream_windows(stream_data)
            
            # 4. Genera grani
            stream.generate_grains()
            
            self.streams.append(stream)
            print(f"  → Stream '{stream.stream_id}': {stream}")
    
    def _filter_solo_mute(self, stream_data_list: list) -> list:
        """
        Applica logica solo/mute agli stream.
        
        Regole:
        - Se almeno uno stream ha 'solo' → prendi SOLO quelli con 'solo'
        - Altrimenti → prendi tutti TRANNE quelli con 'mute'
        
        Args:
            stream_data_list: lista dizionari stream
            
        Returns:
            list: stream filtrati
        """
        # Controlla se c'è almeno un solo
        solo_mode = any('solo' in s for s in stream_data_list)
        
        if solo_mode:
            # Modalità SOLO: prendi solo quelli con flag 'solo'
            filtered = [s for s in stream_data_list if 'solo' in s]
            print(
                f"⚡ SOLO MODE: creazione di {len(filtered)} stream "
                f"(su {len(stream_data_list)} totali)"
            )
        else:
            # Modalità normale: escludi solo quelli muted
            filtered = [s for s in stream_data_list if 'mute' not in s]
            muted_count = len(stream_data_list) - len(filtered)
            
            if muted_count > 0:
                print(f"🔇 {muted_count} stream muted")
        
        return filtered
    
    # =========================================================================
    # CREAZIONE TESTINE
    # =========================================================================
    
    def _create_testine(self, testina_data_list: list):
        """
        Crea le testine tape recorder.
        
        Args:
            testina_data_list: lista dizionari parametri testina da YAML
        """
        print(f"Creazione di {len(testina_data_list)} testine tape recorder...")
        
        for testina_data in testina_data_list:
            # Crea testina
            testina = Testina(testina_data)
            
            # Registra ftable sample
            testina.sample_table_num = self.ftable_manager.register_sample(
                testina.sample_path
            )
            
            self.testine.append(testina)
            print(f"  → Testina '{testina.testina_id}': {testina}")
    
    # =========================================================================
    # PREPROCESSING YAML
    # =========================================================================
    
    def _eval_math_expressions(self, obj):
        """
        Valuta espressioni matematiche nei valori YAML.
        
        Riconosce pattern "(espressione)" e valuta l'espressione.
        Supporta: operatori aritmetici, costanti (pi, e), funzioni base.
        
        Args:
            obj: oggetto da preprocessare (dict, list, str, number)
            
        Returns:
            oggetto con espressioni valutate
            
        Examples:
            "(10 + 5)" → 15
            "(pi * 2)" → 6.283...
            "(max(3, 7))" → 7
        """
        # Ricorsione su dict
        if isinstance(obj, dict):
            return {
                k: self._eval_math_expressions(v) 
                for k, v in obj.items()
            }
        
        # Ricorsione su list
        elif isinstance(obj, list):
            return [self._eval_math_expressions(item) for item in obj]
        
        # Valutazione stringhe con pattern (...)
        elif isinstance(obj, str):
            # Regex: cattura espressioni tra parentesi
            # Supporta lettere per costanti (pi, e) e funzioni
            pattern = r'\(([a-zA-Z0-9+\-*/.() ]+)\)'
            
            def evaluate_match(match):
                expr = match.group(1)
                try:
                    # Dizionario funzioni/costanti sicure
                    safe_dict = {
                        'abs': abs,
                        'int': int,
                        'float': float,
                        'min': min,
                        'max': max,
                        'pow': pow,
                        'pi': math.pi,
                        'e': math.e
                    }
                    
                    # Valuta espressione in ambiente sicuro
                    result = eval(expr, {"__builtins__": {}}, safe_dict)
                    return str(result)
                    
                except Exception as e:
                    print(
                        f"⚠️  Warning: impossibile valutare '{expr}': {e}"
                    )
                    # Ritorna espressione originale se fallisce
                    return match.group(0)
            
            # Sostituisci tutte le espressioni
            evaluated = re.sub(pattern, evaluate_match, obj)
            
            # Converti in numero se possibile
            try:
                return float(evaluated) if '.' in evaluated else int(evaluated)
            except ValueError:
                return evaluated
        
        # Altri tipi: passa through
        else:
            return obj
        
    def _register_stream_windows(self, stream_data: dict) -> dict:
        """Pre-registra tutte le finestre per questo stream."""
        stream_id = stream_data.get('stream_id', 'unknown')
        
        # USA METODO STATICO (no istanza temporanea!)
        possible_windows = WindowController.parse_window_list(
            params=stream_data.get('grain', {}),
            stream_id=stream_id
        )
        
        # Registra tutte le finestre nel FtableManager
        window_map = {}
        for window_name in possible_windows:
            table_num = self.ftable_manager.register_window(window_name)
            window_map[window_name] = table_num
        
        return window_map