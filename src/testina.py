class Testina:
    """
    Testina di lettura semplice (tape recorder head)
    Legge un file audio in modo lineare senza granulazione
    """
    def __init__(self, params):
        # === IDENTITÀ ===
        self.testina_id = params['testina_id']
        
        # === TIMING ===
        self.onset = params['onset']
        self.duration = params['duration']
        
        # === PLAYBACK ===
        self.sample_path = params['sample']
        self.start_position = params.get('start_position', 0.0)  # secondi
        self.speed = params.get('speed', 1.0)  # 1.0 = normale
        
        # === LOOP (opzionale) ===
        self.loop = params.get('loop', False)
        self.loop_start = params.get('loop_start', 0.0)
        self.loop_end = params.get('loop_end', None)  # None = fine file
                
        # === OUTPUT ===
        self.volume = params.get('volume', 0.0)  # dB
        self.pan = params.get('pan', 0.5)  # 0=L, 0.5=C, 1=R
        
        # === CSOUND REFERENCE ===
        self.sample_table_num = None  # verrà assegnato dal Generator
    
    def to_score_line(self):
        """Genera la linea di score per Csound"""
        # i "TapeRecorder" onset duration start speed pitch volume pan loop sample_table
        loop_flag = 1 if self.loop else 0

        loop_start_val = self.loop_start if self.loop_start is not None else -1
        loop_end_val = self.loop_end if self.loop_end is not None else -1

        return (f'i "TapeRecorder" {self.onset:.6f} {self.duration:.6f} '
                f'{self.start_position:.6f} {self.speed:.6f} '
                f'{self.volume:.2f} {self.pan:.3f} '
                f'{loop_flag} {loop_start_val:.6f} {loop_end_val:.6f} '
                f'{self.sample_table_num}\n')
    
    def __repr__(self):
        return (f"Testina(id={self.testina_id}, onset={self.onset}, "
                f"dur={self.duration}, speed={self.speed})")