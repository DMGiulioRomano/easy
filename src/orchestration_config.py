# orchestration_config.py
from dataclasses import dataclass,fields
from typing import Optional
    
@dataclass(frozen=True)
class OrchestrationConfig:
    dephase: Optional[dict] = None
    range_always_active: bool = False
    distribution_mode: str = 'uniform'
    
    @classmethod
    def from_yaml(cls, yaml_data: dict, allow_none: bool = False) -> 'OrchestrationConfig':
        """
        Factory method per creare config da YAML con allocazione dinamica.
        
        Estrae automaticamente i campi definiti nel dataclass dai dati YAML.
        """        
        field_names = [f.name for f in fields(cls)]
        
        if allow_none:
            # Includi i campi anche se il valore è None
            kwargs = {name: yaml_data[name] for name in field_names if name in yaml_data}
        else:
            # Includi solo campi con valori non-None
            kwargs = {
                name: yaml_data[name] 
                for name in field_names 
                if name in yaml_data and yaml_data[name] is not None
            }
        
        return cls(**kwargs)            

