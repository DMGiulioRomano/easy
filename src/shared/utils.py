import random
import soundfile as sf
from typing import Any
# Path per i sample audio
PATHSAMPLES = './refs/'

def get_sample_duration(filepath: str) -> float:
    """Ottiene la durata di un file audio in secondi."""
    info = sf.info(PATHSAMPLES + filepath)
    return info.duration


def random_percent(percent: float = 90) -> bool:
    """Ritorna True con probabilità percent%."""
    return (percent / 100) > random.uniform(0, 1)

def get_nested(data: dict, path: str, default: Any) -> Any:
    """
    Naviga un dict con dot notation.
    
    Args:
        data: Dizionario da navigare
        path: Percorso in dot notation (es. 'grain.duration')
        default: Valore di default se il percorso non esiste
        
    Returns:
        Valore trovato o default
    """
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current