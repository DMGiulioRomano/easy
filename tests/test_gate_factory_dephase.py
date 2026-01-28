"""
test_gate_factory_dephase.py

Test suite completa per la nuova logica dephase in GateFactory.
Copre tutti i DephaseMode e le combinazioni con range_always_active.
"""

import pytest
from gate_factory import GateFactory, DephaseMode
from probability_gate import NeverGate, AlwaysGate, RandomGate, EnvelopeGate
from parameter_definitions import IMPLICIT_JITTER_PROB


class TestDephaseClassification:
    """Test per _classify_dephase"""
    
    def test_classify_false(self):
        assert GateFactory._classify_dephase(False) == DephaseMode.DISABLED
    
    def test_classify_none(self):
        assert GateFactory._classify_dephase(None) == DephaseMode.IMPLICIT
    
    def test_classify_int(self):
        assert GateFactory._classify_dephase(50) == DephaseMode.GLOBAL
    
    def test_classify_float(self):
        assert GateFactory._classify_dephase(33.5) == DephaseMode.GLOBAL
    
    def test_classify_dict(self):
        assert GateFactory._classify_dephase({'pc_rand_volume': 100}) == DephaseMode.SPECIFIC
    
    def test_classify_invalid_type(self):
        with pytest.raises(ValueError, match="dephase tipo invalido"):
            GateFactory._classify_dephase("invalid")


class TestParameterWithoutDephaseKey:
    """Parametri senza dephase_key → sempre NeverGate"""
    
    def test_no_dephase_key_returns_never_gate(self):
        gate = GateFactory.create_gate(
            dephase=None,
            param_key=None,  # ← parametro non supporta dephase
            default_prob=IMPLICIT_JITTER_PROB
        )
        assert isinstance(gate, NeverGate)


class TestRangeAlwaysActive:
    """range_always_active=True bypassa tutto per range espliciti"""
    
    def test_bypasses_disabled(self):
        gate = GateFactory.create_gate(
            dephase=False,
            param_key='pc_rand_volume',
            has_explicit_range=True,
            range_always_active=True
        )
        assert isinstance(gate, AlwaysGate)
    
    def test_bypasses_global_prob(self):
        gate = GateFactory.create_gate(
            dephase=10,  # ← dovrebbe dare 10%, ma viene bypassato
            param_key='pc_rand_volume',
            has_explicit_range=True,
            range_always_active=True
        )
        assert isinstance(gate, AlwaysGate)
    
    def test_bypasses_specific_prob(self):
        gate = GateFactory.create_gate(
            dephase={'pc_rand_volume': 5},
            param_key='pc_rand_volume',
            has_explicit_range=True,
            range_always_active=True
        )
        assert isinstance(gate, AlwaysGate)


class TestDephaseDisabled:
    """dephase=False: range espliciti 100%, altri 0%"""
    
    def test_with_explicit_range_returns_always(self):
        gate = GateFactory.create_gate(
            dephase=False,
            param_key='pc_rand_volume',
            has_explicit_range=True,
            range_always_active=False
        )
        assert isinstance(gate, AlwaysGate)
    
    def test_without_explicit_range_returns_never(self):
        gate = GateFactory.create_gate(
            dephase=False,
            param_key='pc_rand_volume',
            has_explicit_range=False
        )
        assert isinstance(gate, NeverGate)


