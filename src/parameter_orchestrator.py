"""
parameter_orchestrator.py - Coordina ParameterFactory e GateFactory.
Isola completamente la logica di dephase dal parsing dei parametri.
"""

from typing import Dict, Optional
from parameter_factory import ParameterFactory
from gate_factory import GateFactory
from probability_gate import ProbabilityGate
from parameter import Parameter
from parameter_schema import ParameterSpec
from parameter_definitions import IMPLICIT_JITTER_PROB
from exclusive_selector import ExclusiveGroupSelector

class ParameterOrchestrator:
    """
    Orchestratore: collega ParameterFactory e GateFactory senza accoppiarle.
    """
    
    def __init__(
        self,
        stream_id: str,
        duration: float,
        time_mode: str = 'absolute'
    ):
        self._param_factory = ParameterFactory(
            stream_id, duration, "Orchestrator", time_mode
        )
        self._stream_id = stream_id
        self._dephase_config = None
    
    def set_dephase_config(
        self, 
        dephase_config: Optional[dict],
        range_always_active: bool = False
    ):
        """
        Imposta configurazione dephase e flag globale range.
        
        Context Object Pattern: raggruppa configurazioni correlate.
        """
        self._dephase_config = dephase_config
        self._range_always_active = range_always_active  # ← SALVA
    
    def create_parameter_with_gate(
        self,
        name: str,
        yaml_data: dict,
        param_spec: ParameterSpec
    ) -> Parameter:
        """
        Crea un Parameter completo con il suo ProbabilityGate.
        
        Design Pattern: Strategy Injection
        """
        # 1. Crea il Parameter base (SENZA probabilità)
        param = self._param_factory.create_single_parameter(name, yaml_data)

        # Controlla se range è esplicitato
        has_explicit_range = False
        if param_spec.range_path:
            range_val = ParameterFactory._get_nested(
                yaml_data, param_spec.range_path, None
            )
            has_explicit_range = (range_val is not None)
            
        # 2. Crea il ProbabilityGate corrispondente
        gate = GateFactory.create_gate(
            dephase_config=self._dephase_config,
            param_key=param_spec.dephase_key,
            default_prob=IMPLICIT_JITTER_PROB,
            has_explicit_range=has_explicit_range,
            range_always_active=self._range_always_active
        )
        
        # 3. Inietta il gate nel Parameter (modifica la classe Parameter)
        param.set_probability_gate(gate)
        
        return param
    
    def create_all_parameters(
        self,
        yaml_data: dict,
        schema: list
    ) -> Dict[str, Parameter]:
        """
        Crea tutti i parametri con i rispettivi gate.
        """
        
        # Seleziona parametri attivi
        selected_specs, _ = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        result = {}
        for spec_name, spec in selected_specs.items():
            if spec.is_smart:
                param = self.create_parameter_with_gate(
                    spec_name, yaml_data, spec
                )
                result[spec_name] = param
            else:
                # Parametri non smart (raw)
                result[spec_name] = self._param_factory._extract_raw_value(
                    spec, yaml_data
                )
        
        return result
    
