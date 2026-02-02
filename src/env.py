from typing import Union, List, Dict, Any

class Envelope:
    """
    Envelope temporale con supporto cicli multipli posizionali.
    
    Supporta interpolazione lineare, cubica e step.
    Supporta cicli multipli posizionali con marker 'cycle'.
    """
    
    def __init__(self, breakpoints):
        """
        Args:
            breakpoints: 
                - Lista di [time, value] con opzionali 'cycle'
                - Dict con 'type' e 'points' (con opzionali 'cycle')
            
        Examples:
            # Singolo ciclo
            Envelope([[0, 0], [0.05, 1], 'cycle'])
            
            # Due cicli
            Envelope([[0, 0], [0.05, 1], 'cycle', [0.3, 0], [0.39, 1], 'cycle'])
            
            # Mix ciclico + non ciclico
            Envelope([[0, 0], [0.05, 1], 'cycle', [0.5, 0.5], [1.0, 0]])
            
            # Con tipo esplicito
            Envelope({
                'type': 'cubic',
                'points': [[0, 0], [0.05, 1], 'cycle']
            })
        """
        # Parse type e raw_points
        if isinstance(breakpoints, dict):
            self.type = breakpoints.get('type', 'linear')
            raw_points = breakpoints['points']
        elif isinstance(breakpoints, list):
            self.type = 'linear'
            raw_points = breakpoints
        else:
            raise ValueError(f"Formato envelope non valido: {breakpoints}")
        
        # Valida tipo
        valid_types = ['linear', 'step', 'cubic']
        if self.type not in valid_types:
            raise ValueError(
                f"Tipo envelope non valido: '{self.type}'. "
                f"Validi: {valid_types}"
            )
        
        # Parse segmenti (normali e ciclici)
        self.segments = self._parse_segments(raw_points)
        
        # Valida
        if not self.segments:
            raise ValueError("Envelope deve contenere almeno un breakpoint.")
        
        # Pre-calcola tangenti per cubic
        if self.type == 'cubic':
            self._precompute_tangents()
    
    def _parse_segments(self, raw_points: list) -> List[Dict]:
        """
        Parsa lista mista di [time, value] e 'cycle'.
        
        Returns:
            List[dict]: Lista di segmenti con struttura:
                {
                    'start_time': float,
                    'breakpoints': [[t, v], ...],
                    'cycle': bool,
                    'cycle_duration': float or None
                }
        """
        segments = []
        current_points = []
        
        for item in raw_points:
            if isinstance(item, str):
                # Trovato marker 'cycle'
                if item.lower() != 'cycle':
                    raise ValueError(
                        f"Stringa non riconosciuta: '{item}'. "
                        "Usa 'cycle' (case-insensitive)."
                    )
                
                if len(current_points) < 2:
                    raise ValueError(
                        f"Ciclo richiede almeno 2 breakpoints. "
                        f"Trovati {len(current_points)}."
                    )
                
                # Crea segmento ciclico
                sorted_points = sorted(current_points, key=lambda x: x[0])
                t_start = sorted_points[0][0]
                t_end = sorted_points[-1][0]
                
                segments.append({
                    'start_time': t_start,
                    'breakpoints': sorted_points,
                    'cycle': True,
                    'cycle_duration': t_end - t_start
                })
                
                # Reset per prossimo segmento
                current_points = []
                
            elif isinstance(item, list) and len(item) == 2:
                # Breakpoint normale [time, value]
                current_points.append(item)
            else:
                raise ValueError(
                    f"Elemento non valido: {item}. "
                    "Atteso [time, value] o 'cycle'."
                )
        
        # Se ci sono punti rimanenti senza 'cycle' → segmento non ciclico
        if current_points:
            sorted_points = sorted(current_points, key=lambda x: x[0])
            t_start = sorted_points[0][0]
            
            segments.append({
                'start_time': t_start,
                'breakpoints': sorted_points,
                'cycle': False,
                'cycle_duration': None
            })
        
        return segments
    
    def _precompute_tangents(self):
        """
        Pre-calcola tangenti Fritsch-Carlson per ogni segmento cubic.
        """
        for segment in self.segments:
            points = segment['breakpoints']
            
            if len(points) < 2:
                segment['tangents'] = [0.0]
                continue
            
            # Calcola pendenze tra breakpoints
            n = len(points)
            deltas = []
            for i in range(n - 1):
                t0, v0 = points[i]
                t1, v1 = points[i + 1]
                deltas.append((v1 - v0) / (t1 - t0))
            
            # Calcola tangenti con algoritmo Fritsch-Carlson
            tangents = []
            for i in range(n):
                if i == 0:
                    m = deltas[0] if n > 1 else 0.0
                elif i == n - 1:
                    m = deltas[-1]
                else:
                    d0 = deltas[i - 1]
                    d1 = deltas[i]
                    
                    if d0 * d1 <= 0:
                        m = 0.0
                    else:
                        m = 2.0 * d0 * d1 / (d0 + d1)
                        if m > 0:
                            m = min(m, 3.0 * min(d0, d1))
                        else:
                            m = max(m, 3.0 * max(d0, d1))
                
                tangents.append(m)
            
            segment['tangents'] = tangents
    
    def evaluate(self, time: float) -> float:
        """
        Valuta envelope al tempo specificato.
        
        Per segmenti ciclici:
        - Il ciclo si ripete fino all'inizio del prossimo segmento
        - Nessuna interpolazione al wrap-around (discontinuità accettata)
        
        Args:
            time: tempo in secondi
            
        Returns:
            float: valore interpolato
        """
        if not self.segments:
            raise ValueError("Envelope vuoto")
        
        # Trova segmento attivo al tempo t
        active_segment = self._find_active_segment(time)
        
        if active_segment['cycle']:
            return self._evaluate_cyclic_segment(time, active_segment)
        else:
            return self._evaluate_normal_segment(time, active_segment)
    
    def _find_active_segment(self, time: float) -> Dict:
        """
        Trova quale segmento è attivo al tempo t.
        
        Logica: L'ultimo segmento con start_time <= time è attivo.
        """
        # Prima del primo segmento: usa primo segmento
        if time < self.segments[0]['start_time']:
            return self.segments[0]
        
        # Trova ultimo segmento che inizia prima/a time
        active = self.segments[0]
        for seg in self.segments:
            if seg['start_time'] <= time:
                active = seg
            else:
                break
        
        return active

    def _evaluate_cyclic_segment(
        self, 
        time: float, 
        segment: Dict
    ) -> float:
        """
        Valuta segmento ciclico con modulo.
        
        Il ciclo si ripete indefinitamente. L'ultimo breakpoint
        del ciclo è raggiungibile, il wrap-around avviene dopo.
        """
        points = segment['breakpoints']
        t_start = segment['start_time']
        cycle_dur = segment['cycle_duration']
        
        # Prima dell'inizio del segmento: hold primo valore
        if time < t_start:
            return points[0][1]
        
        # Calcola posizione nel ciclo
        elapsed = time - t_start
        
        # Calcola quanti cicli sono passati
        cycles_exact = elapsed / cycle_dur
        cycles_int = round(cycles_exact)  # Arrotonda al più vicino
        
        # Controlla se siamo molto vicini a un multiplo intero
        if abs(cycles_exact - cycles_int) < 1e-9:
            # Siamo su/vicino a un multiplo del ciclo
            if cycles_int == 0:
                # Inizio del primo ciclo
                t_actual = t_start
            else:
                # Fine di un ciclo (uno o più cicli completi)
                # Restituisci direttamente l'ultimo valore
                return points[-1][1]
        else:
            # Caso normale: usa modulo
            t_in_cycle = elapsed % cycle_dur
            t_actual = t_start + t_in_cycle
        
        # Usa interpolazione sui breakpoints del segmento
        return self._interpolate_points(t_actual, points, segment)

    def _interpolate_points(
        self, 
        time: float, 
        points: List, 
        segment: Dict
    ) -> float:
        """
        Interpolazione (linear/step/cubic) su lista di breakpoints.
        """
        # Singolo punto: costante
        if len(points) == 1:
            return points[0][1]
        
        # CASO SPECIALE PER STEP: Se cade esattamente su un breakpoint,
        # restituisci il valore di quel breakpoint
        if self.type == 'step':
            for i in range(len(points)):
                if abs(time - points[i][0]) < 1e-10:
                    return points[i][1]
        
        # Trova segmento [t1, t2] contenente time
        for i in range(len(points) - 1):
            t1, v1 = points[i]
            t2, v2 = points[i + 1]
            
            # Per l'ultimo segmento, usa <= su entrambi i lati
            is_last_segment = (i == len(points) - 2)
            
            if is_last_segment:
                in_segment = (t1 <= time <= t2)
            else:
                in_segment = (t1 <= time < t2)
            
            if in_segment:
                if self.type == 'step':
                    # Step: tiene valore sinistro
                    return v1
                
                elif self.type == 'linear':
                    # Interpolazione lineare
                    if abs(t2 - t1) < 1e-10:
                        return v2
                    t_norm = (time - t1) / (t2 - t1)
                    return v1 + (v2 - v1) * t_norm
                
                elif self.type == 'cubic':
                    # Interpolazione cubica Hermite
                    m1 = segment['tangents'][i]
                    m2 = segment['tangents'][i + 1]
                    return self._cubic_hermite(time, t1, v1, m1, t2, v2, m2)
        
        # Fallback: ultimo breakpoint
        return points[-1][1]            

    def _evaluate_normal_segment(
        self, 
        time: float, 
        segment: Dict
    ) -> float:
        """
        Valuta segmento non ciclico (comportamento standard).
        """
        points = segment['breakpoints']
        t_start = points[0][0]
        t_end = points[-1][0]
        
        # Prima dell'inizio: hold primo valore
        if time < t_start:
            return points[0][1]
        
        # Dopo la fine: hold ultimo valore
        if time > t_end:
            return points[-1][1]
        
        # Dentro il segmento: interpola
        return self._interpolate_points(time, points, segment)
    
    def _cubic_hermite(
        self, 
        t: float, 
        t0: float, v0: float, m0: float,
        t1: float, v1: float, m1: float
    ) -> float:
        """
        Interpolazione cubica Hermite tra due punti.
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
    
    def integrate(self, from_time: float, to_time: float) -> float:
        """
        Integrale dell'envelope tra from_time e to_time.
        
        NOTA: Attualmente non supportato per envelope con cicli.
        Solleva NotImplementedError se ci sono segmenti ciclici.
        """
        # Check se ci sono cicli
        has_cycles = any(seg['cycle'] for seg in self.segments)
        
        if has_cycles:
            raise NotImplementedError(
                "integrate() non è ancora supportato per envelope con cicli. "
                "Implementazione futura."
            )
        
        # Se non ci sono cicli, usa logica normale
        # (qui andrebbe il codice di integrate esistente)
        # Per ora placeholder
        raise NotImplementedError(
            "integrate() per envelope non ciclici da implementare"
        )
    
    def __repr__(self):
        return (
            f"Envelope(type={self.type}, "
            f"segments={len(self.segments)})"
        )