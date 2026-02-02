from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Grain:
    """
    Rappresentazione immutabile di un singolo evento granulare.
    Usa slots=True per ottimizzare la memoria su grandi quantità di istanze.
    """
    onset: float
    duration: float
    pointer_pos: float
    pitch_ratio: float
    volume: float
    pan: float
    sample_table: int
    envelope_table: int

    def to_score_line(self) -> str:
        """Genera la linea di score Csound."""
        # Nota: l'accesso agli attributi è più veloce con slots
        return (f'i "Grain" {self.onset:.6f} {self.duration:.6f} '
                f'{self.pointer_pos:.6f} {self.pitch_ratio:.6f} '
                f'{self.volume:.2f} {self.pan:.3f} '
                f'{self.sample_table} {self.envelope_table}\n')