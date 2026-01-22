"""
parameter_factory.py

Factory che assembla oggetti Parameter per Stream.

Combina:
- parameter_schema.py: Sa DOVE trovare i dati nel YAML
- parameter_definitions.py: Sa QUALI SONO i limiti (bounds)
- parser.py: Sa COME creare oggetti Parameter

Design Pattern:
- Factory: Crea oggetti complessi nascondendo i dettagli
- Facade: Interfaccia semplice verso sottosistemi complessi
"""

from typing import Any, Dict, Optional, Union

from parameter import Parameter
from parser import GranularParser
from parameter_schema import STREAM_PARAMETER_SCHEMA, ParameterSpec
# IMPORTA LA COSTANTE DAL REGISTRY
from parameter_definitions import IMPLICIT_JITTER_PROB 


class ParameterFactory:
    """
    Factory per la creazione dei parametri di Stream.
    
    Legge lo schema dichiarativo e usa GranularParser per creare
    gli oggetti Parameter. Stream non deve sapere come funziona
    il parsing, riceve solo i Parameter pronti all'uso.
    
    Usage:
        factory = ParameterFactory('stream_1', duration=10.0)
        params = factory.create_all_parameters(yaml_data)
        
        # params = {'volume': Parameter, 'pan': Parameter, ...}
        
        # In Stream.__init__:
        for name, param in params.items():
            setattr(self, name, param)
    """
    
    def __init__(
        self, 
        stream_id: str, 
        duration: float, 
        time_mode: str = 'absolute'
    ):
        """
        Inizializza la factory con il contesto dello Stream.
        
        Args:
            stream_id: ID dello stream (per logging)
            duration: Durata totale (per normalizzazione envelope)
            time_mode: 'absolute' o 'normalized'
        """
        self._parser = GranularParser(stream_id, duration, time_mode)
        self._stream_id = stream_id
    
    def create_all_parameters(
        self, 
        yaml_data: dict,
        schema: list = None
    ) -> Dict[str, Union[Parameter, Any]]:
        """
        Crea tutti i parametri definiti nello schema.
        
        Args:
            yaml_data: Dict completo dei parametri YAML dello stream
            
        Returns:
            Dict[nome_attributo, Parameter o valore raw]
        """
        result = {}
        dephase = yaml_data.get('dephase')  
        
        # Se schema è None, usa quello di default (Stream)
        target_schema = schema if schema is not None else STREAM_PARAMETER_SCHEMA


        for spec in target_schema:
            if spec.is_smart:
                result[spec.name] = self._create_smart_parameter(spec, yaml_data, dephase)
            else:
                result[spec.name] = self._extract_raw_value(spec, yaml_data)

        return result
    
    def create_single_parameter(
        self, 
        name: str, 
        yaml_data: dict
    ) -> Union[Parameter, Any]:
        """
        Crea un singolo parametro per nome.
        
        Utile per testing o per creare parametri singoli.
        """
        from parameter_schema import get_parameter_spec
        
        spec = get_parameter_spec(name)
        dephase = yaml_data.get('dephase')
        
        if spec.is_smart:
            return self._create_smart_parameter(spec, yaml_data, dephase)
        return self._extract_raw_value(spec, yaml_data)
    
    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================
    
    def _create_smart_parameter(
        self, 
        spec: ParameterSpec, 
        yaml_data: dict, 
        dephase: Optional[dict]
    ) -> Parameter:
        """
        Crea un oggetto Parameter usando GranularParser.
        """
        # 1. Estrai valore base dal YAML
        value = self._get_nested(yaml_data, spec.yaml_path, spec.default)
        
        # 2. Estrai range se definito nello schema
        range_val = None
        if spec.range_path:
            range_val = self._get_nested(yaml_data, spec.range_path, None)
        
        # Passo anche range_val perché serve per decidere se dare 1% o 100%
        prob_val = self._resolve_dephase_prob(spec, dephase, range_val)
        # 4. Usa il parser per creare il Parameter
        return self._parser.parse_parameter(
            name=spec.name,  # Stessa chiave per bounds e attributo
            value_raw=value,
            range_raw=range_val,
            prob_raw=prob_val
        )
    
    def _extract_raw_value(self, spec: ParameterSpec, yaml_data: dict) -> Any:
        """
        Estrae un valore raw (non Parameter) dal YAML.
        
        Usato per parametri come 'grain_envelope' che sono stringhe.
        """
        return self._get_nested(yaml_data, spec.yaml_path, spec.default)
    
    def _resolve_dephase_prob(
        self, 
        spec: ParameterSpec, 
        dephase: Optional[dict],
        range_val: Optional[Any]
    ) -> Optional[Any]:
        """
        Risolve la probabilità dephase per un parametro.
        
        Logica:
        - Se spec.dephase_key è None → parametro non supporta dephase → None
        - Se dephase è None (assente nel YAML) → None (Scenario A: sempre attivo)
        - Se dephase esiste ma la chiave specifica no → None (usa default del Parameter)
        - Altrimenti → valore specificato
        """
        if spec.dephase_key is None:
            return None
        
        if dephase is None:
            return None
        
        # 1. Cerca valore esplicito
        explicit_prob = dephase.get(spec.dephase_key)
        if explicit_prob is not None:
            return explicit_prob
            
        # 2. SE LA CHIAVE MANCA:
        if range_val is None:
            # Caso: Dephase attivo, ma Nessun Range e Nessuna Probabilità specificata.
            # Ritorna 1.0 (1%) -> Attiva il "Jitter Implicito" leggero
            return IMPLICIT_JITTER_PROB
        else:
            # Caso: Utente ha messo un Range esplicito ma nessuna probabilità.
            # Ritorna None (100%) -> Applica quel range a tutti i grani
            return None
        
    @staticmethod
    def _get_nested(data: dict, path: str, default: Any) -> Any:
        """
        Naviga un dict con dot notation.
        
        Examples:
            _get_nested({'grain': {'duration': 0.05}}, 'grain.duration', 0.1)
            → 0.05
            
            _get_nested({'volume': -6}, 'volume', 0)
            → -6
            
            _get_nested({}, 'missing.path', 42)
            → 42
        """
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current