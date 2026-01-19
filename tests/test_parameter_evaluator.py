"""
Test per ParameterEvaluator

Esegui con: python test_parameter_evaluator.py
"""

import sys
import random

# =============================================================================
# MOCK delle dipendenze (per test standalone)
# =============================================================================

class MockEnvelope:
    """Mock minimale di Envelope per testing"""
    def __init__(self, breakpoints):
        if isinstance(breakpoints, dict):
            self.breakpoints = sorted(breakpoints['points'], key=lambda x: x[0])
            self.type = breakpoints.get('type', 'linear')
        else:
            self.breakpoints = sorted(breakpoints, key=lambda x: x[0])
            self.type = 'linear'
    
    def evaluate(self, time):
        if len(self.breakpoints) == 1:
            return self.breakpoints[0][1]
        
        if time <= self.breakpoints[0][0]:
            return self.breakpoints[0][1]
        if time >= self.breakpoints[-1][0]:
            return self.breakpoints[-1][1]
        
        for i in range(len(self.breakpoints) - 1):
            t1, v1 = self.breakpoints[i]
            t2, v2 = self.breakpoints[i + 1]
            if t1 <= time < t2:
                t_norm = (time - t1) / (t2 - t1)
                return v1 + (v2 - v1) * t_norm
        
        return self.breakpoints[-1][1]
    
    def __repr__(self):
        return f"Envelope(type={self.type}, points={self.breakpoints})"


# Mock del logger
def mock_log_clip_warning(stream_id, param_name, time, value, clamped, min_val, max_val, is_envelope):
    print(f"  ⚠️  CLIP [{stream_id}] {param_name} @ t={time:.3f}: {value:.4f} → {clamped:.4f} (bounds: {min_val}, {max_val})")


# Inject mocks nel namespace prima di importare
sys.modules['envelope'] = type(sys)('envelope')
sys.modules['envelope'].Envelope = MockEnvelope

sys.modules['logger'] = type(sys)('logger')
sys.modules['logger'].log_clip_warning = mock_log_clip_warning

# Ora possiamo importare
from src.parameter_evaluator import ParameterEvaluator, ParameterBounds


# =============================================================================
# TEST
# =============================================================================

def test_parse_number():
    """Test: parsing di numeri semplici"""
    print("\n📝 Test: parse numeri")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    result = evaluator.parse(50, "density")
    assert result == 50, f"Expected 50, got {result}"
    print(f"  ✓ parse(50) → {result}")
    
    result = evaluator.parse(3.14, "some_param")
    assert result == 3.14, f"Expected 3.14, got {result}"
    print(f"  ✓ parse(3.14) → {result}")


def test_parse_list_envelope():
    """Test: parsing di envelope da lista"""
    print("\n📝 Test: parse lista → Envelope")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    result = evaluator.parse([[0, 20], [5, 100], [10, 50]], "density")
    assert isinstance(result, MockEnvelope), f"Expected Envelope, got {type(result)}"
    print(f"  ✓ parse([[0,20], [5,100], [10,50]]) → {result}")
    
    # Verifica valutazione
    val = result.evaluate(2.5)
    expected = 20 + (100 - 20) * (2.5 / 5)  # interpolazione lineare
    assert abs(val - expected) < 0.001, f"Expected ~{expected}, got {val}"
    print(f"  ✓ evaluate(2.5) → {val:.2f} (expected ~{expected:.2f})")


def test_parse_dict_envelope():
    """Test: parsing di envelope da dict"""
    print("\n📝 Test: parse dict → Envelope")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    result = evaluator.parse({
        'type': 'cubic',
        'points': [[0, 0], [5, 100], [10, 0]]
    }, "volume")
    
    assert isinstance(result, MockEnvelope), f"Expected Envelope, got {type(result)}"
    assert result.type == 'cubic'
    print(f"  ✓ parse(dict con type='cubic') → {result}")


def test_parse_normalized_time():
    """Test: normalizzazione temporale"""
    print("\n📝 Test: time_mode='normalized'")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0, time_mode='normalized')
    
    # Con time_mode normalized, [0, 1] diventa [0, 10]
    result = evaluator.parse([[0, 20], [1, 100]], "density")
    
    # Verifica che i tempi siano stati scalati
    assert result.breakpoints[0][0] == 0.0
    assert result.breakpoints[1][0] == 10.0  # 1 * 10
    print(f"  ✓ [[0,20], [1,100]] con duration=10 → breakpoints tempi: {[bp[0] for bp in result.breakpoints]}")


