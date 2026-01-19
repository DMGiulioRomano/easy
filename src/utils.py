import random
import soundfile as sf
# Path per i sample audio
PATHSAMPLES = './refs/'


def get_sample_duration(filepath: str) -> float:
    """Ottiene la durata di un file audio in secondi."""
    info = sf.info(PATHSAMPLES + filepath)
    return info.duration


def random_percent(percent: float = 90) -> bool:
    """Ritorna True con probabilità percent%."""
    return (percent / 100) > random.uniform(0, 1)

