# tests/conftest.py
import pytest
import sys
from pathlib import Path

# Aggiunge la root del progetto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importiamo le classi per poter creare gli oggetti nelle fixtures
try:
    from envelope import Envelope
    from parameter_evaluator import ParameterEvaluator
except ImportError:
    pass  # Gestito dai test se fallisce

# =============================================================================
# MOCK AUDIO
# =============================================================================

@pytest.fixture
def mock_sample_duration(monkeypatch):
    """Restituisce sempre 10.0 secondi come durata sample."""
    def _mock_get_duration(filepath):
        return 10.0
    monkeypatch.setattr("stream.get_sample_duration", _mock_get_duration)
    return 10.0

# =============================================================================
# FIXTURES EVALUATOR
# =============================================================================

@pytest.fixture
def evaluator():
    return ParameterEvaluator(stream_id="test_stream", duration=10.0, time_mode='absolute')

# =============================================================================
# FIXTURES ENVELOPE (Dati e Oggetti)
# =============================================================================

@pytest.fixture
def env_linear():
    """
    Envelope lineare standard.
    Punti: [0, 0] -> [10, 100]
    Durata: 10s
    Valore: 0 -> 100
    """
    return Envelope([[0, 0], [10, 100]])

@pytest.fixture
def env_step():
    """
    Envelope a gradini (Step).
    0-5s:  valore 10
    5-10s: valore 50
    >10s:  valore 100
    """
    data = {'type': 'step', 'points': [[0, 10], [5, 50], [10, 100]]}
    return Envelope(data)

@pytest.fixture
def env_cubic():
    """
    Envelope cubico "difficile" (Plateau).
    Punti: [0,0] -> [1,10] -> [2,10] -> [3,0]
    Serve a testare che non ci sia overshoot tra 1 e 2.
    """
    data = {'type': 'cubic', 'points': [[0, 0], [1, 10], [2, 10], [3, 0]]}
    return Envelope(data)