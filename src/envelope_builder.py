# envelope_builder.py
"""
Builder per parsing formati Envelope (legacy + nuovo formato compatto).

Design Pattern: Builder
- Separa logica di parsing da Envelope
- Gestisce formato legacy: [[t, v], ..., 'cycle']
- Gestisce nuovo formato: [[[x%, y], ...], total_time, n_reps, interp_type?]

FIXES APPLICATI:
1. parse() riconosce formato compatto diretto
2. extract_interp_type() controlla raw_points stesso prima di iterare
3. _expand_compact_format() garantisce ordinamento temporale monotono
4. _is_compact_format() accetta pattern vuoti (validazione in _expand_compact_format)
"""

from typing import List, Union, Tuple, Optional
from time_distribution import TimeDistributionFactory

class EnvelopeBuilder:
    """
    Builder per creare liste di breakpoints da formati multipli.
    
    Supporta:
    - Legacy format: [[0, 0], [0.1, 1], 'cycle']
    - Compact format: [[[0, 0], [100, 1]], 0.4, 4]
    - Mixed formats in single list
    """
    
    # Offset infinitesimale per discontinuità
    DISCONTINUITY_OFFSET = 0.000001
    
    @classmethod
    def parse(cls, raw_points: list) -> list:
        """
        Parsa lista mista di formati, espandendo formato compatto.
        
        Args:
            raw_points: 
                - [[[x%, y], ...], total_time, n_reps, interp?] (formato compatto diretto)
                - Lista con mix di:
                    * [time, value] (legacy)
                    * 'cycle' marker
                    * [[[x%, y], ...], total_time, n_reps, interp?] (compact wrapped)
                
        Returns:
            Lista espansa con solo [time, value] e 'cycle'
            
        Examples:
            # Formato compatto DIRETTO (caso più comune)
            >>> EnvelopeBuilder.parse([[[0, 0], [100, 1]], 0.4, 4])
            [[0.0, 0], [0.1, 1], [0.100001, 0], [0.100002, 0], [0.2, 1], ...]
            
            # Legacy passa invariato
            >>> EnvelopeBuilder.parse([[0, 0], [1, 10], 'cycle'])
            [[0, 0], [1, 10], 'cycle']
        """
        # FIX 1: Controlla PRIMA se raw_points STESSO è un formato compatto
        if cls._is_compact_format(raw_points):
            # Espandi direttamente e ritorna
            return cls._expand_compact_format(raw_points)
        
        # Altrimenti, itera sugli elementi (formato legacy o misto)
        expanded = []
        
        for item in raw_points:
            if cls._is_compact_format(item):
                # Espandi formato compatto
                compact_expanded = cls._expand_compact_format(item)
                expanded.extend(compact_expanded)
            else:
                # Legacy: passa invariato ([t, v] o 'cycle')
                expanded.append(item)
        
        return expanded

    @classmethod
    def _is_compact_format(cls, item: Any) -> bool:
        """
        Riconosce formato compatto.
        
        PRIMA: [pattern, total_time, n_reps, interp?]
        DOPO:  [pattern, total_time, n_reps, interp?, time_dist?]
        """
        if not isinstance(item, list):
            return False
        
        # MODIFICA: Era 3-4, ora 3-5
        if len(item) < 3 or len(item) > 5:
            return False
        
        # [0]: pattern_points (list)
        if not isinstance(item[0], list):
            return False
        
        # [1]: total_time (float/int)
        if not isinstance(item[1], (int, float)):
            return False
        
        # [2]: n_reps (int)
        if not isinstance(item[2], int):
            return False
        
        # [3]: interp_type (str, opzionale)
        if len(item) >= 4 and item[3] is not None:
            if not isinstance(item[3], str):
                return False
        
        # [4]: time_dist (str/dict, opzionale) - NUOVO
        if len(item) == 5 and item[4] is not None:
            if not isinstance(item[4], (str, dict)):
                return False
        
        return True



    @classmethod
    def _expand_compact_format(cls, compact: list) -> list:
        """
        Espande formato compatto usando TimeDistributionStrategy.
        
        Args:
            compact: [pattern, total_time, n_reps, interp?, time_dist?]
        """
        # Parse input
        pattern_points_pct = compact[0]
        total_time = compact[1]
        n_reps = compact[2]
        interp_type = compact[3] if len(compact) >= 4 else None
        time_dist_spec = compact[4] if len(compact) == 5 else None  # NUOVO
        
        # Validazione (come prima)
        if n_reps < 1:
            raise ValueError(f"n_reps deve essere >= 1, ricevuto: {n_reps}")
        if total_time <= 0:
            raise ValueError(f"total_time deve essere > 0, ricevuto: {total_time}")
        if not pattern_points_pct:
            raise ValueError("pattern_points non può essere vuoto")
        
        # NUOVO: Crea strategia di distribuzione temporale
        distributor = TimeDistributionFactory.create(time_dist_spec)
        
        # NUOVO: Ottieni distribuzione cicli
        cycle_start_times, cycle_durations = distributor.calculate_distribution(
            total_time, 
            n_reps
        )
        
        # Espandi breakpoints usando la distribuzione
        expanded = []
        
        for rep in range(n_reps):
            # MODIFICA: Usa cycle_start_times e cycle_durations calcolati
            cycle_start_time = cycle_start_times[rep]
            cycle_duration = cycle_durations[rep]
            
            # Converti coordinate % → assolute per questo ciclo
            for i, (x_pct, y) in enumerate(pattern_points_pct):
                x_normalized = x_pct / 100.0
                t_absolute = cycle_start_time + (x_normalized * cycle_duration)
                
                # Applica offset discontinuità
                if rep > 0 and i == 0:
                    t_absolute += cls.DISCONTINUITY_OFFSET
                
                expanded.append([t_absolute, y])
        
        # MODIFICA: Logging esteso (opzionale)
        cls._log_compact_transformation(compact, expanded, distributor)
        
        return expanded


    @classmethod
    def _log_compact_transformation(
        cls, 
        compact: list, 
        expanded: list,
        distributor = None  # NUOVO parametro
    ):
        """
        Logga trasformazione con info distribuzione temporale.
        
        MODIFICA: Aggiungi parametro distributor opzionale
        """
        from logger import get_clip_logger
        
        logger = get_clip_logger()
        if logger is None:
            return
        
        # Parse compact
        pattern_points_pct = compact[0]
        total_time = compact[1]
        n_reps = compact[2]
        interp_type = compact[3] if len(compact) >= 4 else None
        time_dist_spec = compact[4] if len(compact) == 5 else None  # NUOVO
        
        # Log header
        logger.info(f"\n{'='*80}\nCOMPACT ENVELOPE TRANSFORMATION\n{'='*80}")
        
        # Input
        logger.info(f"\n[INPUT] Compact format:")
        logger.info(f"  Pattern points: {pattern_points_pct}")
        logger.info(f"  Total time: {total_time}s")
        logger.info(f"  Repetitions: {n_reps}")
        if interp_type:
            logger.info(f"  Interpolation: {interp_type}")
        if time_dist_spec:  # NUOVO
            logger.info(f"  Time distribution: {time_dist_spec}")
        if distributor:  # NUOVO
            logger.info(f"  Distribution strategy: {distributor.name}")
        
        # Output
        logger.info(f"\n[OUTPUT] Expanded format:")
        logger.info(f"  Total breakpoints: {len(expanded)}")
        logger.info(f"  Time range: {expanded[0][0]:.6f}s → {expanded[-1][0]:.6f}s")
        
        # Mostra distribuzione cicli
        if distributor and n_reps > 1:
            starts, durations = distributor.calculate_distribution(total_time, n_reps)
            logger.info(f"\n[CYCLE DISTRIBUTION]:")
            for i in range(n_reps):
                logger.info(
                    f"  Cycle {i}: {starts[i]:.3f}s - {starts[i] + durations[i]:.3f}s "
                    f"(duration: {durations[i]:.3f}s)"
                )
        
        logger.info(f"{'='*80}\n")



    @classmethod
    def extract_interp_type(cls, raw_points: list) -> Optional[str]:
        """
        Estrae tipo interpolazione da formato compatto (se presente).
        
        Se ci sono più formati compatti con tipi diversi, usa il primo.
        
        Args:
            raw_points: Lista con possibili formati compatti
            
        Returns:
            str or None: Tipo interpolazione ('linear', 'cubic', 'step')
        """
        # FIX 2: Controlla PRIMA se raw_points STESSO è formato compatto con tipo
        if cls._is_compact_format(raw_points):
            # Formato compatto con 4 elementi include interp_type
            if len(raw_points) == 4:
                return raw_points[3]
            return None
        
        # Altrimenti itera sugli elementi (formato misto)
        for item in raw_points:
            if cls._is_compact_format(item):
                # Formato compatto con 4 elementi include interp_type
                if len(item) == 4:
                    return item[3]
        
        return None

    @classmethod
    def extract_time_dist(cls, raw_points: list) -> Optional[Union[str, dict]]:
        """
        Estrae specifica distribuzione temporale da formato compatto.
        
        Returns:
            time_dist spec (str o dict) o None
        """
        if cls._is_compact_format(raw_points):
            if len(raw_points) == 5:
                return raw_points[4]
        return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def detect_format_type(item) -> str:
    """
    Helper per debugging: rileva tipo di formato.
    
    Returns:
        'compact' | 'breakpoint' | 'cycle' | 'unknown'
    """
    if isinstance(item, str) and item.lower() == 'cycle':
        return 'cycle'
    
    if EnvelopeBuilder._is_compact_format(item):
        return 'compact'
    
    if isinstance(item, list) and len(item) == 2:
        return 'breakpoint'
    
    return 'unknown'