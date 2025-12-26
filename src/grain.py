class Grain:
    def __init__(self, onset, duration, pointer_pos, pitch_ratio, volume, pan, sample_table, envelope_table, grain_reverse=False):
        self.onset = onset         
        self.duration = duration   
        self.pointer_pos = pointer_pos
        self.pitch_ratio = pitch_ratio
        self.volume = volume
        self.pan = pan
        self.sample_table = sample_table
        self.envelope_table = envelope_table
        self.grain_reverse = grain_reverse

    def to_score_line(self):
        """Genera la linea di score Csound"""
        reverse_flag = 1 if self.grain_reverse else 0
        return (f'i "Grain" {self.onset:.6f} {self.duration} '
                f'{self.pointer_pos:.6f} {self.pitch_ratio} '
                f'{self.volume} {self.pan} '
                f'{self.sample_table} {self.envelope_table} '
                f'{reverse_flag}\n')  