"""
DensityController - Gestione densità e distribuzione temporale dei grani.

Implementa il modello Truax per la distribuzione temporale:
- SYNCHRONOUS (distribution=0): inter-onset fisso
- ASYNCHRONOUS (distribution=1): random(0, 2×avg)
- INTERPOLAZIONE: blend lineare tra i due
"""

import random
from typing import Optional
from parameter_evaluator import ParameterEvaluator


class DensityController:
    """
    Controlla la densità granulare e la distribuzione temporale.
    
    Due modalità mutuamente esclusive:
    1. FILL_FACTOR (prioritaria): density = fill_factor / grain_duration
       - La densità si adatta automaticamente alla durata del grano
       
    2. DENSITY diretta: valore fisso o Envelope
       - Controllo esplicito della densità in grani/secondo
    """
    
    def __init__(
        self,
        evaluator: ParameterEvaluator,
        params: dict
    ):
        """
        Inizializza il controller di densità.
        
        Args:
            evaluator: ParameterEvaluator per parsing e valutazione
            params: dizionario parametri YAML
        """
        self.evaluator = evaluator
        
        # Determina modalità e inizializza parametri
        self._init_density_mode(params)
        self._init_distribution(params)
    
    def _init_density_mode(self, params: dict) -> None:
        """
        Determina la modalità di calcolo densità.
        Priorità: fill_factor > density > default (fill_factor=2.0).
        """
        if 'fill_factor' in params:
            # Modalità FILL_FACTOR esplicita
            self.fill_factor = self.evaluator.parse(
                params['fill_factor'], 
                'fill_factor'
            )
            self.density = None
            self._mode = 'fill_factor'
            
        elif 'density' in params:
            # Modalità DENSITY diretta
            self.fill_factor = None
            self.density = self.evaluator.parse(
                params['density'],
                'density'
            )
            self._mode = 'density'
            
        else:
            # DEFAULT: fill_factor = 2.0 (Roads: "covered/packed")
            self.fill_factor = 2.0
            self.density = None
            self._mode = 'fill_factor'
    
    def _init_distribution(self, params: dict) -> None:
        """
        Inizializza il parametro distribution.
        0.0 = sincrono, 1.0 = asincrono.
        """
        self.distribution = self.evaluator.parse(
            params.get('distribution', 0.0),
            'distribution'
        )
    
    @property
    def mode(self) -> str:
        """Ritorna la modalità corrente: 'fill_factor' o 'density'."""
        return self._mode
    
    def calculate_inter_onset(
        self,
        elapsed_time: float,
        current_grain_duration: float
    ) -> float:
        """
        Calcola l'inter-onset time per il prossimo grano usando il modello Truax.
        Usa l'Evaluator per validare e clippare la densità effettiva.
        
        Args:
            elapsed_time: tempo trascorso dall'onset dello stream
            current_grain_duration: durata del grano corrente
            
        Returns:
            float: tempo in secondi fino al prossimo onset
        """
        # 1. Calcola density grezza (raw)
        raw_density = self._calculate_raw_density(
            elapsed_time, 
            current_grain_duration
        )
        
        # 2. Usa Evaluator per Safety Clamp e Logging
        # 'effective_density' deve essere definito nei BOUNDS dell'Evaluator
        effective_density = self.evaluator.evaluate(
            raw_density, 
            elapsed_time, 
            'effective_density'
        )
        
        # 3. Calcola inter-onset medio
        avg_inter_onset = 1.0 / effective_density
        
        # 4. Valuta distribution
        distribution = self.evaluator.evaluate(
            self.distribution,
            elapsed_time,
            'distribution'
        )
        
        # 5. Calcola inter-onset finale (blend sincrono/asincrono)
        if distribution == 0.0:
            return avg_inter_onset
        else:
            sync_value = avg_inter_onset
            async_value = random.uniform(0.0, 2.0 * avg_inter_onset)
            return (1.0 - distribution) * sync_value + distribution * async_value
    
    def _calculate_raw_density(
        self,
        elapsed_time: float,
        current_grain_duration: float
    ) -> float:
        """Calcola la densità grezza prima del clamping in base alla modalità."""
        if self._mode == 'fill_factor':
            ff = self.evaluator.evaluate(
                self.fill_factor,
                elapsed_time,
                'fill_factor'
            )
            # Evita divisione per zero
            if current_grain_duration <= 1e-6:
                current_grain_duration = 0.001
            return ff / current_grain_duration
        else:
            return self.evaluator.evaluate(
                self.density,
                elapsed_time,
                'density'
            )
    
    def get_density_value(self, elapsed_time: float) -> Optional[float]:
        """Ritorna il valore di density se in modalità density (per debug)."""
        if self._mode == 'density':
            return self.evaluator.evaluate(
                self.density, elapsed_time, 'density'
            )
        return None
    
    def get_fill_factor_value(self, elapsed_time: float) -> Optional[float]:
        """Ritorna il valore di fill_factor se in modalità fill_factor (per debug)."""
        if self._mode == 'fill_factor':
            return self.evaluator.evaluate(
                self.fill_factor, elapsed_time, 'fill_factor'
            )
        return None
    
    def get_distribution_value(self, elapsed_time: float) -> float:
        """Ritorna il valore corrente di distribution."""
        return self.evaluator.evaluate(
            self.distribution, elapsed_time, 'distribution'
        )