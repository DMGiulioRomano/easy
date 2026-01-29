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
from parameter_definitions import DEFAULT_PROB
from exclusive_selector import ExclusiveGroupSelector
from orchestration_config import OrchestrationConfig

class ParameterOrchestrator:
    """
    Orchestratore: collega ParameterFactory e GateFactory senza accoppiarle.
    """
    
    def __init__(
        self,
        stream_id: str,
        duration: float,
        config: OrchestrationConfig = None
    ):
        self._config = config
        self._param_factory = ParameterFactory(
            stream_id=stream_id, 
            duration=duration,
            distribution_mode=self._config.distribution_mode
        )
        self._stream_id = stream_id
        self._duration=duration        
    
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
                param = self.create_parameter_with_gate(yaml_data, spec)
                result[spec_name] = param
            else:
                # Parametri non smart (raw)
                result[spec_name] = self._param_factory.create_raw_parameter(spec, yaml_data)
        return result
    
    def create_parameter_with_gate(
        self,
        yaml_data: dict,
        param_spec: ParameterSpec
    ) -> Parameter:
        """
        Crea un Parameter completo con il suo ProbabilityGate.
        
        Design Pattern: Strategy Injection
        """
        # 1. Crea il Parameter base (SENZA probabilità)
        param = self._param_factory.create_smart_parameter(param_spec, yaml_data)

        # Controlla se range è esplicitato
        has_explicit_range = False
        has_explicit_range = param._mod_range is not None
        
        # 2. Crea il ProbabilityGate corrispondente
        gate = GateFactory.create_gate(
            dephase=self._config.dephase,       
            param_key=param_spec.dephase_key,
            default_prob=DEFAULT_PROB,
            has_explicit_range=has_explicit_range,
            range_always_active=self._config.range_always_active,
            duration=self._duration,
            time_mode=self._config.time_mode
        )        
        # 3. Inietta il gate nel Parameter (modifica la classe Parameter)
        param.set_probability_gate(gate)
        
        return param