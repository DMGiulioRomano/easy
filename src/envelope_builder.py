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
        
        if len(item) > 4:  # Massimo: [pattern_points, total_time, n_reps, interp]
            return False
        
        # Primo elemento deve essere lista (anche se vuota)
        if not isinstance(item[0], list):
            return False
        
        # FIX 4: NON rifiutare pattern vuoti qui
        # La validazione "pattern_points non può essere vuoto" è in _expand_compact_format
        
        # Se pattern NON vuoto, verifica formato [x, y]
        if item[0]:
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
        Garantisce ordinamento temporale monotono stretto.
        
        Args:
            compact: [[[x%, y], ...], total_time, n_reps, interp?]
            
        Returns:
            Lista di breakpoints [t, v] con tempi strettamente crescenti
            
        Algorithm:
            1. Calcola cycle_duration = total_time / n_reps
            2. Per ogni ripetizione:
               - Converti coordinate % → assolute
               - Se tempo <= precedente, sposta avanti con offset
               - Aggiungi discontinuità dopo ogni ciclo (tranne l'ultimo)
            3. Ritorna lista con tempi garantiti strettamente crescenti
            
        Examples:
            >>> cls._expand_compact_format([[[0, 0], [100, 1]], 0.4, 4])
            [[0.0, 0], [0.1, 1], [0.100001, 0], [0.100002, 0], [0.2, 1], ...]
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
        
        # Estrai primo valore per discontinuità
        first_value = pattern_points_pct[0][1]
        
        # Espandi breakpoints
        expanded = []
        
        for rep in range(n_reps):
            cycle_start_time = rep * cycle_duration
            
            # Converti coordinate % → assolute per questo ciclo
            for x_pct, y in pattern_points_pct:
                # x_pct è in [0, 100]
                # Normalizza a [0, 1]
                x_normalized = x_pct / 100.0
                
                # Calcola tempo assoluto
                t_absolute = cycle_start_time + (x_normalized * cycle_duration)
                
                # FIX CRITICAL: Garantisce ordinamento monotono stretto
                # Se il tempo è <= all'ultimo inserito, sposta avanti
                if expanded and t_absolute <= expanded[-1][0]:
                    t_absolute = expanded[-1][0] + cls.DISCONTINUITY_OFFSET
                
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