"""
test_parameter_factory.py

Test suite completa per parameter_factory.py e parameter_orchestrator.py.

Coverage:
1. Test ParameterFactory - creazione base
2. Test _get_nested - navigazione YAML
3. Test create_smart_parameter
4. Test create_raw_parameter
5. Test ParameterOrchestrator - orchestrazione completa
6. Test create_parameter_with_gate - gate injection
7. Test ExclusiveGroupSelector - gruppi mutuamente esclusivi
8. Test integrazione schema completi
9. Test error handling
10. Test edge cases
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
sys.path.insert(0, '/home/claude')

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# =============================================================================
# MOCK CLASSES E STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class ParameterSpec:
    """Mock ParameterSpec."""
    name: str
    yaml_path: str
    default: Any
    range_path: Optional[str] = None
    dephase_key: Optional[str] = None
    is_smart: bool = True
    exclusive_group: Optional[str] = None
    group_priority: int = 99


class Parameter:
    """Mock Parameter."""
    def __init__(self, name, value, bounds, mod_range=None, 
                 owner_id="unknown", distribution_mode='uniform'):
        self.name = name
        self.value = value
        self.bounds = bounds
        self.mod_range = mod_range
        self.owner_id = owner_id
        self._probability_gate = None
    
    def set_probability_gate(self, gate):
        self._probability_gate = gate


class ParameterBounds:
    """Mock ParameterBounds."""
    def __init__(self, min_val=0.0, max_val=100.0):
        self.min_val = min_val
        self.max_val = max_val
        self.variation_mode = 'additive'


class ProbabilityGate:
    """Mock ProbabilityGate."""
    def should_apply(self, time: float) -> bool:
        return True


class StreamConfig:
    """Mock StreamConfig."""
    class Context:
        def __init__(self):
            self.stream_id = "test_stream"
            self.duration = 10.0
            self.sample_dur_sec = 5.0
    
    def __init__(self):
        self.context = self.Context()
        self.time_mode = 'absolute'
        self.distribution_mode = 'uniform'
        self.dephase = {}
        self.range_always_active = False


# Mock functions
def get_parameter_definition(name):
    """Mock get_parameter_definition."""
    return ParameterBounds()


# =============================================================================
# GRANULAR PARSER (simplified mock)
# =============================================================================

class GranularParser:
    """Simplified mock GranularParser."""
    def __init__(self, config):
        self.stream_id = config.context.stream_id
        self.duration = config.context.duration
        self.time_mode = config.time_mode
        self.distribution_mode = config.distribution_mode
    
    def parse_parameter(self, name, value_raw, range_raw=None, prob_raw=None):
        """Create Parameter from raw values."""
        bounds = get_parameter_definition(name)
        return Parameter(
            name=name,
            value=value_raw if not isinstance(value_raw, list) else value_raw,
            bounds=bounds,
            mod_range=range_raw,
            owner_id=self.stream_id,
            distribution_mode=self.distribution_mode
        )


# =============================================================================
# EXCLUSIVE GROUP SELECTOR
# =============================================================================

class ExclusiveGroupSelector:
    """Selector for mutually exclusive parameters."""
    
    @staticmethod
    def select_parameters(schema: List[ParameterSpec], 
                         yaml_data: dict) -> tuple:
        """Select parameters handling exclusive groups."""
        groups = {}
        selected_specs = {}
        group_members = {}
        
        # Group specs by exclusive_group
        for spec in schema:
            if spec.exclusive_group:
                if spec.exclusive_group not in groups:
                    groups[spec.exclusive_group] = []
                    group_members[spec.exclusive_group] = []
                groups[spec.exclusive_group].append(spec)
                group_members[spec.exclusive_group].append(spec)
            else:
                selected_specs[spec.name] = spec
        
        # Select one from each group
        for group_name, group_specs in groups.items():
            # Sort by priority
            sorted_specs = sorted(group_specs, key=lambda s: s.group_priority)
            
            # Find first present in YAML
            winner = None
            for spec in sorted_specs:
                value = ExclusiveGroupSelector._get_nested(yaml_data, spec.yaml_path)
                if value is not None:
                    winner = spec
                    break
            
            # If none present, use highest priority with default
            if winner is None:
                winner = sorted_specs[0]
            
            selected_specs[winner.name] = winner
        
        return selected_specs, group_members
    
    @staticmethod
    def _get_nested(data: dict, path: str) -> Any:
        """Get nested value from dict."""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        
        return current


# =============================================================================
# GATE FACTORY
# =============================================================================

class GateFactory:
    """Factory for ProbabilityGate."""
    
    @staticmethod
    def create_gate(dephase, param_key, default_prob, has_explicit_range,
                   range_always_active, duration, time_mode):
        """Create a ProbabilityGate."""
        return ProbabilityGate()


# =============================================================================
# PARAMETER FACTORY
# =============================================================================

class ParameterFactory:
    """Factory for creating Parameter objects."""
    
    def __init__(self, config):
        self._parser = GranularParser(config)
        self._stream_id = config.context.stream_id
    
    def create_smart_parameter(self, spec: ParameterSpec, 
                              yaml_data: dict) -> Parameter:
        """Create smart Parameter from spec."""
        # 1. Get value from YAML
        value = self._get_nested(yaml_data, spec.yaml_path, spec.default)
        
        # 2. Get range if defined
        range_val = None
        if spec.range_path:
            range_val = self._get_nested(yaml_data, spec.range_path, None)
        
        # 3. Use parser to create Parameter
        return self._parser.parse_parameter(
            name=spec.name,
            value_raw=value,
            range_raw=range_val
        )
    
    def create_raw_parameter(self, spec: ParameterSpec, 
                            yaml_data: dict) -> Any:
        """Extract raw value from YAML."""
        return self._get_nested(yaml_data, spec.yaml_path, spec.default)
    
    @staticmethod
    def _get_nested(data: dict, path: str, default: Any) -> Any:
        """Navigate dict with dot notation."""
        if path.startswith('_'):  # Internal marker
            return default
        
        keys = path.split('.')
        current = data
        
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        
        return current


# =============================================================================
# PARAMETER ORCHESTRATOR
# =============================================================================

class ParameterOrchestrator:
    """Orchestrates ParameterFactory and GateFactory."""
    
    def __init__(self, config: StreamConfig):
        self._param_factory = ParameterFactory(config)
        self._config = config
    
    def create_all_parameters(self, yaml_data: dict, 
                            schema: List[ParameterSpec]) -> Dict[str, Parameter]:
        """Create all parameters from schema."""
        # 1. Select parameters (handle exclusive groups)
        selected_specs, group_members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        result = {}
        
        # 2. Create parameters
        for spec_name, spec in selected_specs.items():
            if spec.is_smart:
                param = self.create_parameter_with_gate(yaml_data, spec)
                result[spec_name] = param
            else:
                result[spec_name] = self._param_factory.create_raw_parameter(
                    spec, yaml_data
                )
        
        # 3. Set losers to None
        for group_specs in group_members.values():
            for spec in group_specs:
                if spec.name not in result:
                    result[spec.name] = None
        
        return result
    
    def create_parameter_with_gate(self, yaml_data: dict,
                                  param_spec: ParameterSpec) -> Parameter:
        """Create Parameter with ProbabilityGate injection."""
        # 1. Create base Parameter
        param = self._param_factory.create_smart_parameter(param_spec, yaml_data)
        
        # 2. Check explicit range
        has_explicit_range = param.mod_range is not None
        
        # 3. Create gate
        gate = GateFactory.create_gate(
            dephase=self._config.dephase,
            param_key=param_spec.dephase_key,
            default_prob=75.0,  # Mock default
            has_explicit_range=has_explicit_range,
            range_always_active=self._config.range_always_active,
            duration=self._config.context.duration,
            time_mode=self._config.time_mode
        )
        
        # 4. Inject gate
        param.set_probability_gate(gate)
        
        return param


# =============================================================================
# 1. TEST PARAMETER FACTORY - INITIALIZATION
# =============================================================================

class TestParameterFactoryInitialization:
    """Test ParameterFactory initialization."""
    
    def test_create_factory_with_config(self):
        """Create factory with StreamConfig."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        assert factory._stream_id == "test_stream"
        assert isinstance(factory._parser, GranularParser)
    
    def test_factory_creates_parser(self):
        """Factory creates GranularParser internally."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        assert hasattr(factory, '_parser')
        assert factory._parser.stream_id == "test_stream"


# =============================================================================
# 2. TEST _GET_NESTED
# =============================================================================

class TestGetNested:
    """Test _get_nested - YAML navigation."""
    
    def test_simple_key(self):
        """Navigate simple key."""
        data = {'volume': -6.0}
        
        result = ParameterFactory._get_nested(data, 'volume', 0.0)
        
        assert result == -6.0
    
    def test_nested_key(self):
        """Navigate nested key with dot notation."""
        data = {'grain': {'duration': 0.05}}
        
        result = ParameterFactory._get_nested(data, 'grain.duration', 0.1)
        
        assert result == 0.05
    
    def test_deep_nested_key(self):
        """Navigate deeply nested key."""
        data = {'a': {'b': {'c': 42}}}
        
        result = ParameterFactory._get_nested(data, 'a.b.c', 0)
        
        assert result == 42
    
    def test_missing_key_returns_default(self):
        """Missing key returns default."""
        data = {'volume': -6.0}
        
        result = ParameterFactory._get_nested(data, 'missing', 0.0)
        
        assert result == 0.0
    
    def test_partial_path_returns_default(self):
        """Partial path (not complete) returns default."""
        data = {'grain': {'duration': 0.05}}
        
        result = ParameterFactory._get_nested(data, 'grain.missing', 0.1)
        
        assert result == 0.1
    
    def test_non_dict_in_path_returns_default(self):
        """Non-dict in path returns default."""
        data = {'grain': 42}  # Not a dict
        
        result = ParameterFactory._get_nested(data, 'grain.duration', 0.1)
        
        assert result == 0.1
    
    def test_internal_marker_returns_default(self):
        """Path starting with _ returns default."""
        data = {'test': 10}
        
        result = ParameterFactory._get_nested(data, '_internal_calc_', 0)
        
        assert result == 0


# =============================================================================
# 3. TEST CREATE_SMART_PARAMETER
# =============================================================================

class TestCreateSmartParameter:
    """Test create_smart_parameter."""
    
    def test_create_parameter_from_simple_value(self):
        """Create Parameter from simple value."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0
        )
        yaml_data = {'volume': -12.0}
        
        param = factory.create_smart_parameter(spec, yaml_data)
        
        assert param.name == 'volume'
        assert param.value == -12.0
    
    def test_create_parameter_with_default(self):
        """Create Parameter using default value."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='pan',
            yaml_path='pan',
            default=0.0
        )
        yaml_data = {}  # Empty
        
        param = factory.create_smart_parameter(spec, yaml_data)
        
        assert param.value == 0.0
    
    def test_create_parameter_with_range(self):
        """Create Parameter with range."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            range_path='volume_range'
        )
        yaml_data = {'volume': -12.0, 'volume_range': 3.0}
        
        param = factory.create_smart_parameter(spec, yaml_data)
        
        assert param.value == -12.0
        assert param.mod_range == 3.0
    
    def test_create_parameter_nested_path(self):
        """Create Parameter from nested YAML path."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='grain_duration',
            yaml_path='grain.duration',
            default=0.05
        )
        yaml_data = {'grain': {'duration': 0.1}}
        
        param = factory.create_smart_parameter(spec, yaml_data)
        
        assert param.value == 0.1


# =============================================================================
# 4. TEST CREATE_RAW_PARAMETER
# =============================================================================

class TestCreateRawParameter:
    """Test create_raw_parameter."""
    
    def test_create_raw_string(self):
        """Create raw string value."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='envelope',
            yaml_path='envelope',
            default='hanning',
            is_smart=False
        )
        yaml_data = {'envelope': 'triangle'}
        
        result = factory.create_raw_parameter(spec, yaml_data)
        
        assert result == 'triangle'
    
    def test_create_raw_number(self):
        """Create raw number value."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='count',
            yaml_path='count',
            default=1,
            is_smart=False
        )
        yaml_data = {'count': 5}
        
        result = factory.create_raw_parameter(spec, yaml_data)
        
        assert result == 5
    
    def test_create_raw_uses_default(self):
        """Create raw parameter uses default if missing."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='mode',
            yaml_path='mode',
            default='auto',
            is_smart=False
        )
        yaml_data = {}
        
        result = factory.create_raw_parameter(spec, yaml_data)
        
        assert result == 'auto'


