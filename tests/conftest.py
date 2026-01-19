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

# =============================================================================
# FIXTURES POINTER CONTROLLER
# =============================================================================

@pytest.fixture
def sample_dur_sec():
    """Durata sample standard per test (10 secondi)."""
    return 10.0

@pytest.fixture
def pointer_factory(evaluator, sample_dur_sec):
    """
    Factory per creare PointerController con configurazioni custom.
    
    Usage:
        def test_something(pointer_factory):
            pointer = pointer_factory({'start': 1.0, 'speed': 2.0})
            # oppure con override:
            pointer = pointer_factory({'speed': 0.5}, sample_dur=5.0)
    """
    from pointer_controller import PointerController
    
    def _create(params: dict, sample_dur: float = None, eval_override = None):
        return PointerController(
            params=params,
            evaluator=eval_override or evaluator,
            sample_dur_sec=sample_dur or sample_dur_sec
        )
    
    return _create

@pytest.fixture
def pointer_basic(pointer_factory):
    """PointerController base: start=0, speed=1, no loop."""
    return pointer_factory({'start': 0.0, 'speed': 1.0})

@pytest.fixture
def pointer_with_loop(pointer_factory):
    """PointerController con loop fisso (2.0 - 4.0)."""
    return pointer_factory({
        'start': 0.0,
        'speed': 1.0,
        'loop_start': 2.0,
        'loop_end': 4.0
    })

# =============================================================================
# FIXTURES PITCH CONTROLLER
# =============================================================================

@pytest.fixture
def pitch_factory(evaluator):
    """
    Factory per creare PitchController con configurazioni custom.
    
    Usage:
        def test_something(pitch_factory):
            pitch = pitch_factory({'ratio': 2.0})
            # oppure con override:
            pitch = pitch_factory({'shift_semitones': 7}, eval_override=custom_eval)
    """
    from pitch_controller import PitchController
    
    def _create(params: dict, eval_override=None):
        return PitchController(
            params=params,
            evaluator=eval_override or evaluator
        )
    
    return _create


@pytest.fixture
def pitch_ratio_default(pitch_factory):
    """PitchController in modalità ratio con default (ratio=1.0)."""
    return pitch_factory({})


@pytest.fixture
def pitch_ratio_double(pitch_factory):
    """PitchController in modalità ratio con ratio=2.0 (ottava su)."""
    return pitch_factory({'ratio': 2.0})


@pytest.fixture
def pitch_semitones_fifth(pitch_factory):
    """PitchController in modalità semitoni: +7 semitoni (quinta giusta)."""
    return pitch_factory({'shift_semitones': 7})


@pytest.fixture
def pitch_semitones_envelope(pitch_factory):
    """PitchController con shift_semitones come envelope: 0 → 12 in 10s."""
    return pitch_factory({
        'shift_semitones': [[0, 0], [10, 12]]
    })


@pytest.fixture
def pitch_with_range(pitch_factory):
    """PitchController con range stocastico (ratio mode)."""
    return pitch_factory({
        'ratio': 1.0,
        'range': 0.5
    })


@pytest.fixture
def pitch_semitones_with_range(pitch_factory):
    """PitchController con range stocastico (semitones mode)."""
    return pitch_factory({
        'shift_semitones': 0,
        'range': 4  # ±2 semitoni
    })

# =============================================================================
# FIXTURES DENSITY CONTROLLER
# =============================================================================

from unittest.mock import Mock

@pytest.fixture
def mock_evaluator():
    """
    Mock di ParameterEvaluator configurato per i test.
    """
    evaluator = Mock(spec=ParameterEvaluator)
    
    # 1. PARSE: Lascia passare TUTTO
    def parse_side_effect(value, param_name):
        return value
    
    # 2. EVALUATE: Gestisce numeri, Envelope reali e Mock
    def evaluate_side_effect(value, elapsed_time, param_name):
        # Caso A: Envelope (reale o mockato che ha il metodo evaluate)
        if hasattr(value, 'evaluate'):
            val = float(value.evaluate(elapsed_time))
            
        # Caso B: Numero semplice (float, int)
        else:
            val = float(value)
            
        # Simulazione Clamping per effective_density
        if param_name == 'effective_density':
            return max(0.1, min(4000.0, val))
            
        return val
    
    evaluator.parse.side_effect = parse_side_effect
    evaluator.evaluate.side_effect = evaluate_side_effect
    
    return evaluator

@pytest.fixture
def density_factory(mock_evaluator):  # <--- CAMBIATO QUI: usa mock_evaluator
    """
    Factory per creare DensityController usando il MOCK evaluator.
    """
    from density_controller import DensityController
    
    def _create(params: dict):
        # Passiamo il mock, così accetta oggetti Mock nei parametri
        return DensityController(mock_evaluator, params)
    
    return _create

# Queste fixtures ora useranno indirettamente il mock_evaluator tramite la factory
@pytest.fixture
def density_fill_factor(density_factory):
    """DensityController standard in modalità fill_factor (2.0)."""
    return density_factory({'fill_factor': 2.0})

@pytest.fixture
def density_explicit(density_factory):
    """DensityController standard in modalità density (10.0)."""
    return density_factory({'density': 10.0})

# =============================================================================
# FIXTURES VOICE MANAGER
# =============================================================================

@pytest.fixture
def voice_manager_factory(mock_evaluator):
    """
    Factory per creare VoiceManager usando il MOCK evaluator.
    
    Usage:
        def test_something(voice_manager_factory):
            manager = voice_manager_factory({'number': 4, 'offset_pitch': 7})
    """
    from voice_manager import VoiceManager
    
    def _create(voices_params: dict, sample_dur: float = 10.0):
        return VoiceManager(
            evaluator=mock_evaluator,
            voices_params=voices_params,
            sample_dur_sec=sample_dur
        )
    
    return _create


@pytest.fixture
def voice_manager_single(voice_manager_factory):
    """VoiceManager con una sola voce (default)."""
    return voice_manager_factory({'number': 1})


@pytest.fixture
def voice_manager_four_voices(voice_manager_factory):
    """VoiceManager con 4 voci fisse e offset pitch di 7 semitoni."""
    return voice_manager_factory({
        'number': 4,
        'offset_pitch': 7.0,
        'pointer_offset': 0.5
    })