class TestDephaseImplicit:
    """dephase=None: usa IMPLICIT_JITTER_PROB per tutti"""
    
    def test_uses_default_prob(self):
        gate = GateFactory.create_gate(
            dephase=None,
            param_key='pc_rand_volume',
            default_prob=IMPLICIT_JITTER_PROB,
            has_explicit_range=False
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == IMPLICIT_JITTER_PROB
    
    def test_with_explicit_range_also_uses_default_prob(self):
        """Range esplicito non forza 100% quando dephase=None"""
        gate = GateFactory.create_gate(
            dephase=None,
            param_key='pc_rand_volume',
            default_prob=IMPLICIT_JITTER_PROB,
            has_explicit_range=True,
            range_always_active=False
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == IMPLICIT_JITTER_PROB


class TestDephaseGlobal:
    """dephase=<numero>: probabilità globale per tutti"""
    
    def test_global_prob_50(self):
        gate = GateFactory.create_gate(
            dephase=50,
            param_key='pc_rand_volume',
            has_explicit_range=False
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == 50.0
    
    def test_global_prob_applies_to_explicit_range(self):
        """Range esplicito segue la probabilità globale"""
        gate = GateFactory.create_gate(
            dephase=25,
            param_key='pc_rand_volume',
            has_explicit_range=True,
            range_always_active=False
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == 25.0
    
    def test_global_prob_zero_returns_never(self):
        gate = GateFactory.create_gate(
            dephase=0,
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, NeverGate)
    
    def test_global_prob_hundred_returns_always(self):
        gate = GateFactory.create_gate(
            dephase=100,
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, AlwaysGate)
    
    def test_global_prob_negative_returns_never(self):
        gate = GateFactory.create_gate(
            dephase=-10,
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, NeverGate)
    
    def test_global_prob_over_hundred_returns_always(self):
        gate = GateFactory.create_gate(
            dephase=150,
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, AlwaysGate)


class TestDephaseSpecific:
    """dephase={dict}: probabilità per chiave specifica"""
    
    def test_key_with_explicit_value(self):
        gate = GateFactory.create_gate(
            dephase={'pc_rand_volume': 75},
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == 75.0
    
    def test_key_with_none_value_uses_implicit_jitter(self):
        """Chiave presente ma vuota → IMPLICIT_JITTER_PROB"""
        gate = GateFactory.create_gate(
            dephase={'pc_rand_volume': None},
            param_key='pc_rand_volume',
            default_prob=IMPLICIT_JITTER_PROB
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == IMPLICIT_JITTER_PROB
    
    def test_key_not_mentioned_uses_implicit_jitter(self):
        """Chiave non menzionata → IMPLICIT_JITTER_PROB"""
        gate = GateFactory.create_gate(
            dephase={'pc_rand_pan': 100},  # ← solo pan
            param_key='pc_rand_volume',    # ← chiediamo volume
            default_prob=IMPLICIT_JITTER_PROB
        )
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == IMPLICIT_JITTER_PROB
    
    def test_multiple_keys_independent(self):
        """Ogni chiave è indipendente"""
        dephase_config = {
            'pc_rand_volume': 100,
            'pc_rand_pan': 0,
            'pc_rand_duration': 50
        }
        
        gate_vol = GateFactory.create_gate(
            dephase=dephase_config,
            param_key='pc_rand_volume'
        )
        gate_pan = GateFactory.create_gate(
            dephase=dephase_config,
            param_key='pc_rand_pan'
        )
        gate_dur = GateFactory.create_gate(
            dephase=dephase_config,
            param_key='pc_rand_duration'
        )
        
        assert isinstance(gate_vol, AlwaysGate)
        assert isinstance(gate_pan, NeverGate)
        assert isinstance(gate_dur, RandomGate)
        assert gate_dur.get_probability_value(0.0) == 50.0


class TestEnvelopeSupport:
    """Test per envelope come valore di probabilità"""
    
    def test_envelope_as_dict(self):
        gate = GateFactory.create_gate(
            dephase={'pc_rand_volume': {'points': [[0, 0], [1, 100]]}},
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, EnvelopeGate)
    
    def test_envelope_as_list(self):
        gate = GateFactory.create_gate(
            dephase={'pc_rand_volume': [[0, 20], [1, 80]]},
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, EnvelopeGate)
    
    def test_invalid_envelope_fallback_to_always(self):
        """Envelope invalido → AlwaysGate con warning"""
        gate = GateFactory.create_gate(
            dephase={'pc_rand_volume': {'invalid': 'envelope'}},
            param_key='pc_rand_volume'
        )
        assert isinstance(gate, AlwaysGate)


class TestHelperMethods:
    """Test per metodi helper"""
    
    def test_create_probability_gate_zero(self):
        gate = GateFactory._create_probability_gate(0)
        assert isinstance(gate, NeverGate)
    
    def test_create_probability_gate_negative(self):
        gate = GateFactory._create_probability_gate(-5)
        assert isinstance(gate, NeverGate)
    
    def test_create_probability_gate_hundred(self):
        gate = GateFactory._create_probability_gate(100)
        assert isinstance(gate, AlwaysGate)
    
    def test_create_probability_gate_over_hundred(self):
        gate = GateFactory._create_probability_gate(150)
        assert isinstance(gate, AlwaysGate)
    
    def test_create_probability_gate_random(self):
        gate = GateFactory._create_probability_gate(42.5)
        assert isinstance(gate, RandomGate)
        assert gate.get_probability_value(0.0) == 42.5