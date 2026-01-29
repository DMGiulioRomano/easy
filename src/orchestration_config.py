# orchestration_config.py
from dataclasses import dataclass,fields
from typing import Optional, Union
    
@dataclass(frozen=True)
class OrchestrationConfig:
    dephase: Optional[Union[dict, bool, int, float]] = False
    range_always_active: bool = False
    distribution_mode: str = 'uniform'
    time_mode: str = 'absolute'
    time_scale: float = 1.0 

    @classmethod
    def from_yaml(cls, yaml_data: dict, allow_none: bool = True) -> 'OrchestrationConfig':
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