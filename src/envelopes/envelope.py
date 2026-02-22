# envelope.py - versione semplificata
"""
Envelope system with Composite Pattern.

Supports:
- Standard breakpoints: [[t, v], ...]
- Compact format: [[[x%, y], ...], total_time, n_reps, interp?]
- Dict format: {'type': 'cubic', 'points': [...]}
"""

from typing import Union, List, Dict, Any
from envelopes.envelope_factory import InterpolationStrategyFactory
from envelopes.envelope_segment import NormalSegment, Segment
from envelopes.envelope_interpolation import InterpolationStrategy

class Envelope:
    """
    Envelope temporale con supporto formato compatto.
    
    Supporta interpolazione lineare, cubica e step.
    Supporta nuovo formato compatto per cicli ripetuti.
    """
    
    def __init__(self, breakpoints):
        """
        Args:
            breakpoints: 
                - Lista di [time, value]
                - Nuovo formato compatto: [[[x%, y], ...], total_time, n_reps, interp?]
                - Dict con 'type' e 'points'
            
        Examples:
            # Standard breakpoints
            Envelope([[0, 0], [0.5, 1], [1.0, 0]])
            
            # Nuovo formato compatto: 4 ripetizioni in 0.4s
            Envelope([[[0, 0], [100, 1]], 0.4, 4])
            
            # Formato misto
            Envelope([
                [[[0, 0], [100, 1]], 0.4, 4],  # Compatto
                [0.5, 0.5],                     # Standard
                [1.0, 0]                        # Standard
            ])
            
            # Con tipo esplicito nel dict
            Envelope({
                'type': 'cubic',
                'points': [[[0, 0], [50, 0.5], [100, 1]], 0.2, 2]
            })
        """
        # Import qui per evitare circular import
        from envelopes.envelope_builder import EnvelopeBuilder
        
        # Parse type e raw_points
        if isinstance(breakpoints, dict):
            self.type = breakpoints.get('type', 'linear')
            raw_points = breakpoints['points']
        elif isinstance(breakpoints, list):
            # Controlla se c'è tipo in formato compatto
            extracted_type = EnvelopeBuilder.extract_interp_type(breakpoints)
            self.type = extracted_type or 'linear'
            raw_points = breakpoints
        else:
            raise ValueError(f"Formato envelope non valido: {breakpoints}")
        
        # ESPANDI formato compatto usando Builder
        expanded_points = EnvelopeBuilder.parse(raw_points)
        
        # Crea strategy usando Factory
        self.strategy = InterpolationStrategyFactory.create(self.type)
        
        # Parse segmenti → List[NormalSegment]
        self.segments = self._parse_segments(expanded_points)
        
        # Valida
        if not self.segments:
            raise ValueError("Envelope deve contenere almeno un breakpoint.")
    
    def _parse_segments(self, breakpoints: list) -> List[Segment]:
        """
        Parsa lista di breakpoints in List[NormalSegment].
        
        Nota: Formato compatto già espanso da Builder.
        
        Returns:
            List[NormalSegment]: Lista con singolo segmento contenente tutti i breakpoints
        """
        if not breakpoints:
            raise ValueError("Lista breakpoints vuota.")
        
        # Valida formato breakpoints
        for item in breakpoints:
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError(
                    f"Formato breakpoint non valido: {item}. "
                    "Deve essere [time, value]."
                )
        
        # Crea context per cubic (tangenti)
        context = self._create_context_for_segment(breakpoints)
        
        # Crea singolo NormalSegment con tutti i breakpoints
        segment = NormalSegment(
            breakpoints=breakpoints,
            strategy=self.strategy,
            context=context
        )
        
        return [segment]
    
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
        
        Delegation Pattern: delega al singolo NormalSegment.
        
        Args:
            t: Tempo in secondi
            
        Returns:
            float: Valore dell'envelope
        """
        # Singolo segmento: delega direttamente
        return self.segments[0].evaluate(t)
    
    def integrate(self, from_time: float, to_time: float) -> float:
        """
        Integrale dell'envelope tra from_time e to_time.
        
        Delega al singolo NormalSegment.
        
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
        
        # Singolo segmento: delega direttamente
        return self.segments[0].integrate(from_time, to_time)
        
    @property
    def breakpoints(self) -> List[List[float]]:
        """
        Property per accesso ai breakpoints (backward compatibility).
        
        Dopo il refactoring, i breakpoints sono contenuti nei segments.
        Questa property fornisce accesso diretto per codice legacy.
        
        Returns:
            List[List[float]]: Lista di breakpoints [[t, v], ...]
        """
        # Tipicamente c'è un solo segment con tutti i breakpoints
        if len(self.segments) == 1:
            return self.segments[0].breakpoints
        
        # Nel caso di multi-segmento (futuro), concatena
        all_breakpoints = []
        for seg in self.segments:
            all_breakpoints.extend(seg.breakpoints)
        return all_breakpoints



    @staticmethod
    def is_envelope_like(obj: Any) -> bool:
        """
        Type checker centralizzato: rileva se un oggetto rappresenta envelope-like data.
        
        Supporta:
        - Envelope instances
        - Liste di breakpoints [[t, v], ...]
        - Dict con 'type' e 'points'
        - Formato compatto
        
        Returns:
            bool: True se l'oggetto è envelope-like
        """
        from envelopes.envelope_builder import EnvelopeBuilder
        
        # Istanza Envelope
        if isinstance(obj, Envelope):
            return True
        
        # Lista di breakpoints o formato compatto
        if isinstance(obj, list):
            # Lista vuota: NO
            if not obj:
                return False
            
            # Formato compatto
            if EnvelopeBuilder._is_compact_format(obj):
                return True
            
            # Lista con almeno un [t, v]
            for item in obj:
                if isinstance(item, list) and len(item) == 2:
                    return True
                # Formato compatto dentro lista
                if EnvelopeBuilder._is_compact_format(item):
                    return True
            return False
        
        # Dict con 'points'
        if isinstance(obj, dict):
            return 'points' in obj
        
        return False
    

    @staticmethod
    def _scale_raw_values_y(raw_data: Union[List, Dict], scale_factor: float) -> Union[List, Dict]:
        """
        Scala i valori Y dei dati raw, restituendo dati raw (stesso formato dell'input).
        Usato da PointerController._scale_value per mantenere compatibilita'
        col pipeline parser a valle.
        """
        from envelopes.envelope_builder import EnvelopeBuilder
        import copy
        
        def _scale_list_y(points_list):
            scaled = []
            for item in points_list:
                if EnvelopeBuilder._is_compact_format(item):
                    pattern = item[0]
                    scaled_pattern = [[p[0], p[1] * scale_factor] for p in pattern]
                    new_item = list(item)
                    new_item[0] = scaled_pattern
                    scaled.append(new_item)
                elif isinstance(item, list) and len(item) == 2:
                    scaled.append([item[0], item[1] * scale_factor])
                else:
                    scaled.append(item)
            return scaled

        if isinstance(raw_data, dict):
            new_data = copy.deepcopy(raw_data)
            if 'points' in new_data:
                new_data['points'] = _scale_list_y(new_data['points'])
            return new_data

        if isinstance(raw_data, list):
            if EnvelopeBuilder._is_compact_format(raw_data):
                pattern = raw_data[0]
                scaled_pattern = [[p[0], p[1] * scale_factor] for p in pattern]
                new_data = list(raw_data)
                new_data[0] = scaled_pattern
                return new_data
            else:
                return _scale_list_y(raw_data)

        raise ValueError(f"Formato non supportato per _scale_raw_values_y: {raw_data}")

    @staticmethod
    def scale_envelope_values(raw_data: Union[List, Dict], scale_factor: float) -> 'Envelope':
        """
        Crea un Envelope scalando i VALORI Y (non il tempo).
        Usato da PointerController per loop normalizzati (0-1 -> 0-SampleDur).
        """
        scaled_raw = Envelope._scale_raw_values_y(raw_data, scale_factor)
        return Envelope(scaled_raw)