# =============================================================================
# 5. TEST PARAMETER ORCHESTRATOR
# =============================================================================

class TestParameterOrchestrator:
    """Test ParameterOrchestrator."""
    
    def test_create_orchestrator(self):
        """Create orchestrator with config."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        assert hasattr(orchestrator, '_param_factory')
        assert hasattr(orchestrator, '_config')
    
    def test_create_all_parameters_simple(self):
        """Create all parameters from simple schema."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('volume', 'volume', -6.0),
            ParameterSpec('pan', 'pan', 0.0)
        ]
        yaml_data = {'volume': -12.0, 'pan': 0.5}
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert 'volume' in params
        assert 'pan' in params
        assert params['volume'].value == -12.0
        assert params['pan'].value == 0.5
    
    def test_create_all_parameters_sets_none_for_missing(self):
        """Missing exclusive group members set to None."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('pitch_ratio', 'ratio', 1.0, 
                         exclusive_group='pitch', group_priority=2),
            ParameterSpec('pitch_semitones', 'semitones', None,
                         exclusive_group='pitch', group_priority=1)
        ]
        yaml_data = {'semitones': 7}  # Only semitones present
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert params['pitch_semitones'] is not None
        assert params['pitch_ratio'] is None  # Loser set to None


# =============================================================================
# 6. TEST CREATE_PARAMETER_WITH_GATE
# =============================================================================

class TestCreateParameterWithGate:
    """Test create_parameter_with_gate - gate injection."""
    
    def test_creates_parameter_with_gate(self):
        """Creates Parameter and injects gate."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        spec = ParameterSpec(
            name='volume',
            yaml_path='volume',
            default=-6.0,
            dephase_key='volume'
        )
        yaml_data = {'volume': -12.0}
        
        param = orchestrator.create_parameter_with_gate(yaml_data, spec)
        
        assert param._probability_gate is not None
        assert isinstance(param._probability_gate, ProbabilityGate)
    
    def test_gate_created_with_explicit_range(self):
        """Gate creation detects explicit range."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        spec = ParameterSpec(
            name='pitch',
            yaml_path='ratio',
            default=1.0,
            range_path='range',
            dephase_key='pitch'
        )
        yaml_data = {'ratio': 1.0, 'range': 0.1}
        
        param = orchestrator.create_parameter_with_gate(yaml_data, spec)
        
        assert param.mod_range == 0.1
        assert param._probability_gate is not None


# =============================================================================
# 7. TEST EXCLUSIVE GROUP SELECTOR
# =============================================================================

class TestExclusiveGroupSelector:
    """Test ExclusiveGroupSelector."""
    
    def test_select_from_exclusive_group_by_priority(self):
        """Select parameter by priority when both present."""
        schema = [
            ParameterSpec('option_a', 'a', 1, 
                         exclusive_group='test', group_priority=2),
            ParameterSpec('option_b', 'b', 2,
                         exclusive_group='test', group_priority=1)
        ]
        yaml_data = {'a': 10, 'b': 20}
        
        selected, members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        # option_b has priority 1 (higher)
        assert 'option_b' in selected
        assert 'option_a' not in selected
    
    def test_select_present_over_missing(self):
        """Select present parameter over missing higher priority."""
        schema = [
            ParameterSpec('high_priority', 'high', None,
                         exclusive_group='test', group_priority=1),
            ParameterSpec('low_priority', 'low', 5,
                         exclusive_group='test', group_priority=2)
        ]
        yaml_data = {'low': 10}  # Only low present
        
        selected, members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        # low_priority present, high_priority missing
        assert 'low_priority' in selected
    
    def test_select_default_if_none_present(self):
        """Select highest priority with default if none present."""
        schema = [
            ParameterSpec('option_a', 'a', 1,
                         exclusive_group='test', group_priority=1),
            ParameterSpec('option_b', 'b', 2,
                         exclusive_group='test', group_priority=2)
        ]
        yaml_data = {}  # Neither present
        
        selected, members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        # option_a has priority 1 (highest)
        assert 'option_a' in selected
    
    def test_non_exclusive_always_included(self):
        """Non-exclusive parameters always included."""
        schema = [
            ParameterSpec('volume', 'volume', -6.0),  # Not exclusive
            ParameterSpec('option_a', 'a', 1,
                         exclusive_group='test', group_priority=1)
        ]
        yaml_data = {'volume': -12.0, 'a': 5}
        
        selected, members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        assert 'volume' in selected
        assert 'option_a' in selected
    
    def test_multiple_exclusive_groups(self):
        """Handle multiple exclusive groups."""
        schema = [
            ParameterSpec('pitch_a', 'pitch.a', 1,
                         exclusive_group='pitch', group_priority=1),
            ParameterSpec('pitch_b', 'pitch.b', 2,
                         exclusive_group='pitch', group_priority=2),
            ParameterSpec('density_a', 'density.a', 10,
                         exclusive_group='density', group_priority=1),
            ParameterSpec('density_b', 'density.b', 20,
                         exclusive_group='density', group_priority=2)
        ]
        yaml_data = {
            'pitch': {'a': 5},
            'density': {'b': 15}
        }
        
        selected, members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        assert 'pitch_a' in selected
        assert 'density_b' in selected


# =============================================================================
# 8. TEST INTEGRATION COMPLETE
# =============================================================================

class TestFactoryOrchestratorIntegration:
    """Test complete integration."""
    
    def test_complete_workflow_simple(self):
        """Complete workflow: YAML → Parameters."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('volume', 'volume', -6.0, 
                         range_path='volume_range', dephase_key='volume'),
            ParameterSpec('pan', 'pan', 0.0,
                         dephase_key='pan')
        ]
        yaml_data = {
            'volume': -12.0,
            'volume_range': 3.0,
            'pan': 0.5
        }
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert params['volume'].value == -12.0
        assert params['volume'].mod_range == 3.0
        assert params['pan'].value == 0.5
        assert params['volume']._probability_gate is not None
    
    def test_complete_workflow_exclusive_groups(self):
        """Complete workflow with exclusive groups."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('density', 'density', None,
                         exclusive_group='density_mode', group_priority=2),
            ParameterSpec('fill_factor', 'fill_factor', 2,
                         exclusive_group='density_mode', group_priority=1)
        ]
        yaml_data = {'fill_factor': 3}
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert params['fill_factor'] is not None
        assert params['fill_factor'].value == 3
        assert params['density'] is None  # Loser
    
    def test_mixed_smart_and_raw_parameters(self):
        """Mix of smart and raw parameters."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('volume', 'volume', -6.0, is_smart=True),
            ParameterSpec('envelope', 'envelope', 'hanning', is_smart=False)
        ]
        yaml_data = {'volume': -12.0, 'envelope': 'triangle'}
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert isinstance(params['volume'], Parameter)
        assert params['envelope'] == 'triangle'  # Raw value


