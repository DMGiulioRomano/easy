import pytest
from envelope import Envelope
from parameter_evaluator import ParameterEvaluator, ParameterBounds

# =============================================================================
# 1. TEST PARSING (Conversione input -> dati utilizzabili)
# =============================================================================

def test_parse_scalar(evaluator):
    """Un numero semplice deve rimanere un numero."""
    result = evaluator.parse(42.5, "test_param")
    assert result == 42.5

def test_parse_list_creates_envelope(evaluator):
    """Una lista di liste deve diventare un oggetto Envelope."""
    data = [[0, 0], [1, 100]]
    result = evaluator.parse(data, "test_param")
    
    assert isinstance(result, Envelope)
    assert result.type == 'linear'
    assert result.evaluate(1) == 100

def test_parse_dict_creates_typed_envelope(evaluator):
    """Un dict deve creare un Envelope con il tipo specificato."""
    data = {'type': 'step', 'points': [[0, 10], [5, 50]]}
    result = evaluator.parse(data, "test_param")
    
    assert isinstance(result, Envelope)
    assert result.type == 'step'
    # Test comportamento step (valore sinistro)
    assert result.evaluate(4.9) == 10
    assert result.evaluate(5.0) == 50

def test_parse_invalid_format_raises_error(evaluator):
    """Input stringa non parsabile (senza eval math) deve alzare errore."""
    with pytest.raises(ValueError):
        evaluator.parse("non_un_numero", "bad_param")

# =============================================================================
# 2. TEST NORMALIZZAZIONE TEMPORALE
# =============================================================================

def test_normalized_time_mode():
    """
    Se time_mode='normalized' e duration=10.0:
    Un punto a t=0.5 deve diventare t=5.0
    """
    eval_norm = ParameterEvaluator("test", duration=10.0, time_mode='normalized')
    
    # Input: Envelope che finisce a 1.0 (cioè 100% durata)
    data = [[0.0, 0], [0.5, 50], [1.0, 100]]
    
    env = eval_norm.parse(data, "param")
    
    # Verifica i breakpoints scalati
    # env.breakpoints è [[time, val], ...]
    assert env.breakpoints[1][0] == 5.0  # 0.5 * 10.0
    assert env.breakpoints[2][0] == 10.0 # 1.0 * 10.0

def test_local_normalization_override(evaluator):
    """Un parametro può specificare 'normalized' nel dict anche se l'evaluator è absolute."""
    # Evaluator è 'absolute' di default (dalla fixture in conftest)
    data = {
        'time_unit': 'normalized',  # Override locale
        'points': [[0.5, 100]]
    }
    # La fixture 'evaluator' ha duration=10.0 (vedi conftest.py)
    env = evaluator.parse(data, "param")
    
    assert env.breakpoints[0][0] == 5.0

# =============================================================================
# 3. TEST BOUNDS & CLIPPING (Sicurezza)
# =============================================================================

def test_evaluate_respects_min_bound(evaluator):
    """Density non può essere < 0.1"""
    # Bound definito nel codice: 'density': ParameterBounds(0.1, 4000.0, ...)
    
    # Tentiamo di passare 0.0
    val = evaluator.evaluate(0.0, time=0, param_name='density')
    
    assert val == 0.1  # Deve essere clippato al minimo

def test_evaluate_respects_max_bound(evaluator):
    """Density non può essere > 4000.0"""
    # Tentiamo di passare 10000
    val = evaluator.evaluate(10000, time=0, param_name='density')
    
    assert val == 4000.0

def test_evaluate_envelope_clipping(evaluator):
    """Anche i valori che escono da un Envelope devono essere clippati."""
    # Envelope che va a -100 (illegale per density)
    env = Envelope([[0, -100], [10, -100]])
    
    val = evaluator.evaluate(env, time=5, param_name='density')
    assert val == 0.1

def test_missing_bounds_raises_error(evaluator):
    """Se chiediamo un parametro non mappato in BOUNDS, deve esplodere."""
    with pytest.raises(ValueError) as excinfo:
        evaluator.evaluate(10, 0, "parametro_inventato_inesistente")
    assert "Bounds non definiti" in str(excinfo.value)