def test_evaluate_basic():
    """Test: valutazione con bounds"""
    print("\n📝 Test: evaluate con bounds")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    # Valore dentro i bounds
    result = evaluator.evaluate(500, time=0, param_name='density')
    assert result == 500
    print(f"  ✓ evaluate(500, 'density') → {result} (dentro bounds)")
    
    # Valore sotto il minimo (dovrebbe clippare a 0.1)
    print("  Testing valore sotto minimo...")
    result = evaluator.evaluate(0.01, time=0, param_name='density')
    assert result == 0.1, f"Expected 0.1 (min), got {result}"
    print(f"  ✓ evaluate(0.01, 'density') → {result} (clipped to min)")
    
    # Valore sopra il massimo (dovrebbe clippare a 4000)
    print("  Testing valore sopra massimo...")
    result = evaluator.evaluate(10000, time=0, param_name='density')
    assert result == 4000, f"Expected 4000 (max), got {result}"
    print(f"  ✓ evaluate(10000, 'density') → {result} (clipped to max)")


def test_evaluate_envelope():
    """Test: valutazione di Envelope"""
    print("\n📝 Test: evaluate Envelope")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    # Crea envelope
    env = evaluator.parse([[0, 50], [10, 200]], "density")
    
    # Valuta a vari tempi
    val_0 = evaluator.evaluate(env, time=0, param_name='density')
    val_5 = evaluator.evaluate(env, time=5, param_name='density')
    val_10 = evaluator.evaluate(env, time=10, param_name='density')
    
    print(f"  ✓ t=0:  {val_0}")
    print(f"  ✓ t=5:  {val_5}")
    print(f"  ✓ t=10: {val_10}")
    
    assert val_0 == 50
    assert val_5 == 125  # interpolazione lineare
    assert val_10 == 200


def test_evaluate_with_range():
    """Test: valutazione con range stocastico"""
    print("\n📝 Test: evaluate_with_range")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    # Fissa il seed per riproducibilità
    random.seed(42)
    
    # Base = -6 dB, range = 6 dB → risultato in [-9, -3]
    results = []
    for _ in range(100):
        val = evaluator.evaluate_with_range(
            param=-6.0,
            param_range=6.0,
            time=0,
            param_name='volume'
        )
        results.append(val)
        assert -9.0 <= val <= -3.0, f"Value {val} out of expected range [-9, -3]"
    
    avg = sum(results) / len(results)
    print(f"  ✓ 100 samples con base=-6, range=6:")
    print(f"    min={min(results):.2f}, max={max(results):.2f}, avg={avg:.2f}")


def test_evaluate_scaled():
    """Test: valutazione con bounds scalati"""
    print("\n📝 Test: evaluate_scaled")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    # voice_pointer_offset ha bounds [0, 1], scala per sample_duration=5 sec
    result = evaluator.evaluate_scaled(
        param=0.5,  # 50%
        time=0,
        param_name='voice_pointer_offset',
        scale=5.0  # sample duration
    )
    
    # 0.5 * 1 (max bounds) = 0.5, ma con scale=5, max diventa 5
    # Quindi 0.5 dovrebbe restare 0.5 (dentro [0, 5])
    assert result == 0.5
    print(f"  ✓ evaluate_scaled(0.5, scale=5.0) → {result}")
    
    # Test con valore che eccede il bound scalato
    print("  Testing valore oltre bound scalato...")
    result = evaluator.evaluate_scaled(
        param=10.0,  # oltre il max scalato (5.0)
        time=0,
        param_name='voice_pointer_offset',
        scale=5.0
    )
    assert result == 5.0, f"Expected 5.0 (scaled max), got {result}"
    print(f"  ✓ evaluate_scaled(10.0, scale=5.0) → {result} (clipped)")


def test_unknown_param():
    """Test: errore per parametro senza bounds"""
    print("\n📝 Test: errore parametro sconosciuto")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    try:
        evaluator.evaluate(100, time=0, param_name='parametro_inventato')
        assert False, "Doveva sollevare ValueError"
    except ValueError as e:
        print(f"  ✓ ValueError sollevato correttamente: {e}")


def test_bounds_inspection():
    """Test: ispezione bounds"""
    print("\n📝 Test: get_bounds")
    
    evaluator = ParameterEvaluator("test_stream", duration=10.0)
    
    bounds = evaluator.get_bounds('volume')
    assert bounds is not None
    assert bounds.min_val == -120.0
    assert bounds.max_val == 12.0
    print(f"  ✓ get_bounds('volume') → min={bounds.min_val}, max={bounds.max_val}")
    
    bounds = evaluator.get_bounds('non_esiste')
    assert bounds is None
    print(f"  ✓ get_bounds('non_esiste') → None")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST ParameterEvaluator")
    print("=" * 60)
    
    test_parse_number()
    test_parse_list_envelope()
    test_parse_dict_envelope()
    test_parse_normalized_time()
    test_evaluate_basic()
    test_evaluate_envelope()
    test_evaluate_with_range()
    test_evaluate_scaled()
    test_unknown_param()
    test_bounds_inspection()
    
    print("\n" + "=" * 60)
    print("✅ TUTTI I TEST PASSATI!")
    print("=" * 60)