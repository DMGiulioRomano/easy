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
        
        Supporta segmenti ciclici e non ciclici.
        Per segmenti ciclici: calcola l'integrale considerando le ripetizioni.
        """
        if from_time > to_time:
            return -self.integrate(to_time, from_time)
        
        if from_time == to_time:
            return 0.0
        
        total_integral = 0.0
        current_time = from_time
        
        for segment in self.segments:
            t_start = segment['start_time']
            points = segment['breakpoints']
            
            if segment['cycle']:
                # Segmento ciclico
                cycle_dur = segment['cycle_duration']
                
                # Determina dove inizia e finisce l'integrazione rispetto al ciclo
                # Se siamo prima dell'inizio del ciclo, skippa
                if to_time <= t_start:
                    continue
                
                if current_time < t_start:
                    current_time = t_start
                
                # Calcola quanto tempo copre questo segmento
                time_in_segment = min(to_time, float('inf')) - current_time
                
                # Per cicli, integra fino a to_time
                if current_time < to_time:
                    integral = self._integrate_cyclic_segment(
                        segment, current_time, to_time
                    )
                    total_integral += integral
                    current_time = to_time
            else:
                # Segmento non ciclico
                t_end = points[-1][0]
                
                # Skippa se siamo completamente fuori dal segmento
                if to_time <= t_start or current_time >= t_end:
                    continue
                
                # Limita l'intervallo al segmento
                seg_start = max(current_time, t_start)
                seg_end = min(to_time, t_end)
                
                if seg_start < seg_end:
                    integral = self._integrate_normal_segment(
                        segment, seg_start, seg_end
                    )
                    total_integral += integral
                    current_time = seg_end
        
        return total_integral

    def _integrate_cyclic_segment(
        self, 
        segment: Dict, 
        from_time: float, 
        to_time: float
    ) -> float:
        """
        Integra un segmento ciclico tra from_time e to_time.
        
        Strategia:
        1. Calcola l'integrale di un ciclo completo
        2. Determina quanti cicli completi ci sono nell'intervallo
        3. Integra le porzioni parziali all'inizio e alla fine
        """
        t_start = segment['start_time']
        cycle_dur = segment['cycle_duration']
        points = segment['breakpoints']
        
        # Tempi relativi all'inizio del segmento ciclico
        rel_from = from_time - t_start
        rel_to = to_time - t_start
        
        # Se siamo prima del ciclo, inizia dal ciclo
        if rel_from < 0:
            rel_from = 0
        
        # Calcola l'integrale di un ciclo completo (da t_start a t_start + cycle_dur)
        cycle_integral = self._integrate_points(points, t_start, t_start + cycle_dur)
        
        # Determina la fase iniziale e finale nel ciclo
        phase_from = rel_from % cycle_dur
        phase_to = rel_to % cycle_dur
        
        # Quanti cicli completi attraversiamo?
        cycles_from = rel_from // cycle_dur
        cycles_to = rel_to // cycle_dur
        full_cycles = int(cycles_to - cycles_from)
        
        total = 0.0
        
        # Caso 1: Tutto nell'intervallo è dentro lo stesso ciclo
        if full_cycles == 0:
            # Integra solo da phase_from a phase_to nello stesso ciclo
            t_abs_from = t_start + phase_from
            t_abs_to = t_start + phase_to
            total = self._integrate_points(points, t_abs_from, t_abs_to)
        
        # Caso 2: Attraversiamo uno o più cicli completi
        else:
            # Integrale dalla fase iniziale fino alla fine del primo ciclo
            if phase_from > 0:
                t_abs_from = t_start + phase_from
                t_abs_to = t_start + cycle_dur
                total += self._integrate_points(points, t_abs_from, t_abs_to)
                full_cycles -= 1
            
            # Aggiungi i cicli completi intermedi
            total += full_cycles * cycle_integral
            
            # Integrale dall'inizio dell'ultimo ciclo fino alla fase finale
            if phase_to > 0:
                t_abs_from = t_start
                t_abs_to = t_start + phase_to
                total += self._integrate_points(points, t_abs_from, t_abs_to)
        
        return total

    def _integrate_normal_segment(
        self, 
        segment: Dict, 
        from_time: float, 
        to_time: float
    ) -> float:
        """Integra un segmento normale (non ciclico)."""
        points = segment['breakpoints']
        return self._integrate_points(points, from_time, to_time)

    def _integrate_points(
        self, 
        points: List, 
        from_time: float, 
        to_time: float
    ) -> float:
        """
        Integra tra breakpoints usando il tipo di interpolazione corrente.
        
        Args:
            points: Lista di breakpoints [[t,v], ...]
            from_time: Tempo iniziale
            to_time: Tempo finale
        """
        if from_time >= to_time:
            return 0.0
        
        total = 0.0
        
        # Trova i segmenti rilevanti
        for i in range(len(points) - 1):
            t0, v0 = points[i]
            t1, v1 = points[i + 1]
            
            # Skippa segmenti completamente fuori range
            if to_time <= t0 or from_time >= t1:
                continue
            
            # Limita l'intervallo di integrazione al segmento corrente
            seg_start = max(from_time, t0)
            seg_end = min(to_time, t1)
            
            if seg_start >= seg_end:
                continue
            
            # Integra secondo il tipo
            if self.type == 'step':
                # Step: valore costante v0 nell'intervallo
                total += v0 * (seg_end - seg_start)
            
            elif self.type == 'linear':
                # Linear: integrale del trapezio
                # Valuta l'envelope agli estremi
                v_start = self._interpolate_linear(seg_start, t0, v0, t1, v1)
                v_end = self._interpolate_linear(seg_end, t0, v0, t1, v1)
                # Area del trapezio
                total += 0.5 * (v_start + v_end) * (seg_end - seg_start)
            
            elif self.type == 'cubic':
                # Cubic: integrazione numerica (Simpson o trapezi)
                total += self._integrate_cubic_segment(
                    seg_start, seg_end, t0, v0, t1, v1, i
                )
        
        return total

    def _interpolate_linear(
        self, 
        t: float, 
        t0: float, 
        v0: float, 
        t1: float, 
        v1: float
    ) -> float:
        """Interpolazione lineare semplice."""
        if t1 == t0:
            return v0
        s = (t - t0) / (t1 - t0)
        return v0 + s * (v1 - v0)

    def _integrate_cubic_segment(
        self,
        from_t: float,
        to_t: float,
        t0: float,
        v0: float,
        t1: float,
        v1: float,
        segment_idx: int
    ) -> float:
        """
        Integra un segmento cubic usando la regola di Simpson.
        
        Per Hermite cubic, l'integrale analitico è complesso,
        quindi usiamo integrazione numerica.
        """
        # Ottieni le tangenti per questo segmento
        m0 = self._tangents[segment_idx]
        m1 = self._tangents[segment_idx + 1]
        
        # Regola di Simpson: divide in sotto-intervalli
        n_steps = 10  # Numero di sotto-intervalli
        dt = (to_t - from_t) / n_steps
        
        total = 0.0
        for i in range(n_steps):
            t_a = from_t + i * dt
            t_b = from_t + (i + 1) * dt
            t_mid = (t_a + t_b) / 2
            
            # Valuta l'envelope nei tre punti
            v_a = self._interpolate_cubic_hermite(t_a, t0, v0, t1, v1, m0, m1)
            v_mid = self._interpolate_cubic_hermite(t_mid, t0, v0, t1, v1, m0, m1)
            v_b = self._interpolate_cubic_hermite(t_b, t0, v0, t1, v1, m0, m1)
            
            # Formula di Simpson: (b-a)/6 * (f(a) + 4*f(mid) + f(b))
            total += (dt / 6) * (v_a + 4 * v_mid + v_b)
        
        return total    

    @staticmethod
    def is_envelope_like(obj: Any) -> bool:
        """
        Type checker centralizzato: rileva se un oggetto rappresenta envelope-like data.
        
        Riconosce:
        - Liste di breakpoints: [[t,v], ...] con possibili marker 'cycle'
        - Dict con chiave 'points'
        - Oggetti Envelope
        
        Design Pattern: Type Checker
        Centralizza la logica che era sparsa in gate_factory, parser, ecc.
        """
        # Già un Envelope
        if isinstance(obj, Envelope):
            return True
        
        # Dict con struttura envelope
        if isinstance(obj, dict) and 'points' in obj:
            return True
        
        # Lista di breakpoints (con possibili 'cycle')
        if isinstance(obj, list) and len(obj) > 0:
            # Tutti gli item devono essere o liste [t,v] o marker 'cycle'
            for item in obj:
                if isinstance(item, str):
                    # Marker 'cycle' è valido
                    if item.lower() != 'cycle':
                        return False
                elif isinstance(item, list):
                    # Breakpoint deve avere almeno 2 elementi
                    if len(item) < 2:
                        return False
                else:
                    # Tipo non riconosciuto
                    return False
            return True
        
        return False
    
    @staticmethod
    def extract_points(raw_data: Union[List, dict]) -> List:
        """
        Estrae lista pulita di breakpoints da raw_data, ignorando marker 'cycle'.
        
        Utile per operazioni che devono processare solo i punti numerici
        senza considerare i marker strutturali.
        
        Args:
            raw_data: lista mista o dict con 'points'
            
        Returns:
            Lista di soli breakpoints [[t,v], ...] senza marker
        """
        if isinstance(raw_data, dict):
            points_data = raw_data.get('points', [])
        elif isinstance(raw_data, list):
            points_data = raw_data
        else:
            raise ValueError(f"Formato non valido: {type(raw_data)}")
        
        # Filtra solo i breakpoints numerici
        return [item for item in points_data 
                if isinstance(item, list) and len(item) >= 2]
    
    @staticmethod
    def scale_envelope_values(
        raw_data: Union[List, dict], 
        scale: float
    ) -> Union[List, dict]:
        """
        Scala i VALORI (Y) di un envelope-like object mantenendo struttura.
        NON scala i tempi (X).
        
        Design Pattern: Strategy per scaling
        Gestisce correttamente marker 'cycle' e strutture dict.
        
        Args:
            raw_data: lista o dict con punti
            scale: fattore di scala per i valori Y
            
        Returns:
            Stessa struttura di input con valori scalati
        """
        if isinstance(raw_data, dict):
            # Dict: processa ricorsivamente 'points'
            scaled_dict = dict(raw_data)
            if 'points' in scaled_dict:
                scaled_dict['points'] = Envelope.scale_envelope_values(
                    scaled_dict['points'], 
                    scale
                )
            return scaled_dict
        
        elif isinstance(raw_data, list):
            # Lista: scala solo i breakpoints, preserva marker
            scaled_list = []
            for item in raw_data:
                if isinstance(item, str):
                    # Marker 'cycle' passa inalterato
                    scaled_list.append(item)
                elif isinstance(item, list) and len(item) >= 2:
                    # Breakpoint [t, y]: scala solo y
                    t, y = item[0], item[1]
                    scaled_list.append([t, y * scale])
                else:
                    # Safety: passa invariato
                    scaled_list.append(item)
            return scaled_list
        
        else:
            raise ValueError(f"Tipo non supportato: {type(raw_data)}")
    
    @classmethod
    def from_raw_with_scaling(
        cls,
        raw_data: Union[List, dict],
        time_scale: float = 1.0,
        value_scale: float = 1.0
    ) -> 'Envelope':
        """
        Factory method: crea Envelope da raw data con scaling opzionale.
        
        Combina funzionalità di create_scaled_envelope + scale_values.
        
        Args:
            raw_data: lista [[t,v],...,'cycle'] o dict
            time_scale: fattore scala per tempi (per normalized mode)
            value_scale: fattore scala per valori (per loop_unit scaling)
            
        Returns:
            Envelope con scaling applicato
        """
        # 1. Scala valori se richiesto
        if value_scale != 1.0:
            raw_data = cls.scale_envelope_values(raw_data, value_scale)
        
        # 2. Usa create_scaled_envelope per gestire time scaling
        return create_scaled_envelope(raw_data, time_scale, 'normalized' if time_scale != 1.0 else 'absolute')

    @staticmethod
    def _scale_time_values(raw_points: List, time_scale: float) -> List:
        """
        Scala solo i TEMPI (X) dei breakpoints, preservando marker 'cycle'.
        
        Args:
            raw_points: lista mista di [t, v] e 'cycle'
            time_scale: fattore di scala per i tempi
            
        Returns:
            Lista con tempi scalati e marker preservati
        """
        scaled = []
        for item in raw_points:
            if isinstance(item, str):
                # Marker 'cycle' passa inalterato
                scaled.append(item)
            elif isinstance(item, list) and len(item) >= 2:
                # Breakpoint: scala solo il tempo (X)
                t, v = item[0], item[1]
                scaled.append([t * time_scale, v])
            else:
                # Safety fallback
                scaled.append(item)
        return scaled


    @property
    def breakpoints(self) -> List[List[float]]:
        """
        Restituisce lista flat di tutti i breakpoints (senza marker 'cycle').
        
        Aggrega i breakpoints da tutti i segments per backward compatibility
        con codice che accede direttamente a .breakpoints
        
        Returns:
            Lista di [time, value] ordinati per tempo
        """
        all_points = []
        for segment in self.segments:
            all_points.extend(segment['breakpoints'])
        
        # Ordina per tempo e rimuovi duplicati
        # (due segments potrebbero condividere punti ai bordi)
        seen = set()
        unique_points = []
        for t, v in sorted(all_points, key=lambda p: p[0]):
            if t not in seen:
                seen.add(t)
                unique_points.append([t, v])
        
        return unique_points

    def __repr__(self):
        return (
            f"Envelope(type={self.type}, "
            f"segments={len(self.segments)})"
        )


# envelope.py - FIX create_scaled_envelope()

def create_scaled_envelope(
    raw_data: Union[List, dict],
    duration: float = 1.0,
    time_mode: str = 'absolute'
) -> Envelope:
    """Factory function per creare Envelope con gestione scaling temporale."""
    
    # A) Parse struttura
    if isinstance(raw_data, dict):
        points = raw_data.get('points', [])
        env_type = raw_data.get('type', 'linear')
        local_time_unit = raw_data.get('time_unit')
    else:
        points = raw_data
        env_type = 'linear'
        local_time_unit = None
    
    # B) Determina modalità effettiva
    effective_mode = local_time_unit if local_time_unit else time_mode
    
    # C) Scala tempi se necessario
    if effective_mode == 'normalized':
        # USA IL METODO STATICO per gestire correttamente 'cycle'
        scaled_points = Envelope._scale_time_values(points, duration)
    else:
        scaled_points = points
    
    # D) Crea Envelope
    if isinstance(raw_data, dict):
        return Envelope({'type': env_type, 'points': scaled_points})
    else:
        return Envelope(scaled_points)