# =============================================================================
# 4. TEST RANGE E RANDOM (Stocastico)
# =============================================================================

def test_evaluate_with_range_logic(evaluator, monkeypatch):
    """
    Testa evaluate_with_range mockando random.uniform.
    Formula: base + random(-0.5, 0.5) * range
    """
    import random
    
    # 1. Mockiamo random.uniform per restituire sempre il valore massimo (0.5)
    # Questo ci permette di testare la matematica deterministicamente
    monkeypatch.setattr(random, "uniform", lambda a, b: 0.5)
    
    # Parametro: pan (Min -3600, Max 3600)
    # Base: 0
    # Range: 100
    # Expected: 0 + (0.5 * 100) = 50
    val = evaluator.evaluate_with_range(
        param=0, 
        param_range=100, 
        time=0, 
        param_name='pan'
    )
    assert val == 50.0

def test_evaluate_with_range_clipping(evaluator, monkeypatch):
    """
    Se la variazione random spinge il valore fuori dai limiti,
    deve essere clippato.
    """
    import random
    monkeypatch.setattr(random, "uniform", lambda a, b: 0.5) # Max deviation positiva
    
    # Density: Max 4000
    # Base: 3950
    # Range: 200 (Deviazione max = +100)
    # Calcolo teorico: 3950 + 100 = 4050
    # Expected: 4000 (clippato)
    
    val = evaluator.evaluate_with_range(3950, 200, 0, 'density')
    assert val == 4000.0

# =============================================================================
# 5. TEST PARAMETRI SCALATI
# =============================================================================

def test_evaluate_scaled(evaluator):
    """
    Testa parametri che dipendono dalla durata del sample (es. loop_dur).
    """
    # 'loop_dur' ha bounds min=0.001, max=100.0 (default placeholder)
    # Se passiamo scale=0.5 (es. sample dura 0.5s), il max deve diventare 50.0 o 0.5?
    # Rivedendo il codice di ParameterEvaluator:
    # scaled_max = bounds.max_val * scale
    
    # Prendiamo 'voice_pointer_offset': bounds 0.0 -> 1.0
    # Se il sample dura 10s (scale=10), il max diventa 10.0
    
    val = evaluator.evaluate_scaled(
        param=5.0,     # Valore input
        time=0,
        param_name='voice_pointer_offset',
        scale=10.0     # Moltiplicatore bounds
    )
    
    # Min bound (0.0 * 10) = 0
    # Max bound (1.0 * 10) = 10
    # Input 5.0 è valido
    assert val == 5.0
    
    # Test clipping scalato
    val_overflow = evaluator.evaluate_scaled(
        param=15.0,    # Fuori dal limite scalato (10.0)
        time=0,
        param_name='voice_pointer_offset',
        scale=10.0
    )
    assert val_overflow == 10.0

# Aggiungi in coda a tests/test_parameter_evaluator.py

def test_evaluate_with_envelope_as_range(evaluator, monkeypatch):
    """
    FEATURE CRITICA: Il range di randomizzazione è esso stesso un Envelope.
    Esempio: All'inizio (t=0) jitter=0. Alla fine (t=10) jitter=100.
    """
    import random
    # Mockiamo random per restituire sempre +0.5 (deviazione massima positiva)
    monkeypatch.setattr(random, "uniform", lambda a, b: 0.5)
    
    # Parametro base fisso a 0
    # Range dinamico: Envelope che va da 0 a 100 in 10s
    range_env = Envelope([[0, 0], [10, 100]])
    
    # T=0: Range è 0. Deviazione = 0.5 * 0 = 0. Risultato 0.
    val_0 = evaluator.evaluate_with_range(0, range_env, time=0, param_name='pan')
    assert val_0 == 0.0
    
    # T=5: Range è 50. Deviazione = 0.5 * 50 = 25. Risultato 25.
    val_5 = evaluator.evaluate_with_range(0, range_env, time=5, param_name='pan')
    assert val_5 == 25.0
    
    # T=10: Range è 100. Deviazione = 0.5 * 100 = 50. Risultato 50.
    val_10 = evaluator.evaluate_with_range(0, range_env, time=10, param_name='pan')
    assert val_10 == 50.0