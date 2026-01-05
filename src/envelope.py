class Envelope:
    """
    Envelope temporale definita da breakpoints.
    Supporta interpolazione lineare, cubica e step (costante a tratti).
    """
    def __init__(self, breakpoints):
        """
        Args:
            breakpoints: valore singolo, lista di [time, value], o dict con 'type'
            
        Examples:
            Envelope([[0,50]])                                    # costante
            Envelope([[0, 50], [2, 100], [5, 20]])         # lineare (default)
            Envelope({'type': 'cubic', 'points': [[0, 10], [2, 50], [5, 100]]})
            Envelope({'type': 'step', 'points': [[0, 3], [2, 5], [6, 2]]})
        """
        if isinstance(breakpoints, list):
            # Lista di breakpoints → default linear
            self.breakpoints = sorted(breakpoints, key=lambda x: x[0])
            self.type = 'linear'
        elif isinstance(breakpoints, dict):
            # Dict con type esplicito
            self.breakpoints = sorted(breakpoints['points'], key=lambda x: x[0])
            self.type = breakpoints.get('type', 'linear')
        else:
            raise ValueError(f"Formato envelope non valido: {breakpoints}")
        
        # Pre-calcola le tangenti per interpolazione cubica
        if self.type == 'cubic' and len(self.breakpoints) > 1:
            self._compute_tangents()
        
    def _compute_tangents(self):
        """
        Calcola le tangenti per interpolazione cubica Hermite.
        Usa l'algoritmo Fritsch-Carlson per garantire monotonia locale
        ed evitare overshoot/undershoot nei plateau.
        """
        n = len(self.breakpoints)
        self.tangents = []
        
        # Prima calcola le pendenze di ogni segmento
        deltas = []
        for i in range(n - 1):
            t0, v0 = self.breakpoints[i]
            t1, v1 = self.breakpoints[i + 1]
            deltas.append((v1 - v0) / (t1 - t0))
        
        for i in range(n):
            if i == 0:
                # Primo punto: tangente = pendenza del primo segmento
                m = deltas[0] if n > 1 else 0.0
            elif i == n - 1:
                # Ultimo punto: tangente = pendenza dell'ultimo segmento
                m = deltas[-1]
            else:
                # Punto interno: applica Fritsch-Carlson
                d0 = deltas[i - 1]  # pendenza segmento precedente
                d1 = deltas[i]      # pendenza segmento successivo
                
                # Se le pendenze hanno segni opposti o una è zero → tangente = 0
                # Questo garantisce che plateau e inversioni non abbiano overshoot
                if d0 * d1 <= 0:
                    m = 0.0
                else:
                    # Media armonica (più conservativa della media aritmetica)
                    m = 2.0 * d0 * d1 / (d0 + d1)
                    
                    # Clamp per garantire monotonia (Fritsch-Carlson)
                    # La tangente non deve eccedere 3x la pendenza minore
                    if m > 0:
                        m = min(m, 3.0 * min(d0, d1))
                    else:
                        m = max(m, 3.0 * max(d0, d1))
            
            self.tangents.append(m)

    def _cubic_hermite(self, t, t0, v0, m0, t1, v1, m1):
        """
        Interpolazione cubica Hermite tra due punti.
        
        Args:
            t: punto da valutare
            t0, v0, m0: tempo, valore e tangente del punto sinistro
            t1, v1, m1: tempo, valore e tangente del punto destro
        
        Returns:
            float: valore interpolato
        """
        # Normalizza t in [0, 1]
        s = (t - t0) / (t1 - t0)
        
        # Basis functions di Hermite
        h00 = 2*s*s*s - 3*s*s + 1
        h10 = s*s*s - 2*s*s + s
        h01 = -2*s*s*s + 3*s*s
        h11 = s*s*s - s*s
        
        # Interpolazione
        dt = t1 - t0
        return h00*v0 + h10*dt*m0 + h01*v1 + h11*dt*m1
    
    def evaluate(self, time):
        """
        Valuta l'envelope al tempo specificato.
        
        Args:
            time: tempo in secondi (relativo all'onset dello stream)
            
        Returns:
            float: valore interpolato/costante
        """
        if len(self.breakpoints) == 1:
            return self.breakpoints[0][1]
        # Se time è prima del primo breakpoint → hold primo valore
        if time <= self.breakpoints[0][0]:
            return self.breakpoints[0][1]
        
        # Se time è dopo l'ultimo breakpoint → hold ultimo valore
        if time >= self.breakpoints[-1][0]:
            return self.breakpoints[-1][1]
        
        # Trova i due breakpoints tra cui interpolare
        for i in range(len(self.breakpoints) - 1):
            t1, v1 = self.breakpoints[i]
            t2, v2 = self.breakpoints[i + 1]
            
            if t1 <= time < t2:
                if self.type == 'step':
                    # Step: tiene il valore SINISTRO (left-continuous)
                    return v1
                
                elif self.type == 'linear':
                    # Interpolazione lineare
                    t_norm = (time - t1) / (t2 - t1)
                    return v1 + (v2 - v1) * t_norm
                
                elif self.type == 'cubic':
                    # Interpolazione cubica Hermite
                    m1 = self.tangents[i]
                    m2 = self.tangents[i + 1]
                    return self._cubic_hermite(time, t1, v1, m1, t2, v2, m2)
        
        # Se arriviamo qui, siamo esattamente sull'ultimo breakpoint
        return self.breakpoints[-1][1]
    
    def _integrate_cubic_segment(self, t_start, t_end, t0, v0, m0, t1, v1, m1):
        """
        Integrale analitico di un segmento cubico Hermite.
        
        L'interpolazione cubica è: p(s) = h00(s)*v0 + h10(s)*dt*m0 + h01(s)*v1 + h11(s)*dt*m1
        dove s = (t-t0)/(t1-t0) e dt = t1-t0
        
        Integrando rispetto a t su [t_start, t_end]:
        ∫p(t)dt = dt * ∫p(s)ds (con cambio di variabile)
        """
        dt = t1 - t0
        s_start = (t_start - t0) / dt
        s_end = (t_end - t0) / dt
        
        # Integrale delle basis functions di Hermite su [s_start, s_end]:
        # ∫h00(s)ds = ∫(2s³ - 3s² + 1)ds = s⁴/2 - s³ + s
        # ∫h10(s)ds = ∫(s³ - 2s² + s)ds = s⁴/4 - 2s³/3 + s²/2
        # ∫h01(s)ds = ∫(-2s³ + 3s²)ds = -s⁴/2 + s³
        # ∫h11(s)ds = ∫(s³ - s²)ds = s⁴/4 - s³/3
        
        def H00_integral(s):
            return s*s*s*s/2 - s*s*s + s
        
        def H10_integral(s):
            return s*s*s*s/4 - 2*s*s*s/3 + s*s/2
        
        def H01_integral(s):
            return -s*s*s*s/2 + s*s*s
        
        def H11_integral(s):
            return s*s*s*s/4 - s*s*s/3
        
        # Calcola l'integrale definito
        I_h00 = H00_integral(s_end) - H00_integral(s_start)
        I_h10 = H10_integral(s_end) - H10_integral(s_start)
        I_h01 = H01_integral(s_end) - H01_integral(s_start)
        I_h11 = H11_integral(s_end) - H11_integral(s_start)
        
        # Moltiplica per dt (dal cambio di variabile) e combina
        area = dt * (I_h00*v0 + I_h10*dt*m0 + I_h01*v1 + I_h11*dt*m1)
        return area
    
    def integrate(self, from_time, to_time):
        """
        Calcola l'integrale dell'envelope tra from_time e to_time.
        Gestisce correttamente i casi edge e i diversi tipi di interpolazione.
        
        Args:
            from_time: tempo iniziale (secondi)
            to_time: tempo finale (secondi)
        
        Returns:
            float: integrale (area sotto la curva)
        """
        if from_time >= to_time:
            return 0.0
        
        # Caso costante: rettangolo semplice
        if len(self.breakpoints) == 1:
            value = self.breakpoints[0][1]
            return value * (to_time - from_time)
        
        total_area = 0.0
        t_first = self.breakpoints[0][0]
        t_last = self.breakpoints[-1][0]
        v_first = self.breakpoints[0][1]
        v_last = self.breakpoints[-1][1]
        
        # === ZONA 1: PRIMA del primo breakpoint (hold primo valore) ===
        if from_time < t_first:
            zone_end = min(to_time, t_first)
            total_area += v_first * (zone_end - from_time)
            from_time = t_first
            
            # Se abbiamo finito, ritorna
            if from_time >= to_time:
                return total_area
        
        # === ZONA 2: TRA i breakpoints (interpolazione) ===
        if from_time < t_last and to_time > t_first:
            for i in range(len(self.breakpoints) - 1):
                t1, v1 = self.breakpoints[i]
                t2, v2 = self.breakpoints[i + 1]
                
                # Skippa segmenti completamente fuori range
                if t2 <= from_time or t1 >= to_time:
                    continue
                
                # Clippa il segmento ai limiti di integrazione
                seg_start = max(t1, from_time)
                seg_end = min(t2, to_time)
                
                if seg_start >= seg_end:
                    continue
                
                # Calcola l'area in base al tipo di envelope
                if self.type == 'step':
                    # Step: rettangolo con altezza = v1
                    area = v1 * (seg_end - seg_start)
                
                elif self.type == 'linear':
                    # Lineare: trapezio
                    v_start = self.evaluate(seg_start)
                    v_end = self.evaluate(seg_end)
                    area = (v_start + v_end) / 2.0 * (seg_end - seg_start)
                
                elif self.type == 'cubic':
                    # Cubica: integrale analitico
                    m1 = self.tangents[i]
                    m2 = self.tangents[i + 1]
                    area = self._integrate_cubic_segment(seg_start, seg_end, t1, v1, m1, t2, v2, m2)
                
                total_area += area
        
        # === ZONA 3: DOPO l'ultimo breakpoint (hold ultimo valore) ===
        if to_time > t_last:
            zone_start = max(from_time, t_last)
            total_area += v_last * (to_time - zone_start)
        
        return total_area
    
    def __repr__(self):
        return f"Envelope(type={self.type}, points={self.breakpoints})"

