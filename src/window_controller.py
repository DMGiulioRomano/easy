# src/window_controller.py
from typing import List, Tuple, Dict, Any
from window_registry import WindowRegistry
import random
class WindowController:
    """Gestisce selezione grain envelope."""
    
    # =========================================================================
    # METODI STATICI (per Generator)
    # =========================================================================
    
    @staticmethod
    def parse_window_list(params: dict, stream_id: str = "unknown") -> List[str]:
        """
        Parse configurazione envelope e ritorna lista finestre possibili.
        
        Metodo statico senza stato, usato da Generator per pre-registrare ftables.
        
        Args:
            params: dict grain da YAML (es. {'envelope': 'all'})
            stream_id: per error messages
            
        Returns:
            Lista nomi finestre che potrebbero essere selezionate
        """
        envelope_spec = params.get('envelope', 'hanning')
        
        # Espansione 'all'
        if envelope_spec == 'all' or envelope_spec is True:
            return list(WindowRegistry.WINDOWS.keys())
        
        # Stringa singola
        if isinstance(envelope_spec, str):
            windows = [envelope_spec]
        # Lista esplicita
        elif isinstance(envelope_spec, list):
            if not envelope_spec:
                raise ValueError(
                    f"Stream '{stream_id}': Lista envelope vuota"
                )
            windows = envelope_spec
        else:
            raise ValueError(
                f"Stream '{stream_id}': Formato envelope non valido: {envelope_spec}"
            )
        
        # Validazione
        available = WindowRegistry.all_names()
        for window in windows:
            if window not in available:
                raise ValueError(
                    f"Stream '{stream_id}': "
                    f"Finestra '{window}' non trovata. "
                    f"Disponibili: {available}"
                )
        
        return windows
    
    # =========================================================================
    # METODI D'ISTANZA (per Stream)
    # =========================================================================
    
    def __init__(self, params: dict, dephase: dict = None, stream_id: str = "unknown"):
        """
        Inizializza controller per selezione runtime.
        
        Args:
            params: dict grain da YAML
            dephase: dict con probabilità
            stream_id: per logging
        """
        self._stream_id = stream_id
        
        # Riusa metodo statico per parsing
        self._windows = self.parse_window_list(params, stream_id)
        
        # Range e probability (aspetti dinamici)
        self._range = params.get('envelope_range', 0)
        self._prob = dephase.get('pc_rand_envelope') if dephase else None
    
    def select_window(self) -> str:
        """Seleziona finestra per grano corrente."""
        # Range disabilitato → deterministico
        if self._range == 0:
            return self._windows[0]
        
        # Check dephase probability
        if self._prob is not None:
            if random.random() * 100 > self._prob:
                return self._windows[0]
        
        # Variazione attiva → random
        return random.choice(self._windows)