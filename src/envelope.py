# envelope.py
"""
Envelope system with Composite Pattern.

Refactored from God Class to use:
- InterpolationStrategyFactory for creating strategies
- List[Segment] instead of List[Dict]
- Delegation to Segment classes for evaluate/integrate

Maintains 100% backward compatibility with legacy formats:
- [[0, 0], [0.1, 1], 'cycle']
- {'type': 'cubic', 'points': [...]}
"""

from typing import Union, List, Dict, Any
from envelope_factory import InterpolationStrategyFactory
from envelope_segment import NormalSegment, CyclicSegment, Segment
from envelope_interpolation import InterpolationStrategy


class Envelope:
    """
    Envelope temporale con supporto cicli multipli posizionali.
    
    Supporta interpolazione lineare, cubica e step.
    Supporta cicli multipli posizionali con marker 'cycle'.
    
    Refactored to use Composite Pattern:
    - InterpolationStrategyFactory creates strategies
    - List[Segment] for clean delegation
    - No more if/elif scattered through code
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
        
        # Crea strategy usando Factory
        self.strategy = InterpolationStrategyFactory.create(self.type)
        
        # Parse segmenti (normali e ciclici) → List[Segment]
        self.segments = self._parse_segments(raw_points)
        
        # Valida
        if not self.segments:
            raise ValueError("Envelope deve contenere almeno un breakpoint.")
    
    def _parse_segments(self, raw_points: list) -> List[Segment]:
        """
        Parsa lista mista di [time, value] e 'cycle' in List[Segment].
        
        Returns:
            List[Segment]: Lista di NormalSegment o CyclicSegment
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
                
                # Valida punti prima del cycle
                if len(current_points) < 2:
                    raise ValueError(
                        "Ciclo deve avere almeno 2 breakpoints prima di 'cycle'."
                    )
                
                # Crea context per cubic (tangenti)
                context = self._create_context_for_segment(current_points)
                
                # Crea CyclicSegment
                segment = CyclicSegment(
                    breakpoints=current_points,
                    strategy=self.strategy,
                    context=context
                )
                segments.append(segment)
                
                # Reset per prossimo segmento
                current_points = []
                
            elif isinstance(item, list):
                # Breakpoint [time, value]
                if len(item) != 2:
                    raise ValueError(
                        f"Formato breakpoint non valido: {item}. "
                        "Deve essere [time, value]."
                    )
                current_points.append(item)
            else:
                raise ValueError(
                    f"Elemento non valido: {item}. "
                    "Deve essere [time, value] o 'cycle'."
                )
        
        # Punti rimanenti → NormalSegment
        if current_points:
            if len(current_points) < 1:
                raise ValueError("Segmento normale deve avere almeno 1 breakpoint.")
            
            context = self._create_context_for_segment(current_points)
            segment = NormalSegment(
                breakpoints=current_points,
                strategy=self.strategy,
                context=context
            )
            segments.append(segment)
        
        return segments
    
    def _create_context_for_segment(self, points: List[List[float]]) -> Dict[str, Any]:
        """
        Crea context dict per il segmento (es. tangenti per cubic).
        
        Args:
            points: Breakpoints del segmento
            
        Returns:
            Dict con context (es. {'tangents': [...]})
        """
        context = {}
        
        # Per cubic, calcola tangenti con Fritsch-Carlson
        if self.type == 'cubic':
            tangents = self._compute_fritsch_carlson_tangents(points)
            context['tangents'] = tangents
        
        return context
    
    def _compute_fritsch_carlson_tangents(self, points: List[List[float]]) -> List[float]:
        """
        Calcola tangenti usando algoritmo Fritsch-Carlson.
        
        Previene overshooting mantenendo monotonia.
        """
        n = len(points)
        if n < 2:
            return [0.0] * n
        
        tangents = [0.0] * n
        
        # Pendenze dei segmenti
        deltas = []
        for i in range(n - 1):
            t0, v0 = points[i]
            t1, v1 = points[i + 1]
            if t1 > t0:
                delta = (v1 - v0) / (t1 - t0)
            else:
                delta = 0.0
            deltas.append(delta)
        
        # Tangente iniziale
        tangents[0] = deltas[0]
        
        # Tangenti interne: media pesata con monotonia
        for i in range(1, n - 1):
            d_left = deltas[i - 1]
            d_right = deltas[i]
            
            # Se segni diversi → tangente zero (punto critico)
            if d_left * d_right <= 0:
                tangents[i] = 0.0
            else:
                # Media armonica ponderata (Fritsch-Carlson)
                tangents[i] = 2.0 / (1.0 / d_left + 1.0 / d_right)
        
        # Tangente finale
        tangents[n - 1] = deltas[n - 2]
        
        return tangents
    
    def evaluate(self, t: float) -> float:
        """
        Valuta l'envelope al tempo t.
        
        Delegation Pattern: trova il segmento appropriato e delega.
        
        Args:
            t: Tempo in secondi
            
        Returns:
            float: Valore dell'envelope
        """
        # Trova il segmento che contiene t
        for segment in self.segments:
            # CyclicSegment gestisce wrapping, NormalSegment gestisce hold
            # Controlliamo se il segmento "si occupa" di questo tempo
            if segment.is_cyclic:
                # Segmento ciclico: si occupa di t >= start_time
                if t >= segment.start_time:
                    # Controlla se c'è un segmento successivo che "ruba" il tempo
                    next_seg = self._get_next_segment(segment)
                    if next_seg is None or t < next_seg.start_time:
                        return segment.evaluate(t)
            else:
                # Segmento normale: delega sempre (gestisce hold interno)
                # Ma solo se t è "nel suo dominio" o se è l'ultimo
                next_seg = self._get_next_segment(segment)
                if next_seg is None or t < next_seg.start_time:
                    return segment.evaluate(t)
        
        # Fallback: ultimo segmento (hold finale)
        return self.segments[-1].evaluate(t)
    
    def _get_next_segment(self, current_segment: Segment) -> Union[Segment, None]:
        """Ritorna il segmento successivo o None se è l'ultimo."""
        try:
            idx = self.segments.index(current_segment)
            if idx < len(self.segments) - 1:
                return self.segments[idx + 1]
        except ValueError:
            pass
        return None
    
    def integrate(self, from_time: float, to_time: float) -> float:
        """
        Integrale dell'envelope tra from_time e to_time.
        
        Orchestra l'integrazione attraverso i segmenti.
        
        Args:
            from_time: Tempo iniziale
            to_time: Tempo finale
            
        Returns:
            float: Area sotto la curva
        """
        if from_time > to_time:
            return -self.integrate(to_time, from_time)
        
        if from_time == to_time:
            return 0.0
        
        total_integral = 0.0
        current_time = from_time
        
        for idx, segment in enumerate(self.segments):
            if current_time >= to_time:
                break
            
            # Determina dove finisce questo segmento (o dove inizia il prossimo)
            if idx < len(self.segments) - 1:
                segment_end = self.segments[idx + 1].start_time
            else:
                segment_end = float('inf')
            
            # Limita all'intervallo richiesto
            integrate_to = min(to_time, segment_end)
            
            # Delega al segmento
            if current_time < integrate_to:
                integral_part = segment.integrate(current_time, integrate_to)
                total_integral += integral_part
                current_time = integrate_to
        
        return total_integral
    
    @staticmethod
    def is_envelope_like(obj: Any) -> bool:
        """
        Type checker centralizzato: rileva se un oggetto rappresenta envelope-like data.
        
        Supporta:
        - Envelope instances
        - Liste di breakpoints [[t, v], ...]
        - Dict con 'type' e 'points'
        
        Returns:
            bool: True se l'oggetto è envelope-like
        """
        # Istanza Envelope
        if isinstance(obj, Envelope):
            return True
        
        # Lista di breakpoints
        if isinstance(obj, list):
            # Lista vuota: NO
            if not obj:
                return False
            # Lista con almeno un [t, v] o 'cycle'
            for item in obj:
                if isinstance(item, list) and len(item) == 2:
                    return True
                if isinstance(item, str) and item.lower() == 'cycle':
                    return True
            return False
        
        # Dict con 'points'
        if isinstance(obj, dict):
            return 'points' in obj
        
        return False