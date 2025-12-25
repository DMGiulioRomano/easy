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
