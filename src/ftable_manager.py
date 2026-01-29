"""
FtableManager: gestione centralizzata delle function tables Csound.
Separato dalla logica di orchestrazione.
"""
from typing import Dict, Tuple, Optional
from window_registry import WindowRegistry

class FtableManager:
    """
    Gestisce allocazione e deduplicazione function tables.
    """
    
    def __init__(self, start_num: int = 1):
        """
        Args:
            start_num: primo numero tabella disponibile
        """
        self.tables: Dict[int, Tuple[str, str]] = {}  
        self.next_num = start_num
        self._sample_cache: Dict[str, int] = {}  
        self._window_cache: Dict[str, int] = {}
    
    def register_sample(self, sample_path: str) -> int:
        """
        Registra sample (con deduplicazione).
        
        Returns:
            int: numero tabella
        """
        if sample_path in self._sample_cache:
            return self._sample_cache[sample_path]
        
        num = self.next_num
        self.next_num += 1
        self.tables[num] = ('sample', sample_path)
        self._sample_cache[sample_path] = num
        return num
    
    def register_window(self, window_name: str) -> int:
        """
        Registra window (con deduplicazione).
        
        Returns:
            int: numero tabella
        """
        if window_name in self._window_cache:
            return self._window_cache[window_name]
        
        # Valida che l'window esista nel registro
        if WindowRegistry.get(window_name) is None:
            raise ValueError(
                f"window '{window_name}' non valido. "
                f"Validi: {', '.join(WindowRegistry.all_names())}"
            )
        
        num = self.next_num
        self.next_num += 1
        self.tables[num] = ('window', window_name)
        self._window_cache[window_name] = num
        return num
    
    def write_to_file(self, f) -> None:
        """Scrive tutte le ftables nel file score Csound."""
        f.write("; " + "="*77 + "\n")
        f.write("; FUNCTION TABLES\n")
        f.write("; " + "="*77 + "\n\n")
        
        for num, (ftype, key) in sorted(self.tables.items()):
            if ftype == 'sample':
                f.write(f'; Sample: {key}\n')
                f.write(f'f {num} 0 0 1 "{key}" 0 0 1\n\n')
            
            elif ftype == 'window':
                spec = WindowRegistry.get(key)
                f.write(f'; window: {key} - {spec.description}\n')
                statement = WindowRegistry.generate_ftable_statement(num, key)
                f.write(f'{statement}\n\n')