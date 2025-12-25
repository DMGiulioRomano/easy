class Envelope:
    """
    Envelope temporale definita da breakpoints
    Interpola linearmente o esponenzialmente tra i punti
    """
    def __init__(self, breakpoints):
        """
        Args:
            breakpoints: lista di [time, value] o dict con 'type'
            
        Examples:
            Envelope(50)                              # costante
            Envelope([[0, 50], [2, 100], [5, 20]])   # lineare
            Envelope({'type': 'exponential', 'points': [[0, 10], [5, 100]]})
        """
        if isinstance(breakpoints, (int, float)):
            # Valore costante
            self.breakpoints = [[0, breakpoints]]
            self.type = 'constant'
        elif isinstance(breakpoints, list):
            # Lista di breakpoints
            self.breakpoints = sorted(breakpoints, key=lambda x: x[0])
            self.type = 'linear'
        elif isinstance(breakpoints, dict):
            # Dict con type
            self.breakpoints = sorted(breakpoints['points'], key=lambda x: x[0])
            self.type = breakpoints.get('type', 'linear')
        else:
            raise ValueError(f"Formato envelope non valido: {breakpoints}")
    
    def evaluate(self, time):
        """
        Valuta l'envelope al tempo specificato
        
        Args:
            time: tempo in secondi (relativo all'onset dello stream)
            
        Returns:
            float: valore interpolato
        """
        if self.type == 'constant' or len(self.breakpoints) == 1:
            return self.breakpoints[0][1]
        
        # Se time è prima del primo breakpoint
        if time <= self.breakpoints[0][0]:
            return self.breakpoints[0][1]
        
        # Se time è dopo l'ultimo breakpoint
        if time >= self.breakpoints[-1][0]:
            return self.breakpoints[-1][1]
        
        # Trova i due breakpoints tra cui interpolare
        for i in range(len(self.breakpoints) - 1):
            t1, v1 = self.breakpoints[i]
            t2, v2 = self.breakpoints[i + 1]
            
            if t1 <= time <= t2:
                # Interpolazione lineare
                t_norm = (time - t1) / (t2 - t1)
                
                if self.type == 'linear':
                    return v1 + (v2 - v1) * t_norm
                elif self.type == 'exponential':
                    # Interpolazione esponenziale
                    if v1 <= 0 or v2 <= 0:
                        return v1 + (v2 - v1) * t_norm  # fallback a lineare
                    return v1 * pow(v2 / v1, t_norm)
                else:
                    return v1 + (v2 - v1) * t_norm
        
        return self.breakpoints[-1][1]