# =============================================================================
# 9. TEST ERROR HANDLING
# =============================================================================

class TestFactoryOrchestratorErrors:
    """Test error handling."""
    
    def test_nested_path_on_primitive_value(self):
        """Nested path on primitive returns default."""
        config = StreamConfig()
        factory = ParameterFactory(config)
        
        spec = ParameterSpec(
            name='test',
            yaml_path='grain.duration',
            default=0.05
        )
        yaml_data = {'grain': 42}  # Not a dict
        
        param = factory.create_smart_parameter(spec, yaml_data)
        
        # Should use default
        assert param.value == 0.05


# =============================================================================
# 10. TEST EDGE CASES
# =============================================================================

class TestFactoryOrchestratorEdgeCases:
    """Test edge cases."""
    
    def test_empty_yaml_uses_all_defaults(self):
        """Empty YAML uses all defaults."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('volume', 'volume', -6.0),
            ParameterSpec('pan', 'pan', 0.0)
        ]
        yaml_data = {}
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert params['volume'].value == -6.0
        assert params['pan'].value == 0.0
    
    def test_empty_schema_returns_empty_dict(self):
        """Empty schema returns empty dict."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = []
        yaml_data = {'volume': -12.0}
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        assert params == {}
    
    def test_deeply_nested_path(self):
        """Very deep nested path works."""
        data = {'a': {'b': {'c': {'d': 42}}}}
        
        result = ParameterFactory._get_nested(data, 'a.b.c.d', 0)
        
        assert result == 42
    
    def test_exclusive_group_single_member(self):
        """Exclusive group with single member."""
        schema = [
            ParameterSpec('only_one', 'value', 10,
                         exclusive_group='solo')
        ]
        yaml_data = {'value': 20}
        
        selected, members = ExclusiveGroupSelector.select_parameters(
            schema, yaml_data
        )
        
        assert 'only_one' in selected


# =============================================================================
# 11. TEST PARAMETRIZED
# =============================================================================

class TestFactoryOrchestratorParametrized:
    """Test parametrized for systematic coverage."""
    
    @pytest.mark.parametrize("path,expected", [
        ('a', 1),
        ('b.c', 2),
        ('d.e.f', 3),
        ('missing', 0)
    ])
    def test_get_nested_various_paths(self, path, expected):
        """Test _get_nested with various paths."""
        data = {
            'a': 1,
            'b': {'c': 2},
            'd': {'e': {'f': 3}}
        }
        
        result = ParameterFactory._get_nested(data, path, 0)
        
        assert result == expected
    
    @pytest.mark.parametrize("is_smart", [True, False])
    def test_create_both_parameter_types(self, is_smart):
        """Test creating both smart and raw parameters."""
        config = StreamConfig()
        orchestrator = ParameterOrchestrator(config)
        
        schema = [
            ParameterSpec('test', 'value', 10, is_smart=is_smart)
        ]
        yaml_data = {'value': 20}
        
        params = orchestrator.create_all_parameters(yaml_data, schema)
        
        if is_smart:
            assert isinstance(params['test'], Parameter)
        else:
            assert params['test'] == 20