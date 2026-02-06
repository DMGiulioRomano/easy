# envelope_builder.py
"""
Builder per parsing formati Envelope (legacy + nuovo formato compatto).

Design Pattern: Builder
- Separa logica di parsing da Envelope
- Gestisce formato legacy: [[t, v], ..., 'cycle']
- Gestisce nuovo formato: [[[x%, y], ...], total_time, n_reps, interp_type?]
"""

from typing import List, Union, Tuple, Optional


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
            raw_points: Lista con mix di:
                - [time, value] (legacy)
                - 'cycle' marker
                - [[[x%, y], ...], total_time, n_reps, interp?] (compact)
                
        Returns:
            Lista espansa con solo [time, value] e 'cycle'
            
        Examples:
            # Legacy passa invariato
            >>> EnvelopeBuilder.parse([[0, 0], [1, 10], 'cycle'])
            [[0, 0], [1, 10], 'cycle']
            
            # Compact viene espanso
            >>> EnvelopeBuilder.parse([
            ...     [[[0, 0], [100, 1]], 0.4, 4]
            ... ])
            [[0.0, 0], [0.1, 1], [0.100001, 0], [0.2, 1], ...]
        """
        expanded = []
        
        for item in raw_points:
            if cls._is_compact_format(item):
                # Espandi formato compatto
                compact_expanded = cls._expand_compact_format(item)
                expanded.extend(compact_expanded)
            else:
                # Legacy: passa invariato
                expanded.append(item)
        
        return expanded
    
    @classmethod
    def _is_compact_format(cls, item) -> bool:
        """
        Rileva se item è formato compatto.
        
        Formato compatto: [pattern_points, total_time, n_reps, interp?]
        - pattern_points è lista di liste [[x%, y], ...]
        - total_time è float/int
        - n_reps è int
        - interp è str opzionale
        
        Returns:
            True se è formato compatto
        """
        if not isinstance(item, list):
            return False
        
        # Deve avere 3 o 4 elementi
        if len(item) < 3:  # Minimo: [pattern_points, total_time, n_reps]
            return False        
        # Primo elemento deve essere lista di liste [[x, y], ...]
        if not isinstance(item[0], list):
            return False
        
        if not item[0]:  # Lista vuota
            return False
        
        # Verifica che sia lista di [x, y]
        if not all(isinstance(p, list) and len(p) == 2 for p in item[0]):
            return False
        
        # Secondo elemento: total_time (float/int)
        if not isinstance(item[1], (int, float)):
            return False
        
        # Terzo elemento: n_reps (int)
        if not isinstance(item[2], int):
            return False
        
        # Quarto elemento opzionale: interp_type (str)
        if len(item) == 4 and not isinstance(item[3], str):
            return False
        
        return True
    
    @classmethod
    def _expand_compact_format(cls, compact: list) -> list:
        """
        Espande formato compatto in breakpoints assoluti con discontinuità.
        
        Args:
            compact: [[[x%, y], ...], total_time, n_reps, interp?]
            
        Returns:
            Lista di breakpoints [t, v] espansi
            
        Algorithm:
            1. Calcola cycle_duration = total_time / n_reps
            2. Per ogni ripetizione:
               - Converti coordinate % → assolute
               - Aggiungi discontinuità (offset 0.000001) tranne dopo ultimo ciclo
            3. Ritorna lista espansa
            
        Examples:
            >>> cls._expand_compact_format([[[0, 0], [100, 1]], 0.4, 4])
            [[0.0, 0], [0.1, 1], [0.100001, 0], [0.2, 1], 
             [0.200001, 0], [0.3, 1], [0.300001, 0], [0.4, 1]]
        """
        # Parse input
        pattern_points_pct = compact[0]
        total_time = compact[1]
        n_reps = compact[2]
        # interp_type ignorato qui (gestito da Envelope)
        
        # Valida
        if n_reps < 1:
            raise ValueError(f"n_reps deve essere >= 1, ricevuto: {n_reps}")
        
        if total_time <= 0:
            raise ValueError(f"total_time deve essere > 0, ricevuto: {total_time}")
        
        if not pattern_points_pct:
            raise ValueError("pattern_points non può essere vuoto")
        
        # Calcola durata ciclo singolo
        cycle_duration = total_time / n_reps
        
        # Estrai primo e ultimo valore per discontinuità
        first_value = pattern_points_pct[0][1]
        
        # Espandi breakpoints
        expanded = []
        
        for rep in range(n_reps):
            cycle_start_time = rep * cycle_duration
            
            # Converti coordinate % → assolute
            for x_pct, y in pattern_points_pct:
                # x_pct è in [0, 100]
                # Normalizza a [0, 1]
                x_normalized = x_pct / 100.0
                
                # Calcola tempo assoluto
                t_absolute = cycle_start_time + (x_normalized * cycle_duration)
                
                expanded.append([t_absolute, y])
            
            # Aggiungi discontinuità DOPO ogni ciclo, tranne l'ultimo
            if rep < n_reps - 1:
                # Tempo = fine ciclo corrente + offset infinitesimale
                last_t = expanded[-1][0]
                discontinuity_t = last_t + cls.DISCONTINUITY_OFFSET
                
                # Valore = primo valore del pattern (reset)
                expanded.append([discontinuity_t, first_value])
        
        return expanded
    
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
        for item in raw_points:
            if cls._is_compact_format(item):
                # Formato compatto con 4 elementi include interp_type
                if len(item) == 4:
                    return item[3]
        
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