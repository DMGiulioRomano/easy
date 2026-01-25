"""
parameter_definitions.py

Questo modulo agisce come REGISTRY (Registro) centrale per le definizioni dei parametri.
Contiene i metadati e le regole di validazione (Bounds) per ogni parametro del sistema granulare.

Design Pattern:
- Value Object: La classe ParameterBounds è immutabile.
- Registry: Il dizionario GRANULAR_PARAMETERS centralizza la configurazione.

Qui definiamo COSA sono i parametri, non COME vengono calcolati.
"""

from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class ParameterBounds:
    """
    Definisce i limiti e il comportamento di variazione per un parametro.
    
    Attributes:
        min_val (float): Valore minimo assoluto consentito (Safety Clamp).
        max_val (float): Valore massimo assoluto consentito (Safety Clamp).
        min_range (float): Valore minimo per il parametro range/randomness associato.
        max_range (float): Valore massimo per il parametro range/randomness associato.
        default_jitter (float): Valore di default per variazioni implicite (Scenario B).
        variation_mode (str): Strategia di variazione stocastica.
            - 'additive': (Default) Variazione continua float (valore ± range/2).
                          Es. Volume, Pan, Density.
            - 'quantized': Variazione a step interi (valore ± int(range/2)).
                           Es. Pitch in semitoni, Sample ID.
            - 'invert':   Variazione booleana/probabilistica (flip 0 <-> 1).
                          Es. Reverse (non usa range additivo, usa probabilità).
    """
    min_val: float
    max_val: float
    min_range: float = 0.0
    max_range: float = 0.0
    default_jitter: float = 0.0
    variation_mode: str = 'additive'

# =============================================================================
# SYSTEM CONSTANTS & DEFAULTS
# =============================================================================

# Probabilità di default (1%) usata quando dephase è attivo ma senza range espliciti.
# Questo attiva il "Jitter Implicito" definito nei bounds dei parametri.
IMPLICIT_JITTER_PROB = 1.0 

# =============================================================================
# PARAMETER REGISTRY
# =============================================================================
# Qui sono definiti tutti i parametri supportati dal sistema.
# Se aggiungi un nuovo parametro al motore audio, devi aggiungerlo qui.

GRANULAR_PARAMETERS: Dict[str, ParameterBounds] = {
    
    # =========================================================================
    # DENSITY & TIME
    # =========================================================================
    'density': ParameterBounds(
        min_val=0.1,
        max_val=4000.0,
        min_range=0.0,
        max_range=100.0,
        default_jitter=50.0,
        variation_mode='additive'
    ),
    
    'fill_factor': ParameterBounds(
        min_val=0.001,
        max_val=50.0,
        min_range=0.0,
        max_range=10.0
    ),
    
    'distribution': ParameterBounds(
        min_val=0.0,
        max_val=1.0
        # distribution non ha solitamente un range stocastico associato
    ),
    
    'effective_density': ParameterBounds(
        min_val=0.01,
        max_val=4000.0
    ),

    # =========================================================================
    # GRAIN PROPERTIES
    # =========================================================================
    'grain_duration': ParameterBounds(
        min_val=0.0001,  # 0.1 ms
        max_val=10.0,    # 10 secondi
        min_range=0.0,
        max_range=1.0,
        default_jitter=0.01,
        variation_mode='additive'
    ),
    
    'reverse': ParameterBounds(
        min_val=0,
        max_val=1,
        min_range=0,
        max_range=1,
        default_jitter=0,
        variation_mode='invert'  # <--- NOTA: (Boolean Flip)
    ),

    # =========================================================================
    # PITCH (La distinzione chiave discussa)
    # =========================================================================
    'pitch_semitones': ParameterBounds(
        min_val=-36.0,
        max_val=36.0,
        min_range=0.0,
        max_range=36.0,
        default_jitter=0.0, # Semitoni di solito non hanno jitter implicito se non richiesto
        variation_mode='quantized'  # <--- NOTA: Variazione a interi (randint)
    ),
    
    'pitch_ratio': ParameterBounds(
        min_val=0.125,   # 3 ottave sotto
        max_val=8.0,     # 3 ottave sopra
        min_range=0.0,
        max_range=2.0,
        default_jitter=0.02,
        variation_mode='additive'   
    ),

    # =========================================================================
    # POINTER (PLAYHEAD)
    # =========================================================================  
    'pointer_speed': ParameterBounds(
        min_val=-100.0,
        max_val=100.0
    ),
    
    'pointer_deviation': ParameterBounds(
        min_val=0.0,
        max_val=1.0,        # Normalizzato (100% del loop)
        min_range=0.0,
        max_range=1.0,
        default_jitter=0.005, # DEFAULT MICRO: 0.5% della durata del loop
        variation_mode='additive'
    ),
    
    'loop_dur': ParameterBounds(
        min_val=0.001,
        max_val=1000.0 # Virtualmente infinito, sarà limitato dalla durata sample
    ),

    # =========================================================================
    # OUTPUT (SPATIALIZATION & AMP)
    # =========================================================================
    'volume': ParameterBounds(
        min_val=-120.0,
        max_val=12.0,
        min_range=0.0,
        max_range=24.0,
        default_jitter=1.5,
        variation_mode='additive'
    ),
    
    'pan': ParameterBounds(
        min_val=-3600.0, # Supporto per pan rotativo su più giri
        max_val=3600.0,
        min_range=0.0,
        max_range=360.0,
        default_jitter=15.0,
        variation_mode='additive'
    ),

    # =========================================================================
    # VOICES
    # =========================================================================
    'num_voices': ParameterBounds(
        min_val=1.0,
        max_val=64.0, # Aumentato per sicurezza
        variation_mode='quantized' # Le voci sono intere, ma gestite dal manager
    ),
    
    'voice_pitch_offset': ParameterBounds(
        min_val=-48.0,
        max_val=48.0
    ),
    
    'voice_pointer_offset': ParameterBounds(
        min_val=-1.0, # Consenti offset negativi
        max_val=1.0
    ),
    
    'voice_pointer_range': ParameterBounds(
        min_val=0.0,
        max_val=1.0
    ),

    # =========================================================================
    # PROBABILITIES (DEPHASE)
    # =========================================================================
    'dephase_prob': ParameterBounds(
        min_val=0.0,
        max_val=100.0,
        variation_mode='additive'
    ),
}

def get_parameter_definition(param_name: str) -> ParameterBounds:
    """
    Recupera la definizione di un parametro dal registro.
    
    Args:
        param_name: Il nome del parametro (es. 'density')
        
    Returns:
        ParameterBounds: L'oggetto configurazione.
        
    Raises:
        KeyError: Se il parametro non esiste nel registro.
    """
    if param_name not in GRANULAR_PARAMETERS:
        raise KeyError(f"Parametro '{param_name}' non definito in parameter_definitions.py")
    return GRANULAR_PARAMETERS[param_name]