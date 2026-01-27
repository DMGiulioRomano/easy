# orchestration_config.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class OrchestrationConfig:
    """
    Configuration object per la costruzione dei parametri.
    
    Questi NON sono attributi del prodotto finale (Stream),
    ma configurazioni del PROCESSO di costruzione.
    
    Configuration Object Pattern:
    - Immutabile (frozen=True)
    - Type-safe (mypy/IDE autocomplete)  
    - Self-documenting (docstrings su campi)
    - Facilmente estendibile (aggiungi campi senza rompere codice)
    
    Attributes:
        dephase_config: Blocco 'dephase:' dal YAML, se presente
        range_always_active: Se True, range è attivo anche senza dephase
        
        # FUTURE FLAGS (esempi)
        # jitter_strength: Moltiplica il default_jitter (es. 2.0 = doppio)
        # strict_bounds: Se True, clippa invece di rifiutare
    """
    dephase_config: Optional[dict] = None
    range_always_active: bool = False
    
    # Futuri flag possono essere aggiunti qui senza rompere codice esistente
    # jitter_strength: float = 1.0
    # strict_bounds: bool = True
    
    @classmethod
    def from_yaml(cls, yaml_data: dict) -> 'OrchestrationConfig':
        """
        Factory method per creare config da YAML.
        
        Centralizza l'estrazione dei flag dal YAML in un unico posto.
        """
        return cls(
            dephase_config=yaml_data.get('dephase'),
            range_always_active=yaml_data.get('range_always_active', False)
        )
    
    def __post_init__(self):
        """Validazione opzionale dei valori."""
        if self.dephase_config is not None:
            if not isinstance(self.dephase_config, dict):
                raise TypeError(f"dephase_config deve essere dict, non {type(self.dephase_config)}")