def create_scaled_envelope(
    raw_data: Union[List, Dict],
    duration: float,
    time_mode: str = 'absolute'
    ) -> Envelope:
    """
    Factory helper per creare Envelope con scaling TEMPORALE (X axis).
    Sostituisce la vecchia logica integrandosi con EnvelopeBuilder.
    code Code

    Se time_mode='normalized', moltiplica i tempi [t, v] per 'duration'.
    Nota: I formati compatti (che usano total_time esplicito) NON vengono scalati.
    """
    from envelopes.envelope_builder import EnvelopeBuilder

    # 1. Gestione DICT
    if isinstance(raw_data, dict):
        local_unit = raw_data.get('time_unit', time_mode)
        points = raw_data.get('points', [])
        
        if local_unit == 'normalized':
            scaled_points = _scale_time_recursive(points, duration)
            return Envelope({'type': raw_data.get('type', 'linear'), 'points': scaled_points})
        return Envelope(raw_data)

    # 2. Gestione LIST
    # Se il modo globale è normalized, scaliamo solo i breakpoint semplici
    if time_mode == 'normalized':
        scaled_points = _scale_time_recursive(raw_data, duration)
        return Envelope(scaled_points)

    return Envelope(raw_data)

def _scale_time_recursive(points: List, factor: float) -> List:
    """
    Scala ricorsivamente i tempi per breakpoint standard [t, v].
    Scala anche total_time per formati compatti quando time_mode='normalized'.
    
    Args:
        points: Lista di breakpoints, formati compatti, o mix
        factor: Fattore di scaling (duration dello stream)
    
    Returns:
        Lista con tempi scalati
    """
    from envelopes.envelope_builder import EnvelopeBuilder

    # CASO 1: L'intera lista è un formato compatto
    if EnvelopeBuilder._is_compact_format(points):
        # NUOVO: Scala il total_time (elemento [1])
        scaled_compact = list(points)
        scaled_compact[1] = points[1] * factor
        return scaled_compact

    # CASO 2: Lista di elementi misti
    scaled = []
    for item in points:
        if EnvelopeBuilder._is_compact_format(item):
            scaled_compact = list(item)
            scaled_compact[1] = item[1] * factor
            scaled.append(scaled_compact)
        elif isinstance(item, list) and len(item) == 2:
            # Standard breakpoint: [t, v] -> [t * factor, v]
            scaled.append([item[0] * factor, item[1]])
        else:

            scaled.append(item)
    
    return scaled