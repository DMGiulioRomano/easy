# tests/conftest.py
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import random
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


@pytest.fixture
def mock_evaluator():
    """
    Mock di ParameterEvaluator configurato per i test.
    Aggiornato per supportare evaluate_gated_stochastic.
    """
    from parameter_evaluator import ParameterBounds, ParameterEvaluator # Assicurati dell'import
    
    evaluator = Mock(spec=ParameterEvaluator)
    
    # 1. PARSE: Lascia passare TUTTO
    def parse_side_effect(value, param_name):
        return value
    
    # 2. EVALUATE: Gestisce numeri, Envelope reali e Mock
    def evaluate_side_effect(value, elapsed_time, param_name):
        if hasattr(value, 'evaluate'):
            val = float(value.evaluate(elapsed_time))
        else:
            val = float(value)
            
        if param_name == 'effective_density':
            return max(0.1, min(4000.0, val))
            
        return val
    
    # 3. EVALUATE_GATED_STOCHASTIC (Nuovo!)
    # Per i test con il mock, ignoriamo la stocasticità e ritorniamo il valore base.
    # Questo garantisce determinismo nei test dei controller.
    def evaluate_gated_stochastic_side_effect(base_param, range_param, prob_param, default_jitter, time, param_name):
        return evaluate_side_effect(base_param, time, param_name)
    
    # 4. GET_BOUNDS: Restituisce bounds realistici
    def get_bounds_side_effect(param_name):
        default_bounds = {
            'num_voices': ParameterBounds(1.0, 20.0),
            'voice_pitch_offset': ParameterBounds(-48.0, 48.0),
            'voice_pointer_offset': ParameterBounds(0.0, 1.0),
            'voice_pointer_range': ParameterBounds(0.0, 1.0),
            'density': ParameterBounds(0.1, 4000.0),
            'effective_density': ParameterBounds(0.1, 4000.0),
            # Aggiungi bounds se servono per altri test specifici col mock
        }
        return default_bounds.get(param_name)
    
    # Assegnazione side effects
    evaluator.parse.side_effect = parse_side_effect
    evaluator.evaluate.side_effect = evaluate_side_effect
    evaluator.get_bounds.side_effect = get_bounds_side_effect
    
    # Sostituiamo il vecchio evaluate_with_range con il nuovo metodo
    evaluator.evaluate_gated_stochastic.side_effect = evaluate_gated_stochastic_side_effect
    
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

# =============================================================================
# FIXTURES STREAM (Orchestratore)
# =============================================================================

@pytest.fixture
def mock_sample_duration():
    """Mock per get_sample_duration che ritorna sempre 10.0 secondi."""
    with patch('stream.get_sample_duration', return_value=10.0):
        yield


@pytest.fixture
def stream_params_minimal():
    """Parametri minimi per creare uno Stream valido."""
    return {
        'stream_id': 'test_stream',
        'onset': 0.0,
        'duration': 5.0,
        'sample': 'test.wav',
        'grain': {
            'duration': 0.05,
            'envelope': 'hanning'
        }
    }


@pytest.fixture
def stream_params_full():
    """Parametri completi per creare uno Stream con tutte le feature."""
    return {
        'stream_id': 'full_test_stream',
        'onset': 1.0,
        'duration': 10.0,
        'sample': 'test.wav',
        'time_mode': 'absolute',
        
        # Grain
        'grain': {
            'duration': 0.05,
            'duration_range': 0.01,
            'envelope': 'hanning',
            'reverse': 'auto'
        },
        
        # Pointer
        'pointer': {
            'start': 0.0,
            'speed': 1.0,
            'jitter': 0.01
        },
        
        # Pitch
        'pitch': {
            'ratio': 1.0,
            'range': 0.1
        },
        
        # Density
        'fill_factor': 2.0,
        'distribution': 0.0,
        
        # Voices
        'voices': {
            'number': 2,
            'offset_pitch': 7.0,
            'pointer_offset': 0.1
        },
        
        # Output
        'volume': -6.0,
        'volume_range': 3.0,
        'pan': 0.0,
        'pan_range': 30.0
    }


@pytest.fixture
def stream_params_with_envelopes():
    """Parametri con envelope per test dinamici."""
    return {
        'stream_id': 'envelope_test_stream',
        'onset': 0.0,
        'duration': 10.0,
        'sample': 'test.wav',
        
        # Grain con envelope
        'grain': {
            'duration': [[0, 0.05], [10, 0.1]],  # 50ms → 100ms
            'envelope': 'hanning'
        },
        
        # Pointer con envelope
        'pointer': {
            'start': 0.0,
            'speed': [[0, 1.0], [10, 2.0]]  # 1x → 2x
        },
        
        # Density con envelope
        'density': [[0, 10], [10, 50]],  # 10 → 50 g/s
        
        # Voices con envelope
        'voices': {
            'number': [[0, 1], [5, 4], [10, 1]]  # 1 → 4 → 1
        },
        
        # Volume con envelope
        'volume': [[0, -12], [5, -3], [10, -12]]  # fade in/out
    }


@pytest.fixture
def stream_factory(mock_sample_duration):
    """
    Factory per creare Stream con configurazioni custom.
    Usa il mock della durata sample per evitare I/O su file.
    
    Usage:
        def test_something(stream_factory):
            stream = stream_factory({'stream_id': 'test', ...})
    """
    from stream import Stream
    
    def _create(params: dict):
        return Stream(params)
    
    return _create


@pytest.fixture
def stream_minimal(stream_factory, stream_params_minimal):
    """Stream con configurazione minima."""
    return stream_factory(stream_params_minimal)


@pytest.fixture
def stream_full(stream_factory, stream_params_full):
    """Stream con configurazione completa."""
    return stream_factory(stream_params_full)


@pytest.fixture
def stream_with_envelopes(stream_factory, stream_params_with_envelopes):
    """Stream con envelope sui parametri principali."""
    return stream_factory(stream_params_with_envelopes)


# =============================================================================
# FIXTURES PER DETERMINISMO
# =============================================================================

@pytest.fixture
def fixed_seed():
    """Fissa il seed random per test deterministici."""
    random.seed(42)
    yield
    # Non resetta il seed, i test successivi avranno seed diversi
    # se non usano questa fixture


@pytest.fixture
def deterministic_random(monkeypatch):
    """
    Fixture che rende random.uniform e random.randint deterministici.
    Utile per test che verificano valori esatti.
    """
    # Sempre al centro del range
    monkeypatch.setattr(random, "uniform", lambda a, b: (a + b) / 2)
    monkeypatch.setattr(random, "randint", lambda a, b: (a + b) // 2)


# TEMPORARY FIXTURE FOR TEMPORARY GENERATOR

@pytest.fixture
def yaml_content_minimal():
    """Contenuto YAML minimo per testare il generatore."""
    return """
streams:
  - stream_id: stream_1
    onset: 0.0
    duration: 5.0
    sample: "test.wav"
    grain:
      duration: 0.1
      envelope: hanning
"""

@pytest.fixture
def yaml_file(tmp_path, yaml_content_minimal):
    """Crea un file YAML reale su disco in una directory temporanea."""
    p = tmp_path / "test_score.yaml"
    p.write_text(yaml_content_minimal)
    return str(p)

@pytest.fixture
def generator(yaml_file):
    """Istanza di Generator collegata al file YAML temporaneo."""
    from generator import Generator
    return Generator(yaml_file)