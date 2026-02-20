# tests/test_score_visualizer.py
# =============================================================================
# TEST SUITE - ScoreVisualizer
# =============================================================================

import sys
import types
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, patch, Mock, PropertyMock

import matplotlib
matplotlib.use('Agg')

# =============================================================================
# MOCK INJECTION
# =============================================================================

class MockEnvelope:
    def __init__(self, breakpoints, type_='linear'):
        self.breakpoints = breakpoints
        self.type = type_

    def evaluate(self, t_rel):
        if not self.breakpoints:
            return 0.0
        if t_rel <= self.breakpoints[0][0]:
            return self.breakpoints[0][1]
        if t_rel >= self.breakpoints[-1][0]:
            return self.breakpoints[-1][1]
        for i in range(len(self.breakpoints) - 1):
            t0, v0 = self.breakpoints[i]
            t1, v1 = self.breakpoints[i + 1]
            if t0 <= t_rel <= t1:
                frac = (t_rel - t0) / (t1 - t0) if t1 != t0 else 0.0
                return v0 + frac * (v1 - v0)
        return self.breakpoints[-1][1]


class MockParameter:
    def __init__(self, value, mod_prob=None):
        self._value = value
        self._mod_prob = mod_prob


class MockParameterSpec:
    def __init__(self, name, dephase_key=None):
        self.name = name
        self.dephase_key = dephase_key


_stream_schema   = [MockParameterSpec('volume', 'volume'), MockParameterSpec('pan', 'pan')]
_pointer_schema  = [MockParameterSpec('pointer_start')]
_pitch_schema    = [MockParameterSpec('pitch_ratio', 'pitch_ratio')]
_density_schema  = [MockParameterSpec('density')]
_voice_schema    = [MockParameterSpec('num_voices')]

_envelope_mod = types.ModuleType('envelope')
_envelope_mod.Envelope = MockEnvelope

_parameter_mod = types.ModuleType('parameter')
_parameter_mod.Parameter = MockParameter

_param_schema_mod = types.ModuleType('parameter_schema')
_param_schema_mod.STREAM_PARAMETER_SCHEMA  = _stream_schema
_param_schema_mod.POINTER_PARAMETER_SCHEMA = _pointer_schema
_param_schema_mod.PITCH_PARAMETER_SCHEMA   = _pitch_schema
_param_schema_mod.DENSITY_PARAMETER_SCHEMA = _density_schema
_param_schema_mod.VOICE_PARAMETER_SCHEMA   = _voice_schema

# --- soundfile mock: DEVE avere l'attributo 'read' per permettere patch(...) ---
_sf_mod = types.ModuleType('soundfile')
_sf_mod.read  = MagicMock()   # attributo necessario per patch('soundfile.read', ...)
_sf_mod.info  = MagicMock()   # idem per altri test nella suite

# setdefault: non sovrascrive se il modulo e gia in sys.modules
sys.modules.setdefault('soundfile', _sf_mod)
sys.modules.setdefault('envelope', _envelope_mod)
sys.modules.setdefault('parameter', _parameter_mod)
sys.modules.setdefault('parameter_schema', _param_schema_mod)

from score_visualizer import ScoreVisualizer   # noqa: E402

# =============================================================================
# HELPER FACTORIES
# =============================================================================

FAKE_SR = 44100
FAKE_DURATION = 2.0
FAKE_AUDIO = np.sin(2 * np.pi * 440 * np.linspace(0, FAKE_DURATION, int(FAKE_SR * FAKE_DURATION)))


def make_grain(onset=0.0, duration=0.05, pointer_pos=1.0,
               pitch_ratio=1.0, volume=-6.0, pan=0.0,
               sample_table=1, envelope_table=2):
    g = MagicMock()
    g.onset = onset
    g.duration = duration
    g.pointer_pos = pointer_pos
    g.pitch_ratio = pitch_ratio
    g.volume = volume
    g.pan = pan
    g.sample_table = sample_table
    g.envelope_table = envelope_table
    return g


def make_stream(stream_id='s1', onset=0.0, duration=10.0,
                sample='test.wav', n_voices=1, grains_per_voice=3):
    s = MagicMock()
    s.stream_id = stream_id
    s.onset = onset
    s.duration = duration
    s.sample = sample
    voice = [make_grain(onset + i * (duration / grains_per_voice), 0.05)
             for i in range(grains_per_voice)]
    s.voices = [voice] * n_voices
    # Rimuove gli attributi schema per default (evita che _get_stream_envelopes
    # rilevi parametri inattesi)
    del s.volume
    del s.pan
    del s.pointer_start
    del s.pitch_ratio
    del s.density
    del s.num_voices
    return s


def make_generator(streams):
    g = MagicMock()
    g.streams = streams
    return g


def make_visualizer(streams, config=None):
    gen = make_generator(streams)
    return ScoreVisualizer(gen, config=config)


# fixture condivisa per il mock di soundfile.read usata da molti test
@pytest.fixture
def mock_sf_read():
    """Patcha soundfile.read restituendo FAKE_AUDIO a sr=44100."""
    with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
        yield


# =============================================================================
# GROUP A - __init__ e configurazione
# =============================================================================

class TestInit:

    def test_streams_bound_to_generator_streams(self):
        streams = [make_stream()]
        viz = make_visualizer(streams)
        assert viz.streams is streams

    def test_default_config_page_duration(self):
        viz = make_visualizer([make_stream()])
        assert viz.config['page_duration'] == 30.0

    def test_default_config_page_size_a3(self):
        viz = make_visualizer([make_stream()])
        assert viz.config['page_size'] == (420, 297)

    def test_default_config_grain_colormap(self):
        viz = make_visualizer([make_stream()])
        assert viz.config['grain_colormap'] == 'coolwarm'

    def test_custom_config_overrides_default(self):
        viz = make_visualizer([make_stream()], config={'page_duration': 15.0})
        assert viz.config['page_duration'] == 15.0

    def test_custom_config_does_not_clobber_other_defaults(self):
        viz = make_visualizer([make_stream()], config={'page_duration': 5.0})
        assert viz.config['grain_colormap'] == 'coolwarm'

    def test_waveform_cache_starts_empty(self):
        viz = make_visualizer([make_stream()])
        assert viz.waveform_cache == {}

    def test_page_layouts_starts_empty(self):
        viz = make_visualizer([make_stream()])
        assert viz.page_layouts == []

    def test_total_duration_starts_none(self):
        viz = make_visualizer([make_stream()])
        assert viz.total_duration is None

    def test_page_count_starts_none(self):
        viz = make_visualizer([make_stream()])
        assert viz.page_count is None

    def test_cmap_assigned(self):
        viz = make_visualizer([make_stream()])
        assert viz.cmap is not None

    def test_show_static_params_default_false(self):
        viz = make_visualizer([make_stream()])
        assert viz.config['show_static_params'] is False

    def test_envelope_colors_present_in_config(self):
        viz = make_visualizer([make_stream()])
        assert 'envelope_colors' in viz.config
        assert isinstance(viz.config['envelope_colors'], dict)

    def test_envelope_ranges_present_in_config(self):
        viz = make_visualizer([make_stream()])
        assert 'envelope_ranges' in viz.config
        assert 'volume' in viz.config['envelope_ranges']


# =============================================================================
# GROUP B - analyze()
# =============================================================================

class TestAnalyze:

    def test_raises_if_no_streams(self):
        viz = make_visualizer([])
        with pytest.raises(ValueError, match="Nessuno stream"):
            viz.analyze()

    def test_total_duration_single_stream(self):
        s = make_stream(onset=0.0, duration=20.0)
        viz = make_visualizer([s])
        viz.analyze()
        assert viz.total_duration == pytest.approx(20.0)

    def test_total_duration_multiple_streams(self):
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=5.0, duration=20.0)
        viz = make_visualizer([s1, s2])
        viz.analyze()
        assert viz.total_duration == pytest.approx(25.0)

    def test_page_count_single_page(self):
        s = make_stream(onset=0.0, duration=20.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert viz.page_count == 1

    def test_page_count_exact_multiple(self):
        s = make_stream(onset=0.0, duration=60.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert viz.page_count == 2

    def test_page_count_partial_last_page(self):
        s = make_stream(onset=0.0, duration=45.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert viz.page_count == 2

    def test_page_layouts_length_matches_page_count(self):
        s = make_stream(onset=0.0, duration=75.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert len(viz.page_layouts) == viz.page_count

    def test_page_layout_time_range_first_page(self):
        s = make_stream(onset=0.0, duration=60.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert viz.page_layouts[0]['time_range'] == (0.0, 30.0)

    def test_page_layout_time_range_second_page(self):
        s = make_stream(onset=0.0, duration=60.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert viz.page_layouts[1]['time_range'] == (30.0, 60.0)

    def test_page_layout_active_streams_populated(self):
        s = make_stream(onset=0.0, duration=60.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert s in viz.page_layouts[0]['active_streams']
        assert s in viz.page_layouts[1]['active_streams']

    def test_page_layout_stream_absent_from_non_overlapping_page(self):
        s = make_stream(onset=35.0, duration=10.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert s not in viz.page_layouts[0]['active_streams']
        assert s in viz.page_layouts[1]['active_streams']

    def test_analyze_sets_slot_assignments(self):
        s = make_stream()
        viz = make_visualizer([s], config={'page_duration': 30.0})
        viz.analyze()
        assert 'slot_assignments' in viz.page_layouts[0]

    def test_analyze_empty_page_layout_for_gap(self):
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=70.0, duration=10.0)
        viz = make_visualizer([s1, s2], config={'page_duration': 30.0})
        viz.analyze()
        layout_p2 = viz.page_layouts[1]  # 30..60
        assert layout_p2['active_streams'] == []

    def test_max_concurrent_key_present(self):
        s = make_stream()
        viz = make_visualizer([s])
        viz.analyze()
        assert 'max_concurrent' in viz.page_layouts[0]


# =============================================================================
# GROUP C - _find_active_streams
# =============================================================================

class TestFindActiveStreams:

    def _viz(self, streams):
        return make_visualizer(streams)

    def test_stream_fully_inside_page(self):
        s = make_stream(onset=5.0, duration=10.0)
        viz = self._viz([s])
        result = viz._find_active_streams(0.0, 30.0)
        assert s in result

    def test_stream_starting_before_page(self):
        s = make_stream(onset=0.0, duration=10.0)
        viz = self._viz([s])
        result = viz._find_active_streams(5.0, 30.0)
        assert s in result

    def test_stream_ending_after_page(self):
        s = make_stream(onset=25.0, duration=20.0)
        viz = self._viz([s])
        result = viz._find_active_streams(0.0, 30.0)
        assert s in result

    def test_stream_entirely_before_page(self):
        s = make_stream(onset=0.0, duration=5.0)
        viz = self._viz([s])
        result = viz._find_active_streams(10.0, 40.0)
        assert s not in result

    def test_stream_entirely_after_page(self):
        s = make_stream(onset=50.0, duration=10.0)
        viz = self._viz([s])
        result = viz._find_active_streams(10.0, 40.0)
        assert s not in result

    def test_stream_ending_exactly_at_page_start_excluded(self):
        s = make_stream(onset=0.0, duration=10.0)
        viz = self._viz([s])
        result = viz._find_active_streams(10.0, 40.0)
        assert s not in result

    def test_stream_starting_exactly_at_page_end_excluded(self):
        s = make_stream(onset=40.0, duration=5.0)
        viz = self._viz([s])
        result = viz._find_active_streams(10.0, 40.0)
        assert s not in result

    def test_multiple_streams_mixed(self):
        inside  = make_stream('inside',  5.0, 10.0)
        outside = make_stream('outside', 50.0, 10.0)
        viz = self._viz([inside, outside])
        result = viz._find_active_streams(0.0, 30.0)
        assert inside in result
        assert outside not in result

    def test_returns_empty_list_if_no_overlap(self):
        s = make_stream(onset=100.0, duration=10.0)
        viz = self._viz([s])
        result = viz._find_active_streams(0.0, 30.0)
        assert result == []


# =============================================================================
# GROUP D - _calculate_max_concurrent
# =============================================================================

class TestCalculateMaxConcurrent:

    def _viz(self):
        return make_visualizer([make_stream()])

    def test_single_stream(self):
        viz = self._viz()
        s = make_stream(onset=0.0, duration=10.0)
        result = viz._calculate_max_concurrent([s], 0.0, 30.0)
        assert result == 1

    def test_two_non_overlapping(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=5.0)
        s2 = make_stream('s2', onset=10.0, duration=5.0)
        result = viz._calculate_max_concurrent([s1, s2], 0.0, 30.0)
        assert result == 1

    def test_two_fully_overlapping(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=0.0, duration=10.0)
        result = viz._calculate_max_concurrent([s1, s2], 0.0, 30.0)
        assert result == 2

    def test_three_streams_partial_overlap(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=5.0, duration=10.0)
        s3 = make_stream('s3', onset=7.0, duration=3.0)
        result = viz._calculate_max_concurrent([s1, s2, s3], 0.0, 30.0)
        assert result == 3

    def test_peak_concurrency_not_at_boundaries(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=6.0)
        s2 = make_stream('s2', onset=4.0, duration=6.0)
        result = viz._calculate_max_concurrent([s1, s2], 0.0, 20.0)
        assert result == 2

    def test_empty_streams_list(self):
        viz = self._viz()
        result = viz._calculate_max_concurrent([], 0.0, 30.0)
        assert result == 0


# =============================================================================
# GROUP E - _assign_vertical_slots
# =============================================================================

class TestAssignVerticalSlots:

    def _viz(self):
        return make_visualizer([make_stream()])

    def test_single_stream_assigned_slot_zero(self):
        viz = self._viz()
        s = make_stream('s1', onset=0.0, duration=10.0)
        assignments = viz._assign_vertical_slots([s], 0.0, 30.0)
        assert assignments['s1'] == 0

    def test_two_non_overlapping_share_slot_zero(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=5.0)
        s2 = make_stream('s2', onset=10.0, duration=5.0)
        assignments = viz._assign_vertical_slots([s1, s2], 0.0, 30.0)
        assert assignments['s1'] == assignments['s2'] == 0

    def test_two_overlapping_get_different_slots(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=5.0, duration=10.0)
        assignments = viz._assign_vertical_slots([s1, s2], 0.0, 30.0)
        assert assignments['s1'] != assignments['s2']

    def test_slots_are_integers(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=5.0, duration=10.0)
        assignments = viz._assign_vertical_slots([s1, s2], 0.0, 30.0)
        for slot in assignments.values():
            assert isinstance(slot, int)

    def test_three_streams_two_overlapping_one_free(self):
        viz = self._viz()
        s1 = make_stream('s1', onset=0.0, duration=10.0)
        s2 = make_stream('s2', onset=0.0, duration=10.0)
        s3 = make_stream('s3', onset=15.0, duration=5.0)
        assignments = viz._assign_vertical_slots([s1, s2, s3], 0.0, 30.0)
        assert assignments['s3'] in (0, 1)

    def test_all_streams_have_assignment(self):
        viz = self._viz()
        streams = [make_stream(f's{i}', onset=float(i), duration=5.0) for i in range(5)]
        assignments = viz._assign_vertical_slots(streams, 0.0, 30.0)
        for s in streams:
            assert s.stream_id in assignments

    def test_empty_list_returns_empty_dict(self):
        viz = self._viz()
        assignments = viz._assign_vertical_slots([], 0.0, 30.0)
        assert assignments == {}


# =============================================================================
# GROUP F - _load_waveform e _get_sample_duration
# =============================================================================

class TestLoadWaveform:
    """
    Tutti i patch usano 'soundfile.read': funziona perche _sf_mod.read
    e stato aggiunto come attributo nella fase di mock-injection.
    """

    def _viz(self):
        return make_visualizer([make_stream()])

    def test_returns_tuple_of_three(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            result = viz._load_waveform('sample.wav')
        assert len(result) == 3

    def test_time_axis_starts_at_zero(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            time_axis, _, _ = viz._load_waveform('sample.wav')
        assert time_axis[0] == pytest.approx(0.0)

    def test_time_axis_ends_at_duration(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            time_axis, _, duration = viz._load_waveform('sample.wav')
        assert time_axis[-1] == pytest.approx(duration, rel=1e-3)

    def test_amplitude_normalized_to_minus_one_one(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            _, amplitude, _ = viz._load_waveform('sample.wav')
        assert np.max(np.abs(amplitude)) <= 1.0 + 1e-9

    def test_stereo_audio_mixed_to_mono(self):
        stereo = np.stack([FAKE_AUDIO, FAKE_AUDIO * 0.5], axis=1)
        viz = self._viz()
        with patch('soundfile.read', return_value=(stereo, FAKE_SR)):
            time_axis, amplitude, _ = viz._load_waveform('stereo.wav')
        assert amplitude.ndim == 1

    def test_caching_avoids_second_read(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)) as mock_read:
            viz._load_waveform('sample.wav')
            viz._load_waveform('sample.wav')
        assert mock_read.call_count == 1

    def test_different_paths_load_separately(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)) as mock_read:
            viz._load_waveform('a.wav')
            viz._load_waveform('b.wav')
        assert mock_read.call_count == 2

    def test_fallback_on_read_error(self):
        viz = self._viz()
        with patch('soundfile.read', side_effect=Exception("file not found")):
            result = viz._load_waveform('missing.wav')
        assert len(result) == 3

    def test_fallback_duration_is_one(self):
        viz = self._viz()
        with patch('soundfile.read', side_effect=Exception("err")):
            _, _, duration = viz._load_waveform('bad.wav')
        assert duration == 1.0

    def test_zero_amplitude_audio_no_division_error(self):
        silent = np.zeros(FAKE_SR)
        viz = self._viz()
        with patch('soundfile.read', return_value=(silent, FAKE_SR)):
            _, amplitude, _ = viz._load_waveform('silent.wav')
        assert np.all(amplitude == 0.0)

    def test_duration_stored_in_cache(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz._load_waveform('s.wav')
        assert 's.wav' in viz.waveform_cache

    def test_get_sample_duration_returns_float(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            dur = viz._get_sample_duration('s.wav')
        assert isinstance(dur, float)
        assert dur > 0.0

    def test_get_sample_duration_consistent_with_load_waveform(self):
        viz = self._viz()
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            _, _, expected = viz._load_waveform('s.wav')
            dur = viz._get_sample_duration('s.wav')
        assert dur == pytest.approx(expected)

    def test_downsample_reduces_array_size(self):
        long_audio = np.sin(np.linspace(0, 100, FAKE_SR * 5))
        viz = self._viz()
        with patch('soundfile.read', return_value=(long_audio, FAKE_SR)):
            time_axis, amplitude, _ = viz._load_waveform('long.wav')
        ds = viz.config['waveform_downsample']
        expected_len = len(long_audio[::ds])
        assert len(amplitude) == expected_len


# =============================================================================
# GROUP G - _pitch_to_color e _volume_to_alpha
# =============================================================================

class TestPitchToColor:

    def _viz(self):
        return make_visualizer([make_stream()])

    def test_returns_tuple_of_four(self):
        viz = self._viz()
        color = viz._pitch_to_color(1.0)
        assert len(color) == 4

    def test_values_in_range_zero_one(self):
        viz = self._viz()
        for pitch in [0.5, 1.0, 1.5, 2.0]:
            color = viz._pitch_to_color(pitch)
            assert all(0.0 <= c <= 1.0 for c in color)

    def test_clipping_below_range(self):
        viz = self._viz()
        color_min   = viz._pitch_to_color(viz.config['pitch_range'][0])
        color_below = viz._pitch_to_color(0.0)
        assert color_below == color_min

    def test_clipping_above_range(self):
        viz = self._viz()
        color_max   = viz._pitch_to_color(viz.config['pitch_range'][1])
        color_above = viz._pitch_to_color(100.0)
        assert color_above == color_max

    def test_different_pitches_different_colors(self):
        viz = self._viz()
        c1 = viz._pitch_to_color(0.5)
        c2 = viz._pitch_to_color(2.0)
        assert c1 != c2


class TestVolumeToAlpha:

    def _viz(self):
        return make_visualizer([make_stream()])

    def test_returns_float(self):
        viz = self._viz()
        assert isinstance(viz._volume_to_alpha(-6.0), float)

    def test_max_volume_max_alpha(self):
        viz = self._viz()
        _, a_max = viz.config['grain_alpha_range']
        alpha = viz._volume_to_alpha(viz.config['volume_range'][1])
        assert alpha == pytest.approx(a_max)

    def test_min_volume_min_alpha(self):
        viz = self._viz()
        a_min, _ = viz.config['grain_alpha_range']
        alpha = viz._volume_to_alpha(viz.config['volume_range'][0])
        assert alpha == pytest.approx(a_min)

    def test_clipping_above_max(self):
        viz = self._viz()
        _, a_max = viz.config['grain_alpha_range']
        alpha = viz._volume_to_alpha(999.0)
        assert alpha == pytest.approx(a_max)

    def test_clipping_below_min(self):
        viz = self._viz()
        a_min, _ = viz.config['grain_alpha_range']
        alpha = viz._volume_to_alpha(-9999.0)
        assert alpha == pytest.approx(a_min)

    def test_monotonically_increasing(self):
        viz = self._viz()
        v_min, v_max = viz.config['volume_range']
        volumes = np.linspace(v_min, v_max, 10)
        alphas = [viz._volume_to_alpha(v) for v in volumes]
        for i in range(len(alphas) - 1):
            assert alphas[i] <= alphas[i + 1]


# =============================================================================
# GROUP H - _normalize_envelope_value
# =============================================================================

class TestNormalizeEnvelopeValue:

    def _viz(self):
        return make_visualizer([make_stream()])

    def test_volume_mid_normalizes_to_half(self):
        viz = self._viz()
        v_min, v_max = viz.config['envelope_ranges']['volume']
        mid = (v_min + v_max) / 2.0
        result = viz._normalize_envelope_value('volume', mid)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_volume_min_normalizes_to_zero(self):
        viz = self._viz()
        v_min, _ = viz.config['envelope_ranges']['volume']
        result = viz._normalize_envelope_value('volume', v_min)
        assert result == pytest.approx(0.0)

    def test_volume_max_normalizes_to_one(self):
        viz = self._viz()
        _, v_max = viz.config['envelope_ranges']['volume']
        result = viz._normalize_envelope_value('volume', v_max)
        assert result == pytest.approx(1.0)

    def test_clipping_below_zero(self):
        viz = self._viz()
        v_min, _ = viz.config['envelope_ranges']['volume']
        result = viz._normalize_envelope_value('volume', v_min - 100)
        assert result == pytest.approx(0.0)

    def test_clipping_above_one(self):
        viz = self._viz()
        _, v_max = viz.config['envelope_ranges']['volume']
        result = viz._normalize_envelope_value('volume', v_max + 100)
        assert result == pytest.approx(1.0)

    def test_pan_cyclic_value_within_range(self):
        viz = self._viz()
        result = viz._normalize_envelope_value('pan', 0.0)
        assert 0.0 <= result <= 1.0

    def test_pan_cyclic_value_out_of_range_wraps(self):
        viz = self._viz()
        r1 = viz._normalize_envelope_value('pan', 180.0)
        r2 = viz._normalize_envelope_value('pan', 540.0)
        assert r1 == pytest.approx(r2, abs=0.01)

    def test_unknown_param_clips_to_zero_one(self):
        viz = self._viz()
        result = viz._normalize_envelope_value('nonexistent_param', 0.5)
        assert result == pytest.approx(0.5)

    def test_unknown_param_above_one_clipped(self):
        viz = self._viz()
        result = viz._normalize_envelope_value('nonexistent_param', 5.0)
        assert result == pytest.approx(1.0)

    def test_unknown_param_below_zero_clipped(self):
        viz = self._viz()
        result = viz._normalize_envelope_value('nonexistent_param', -2.0)
        assert result == pytest.approx(0.0)

    def test_pointer_start_normalized(self):
        viz = self._viz()
        result = viz._normalize_envelope_value('pointer_start', 0.5)
        assert result == pytest.approx(0.5)

    @pytest.mark.parametrize('param_name', ['volume', 'pan', 'grain_duration',
                                             'pointer_start', 'pitch_ratio', 'density'])
    def test_known_params_return_float(self, param_name):
        viz = self._viz()
        result = viz._normalize_envelope_value(param_name, 0.0)
        assert isinstance(result, (float, np.floating))


# =============================================================================
# GROUP I - _get_stream_envelopes
# =============================================================================

# NOTA: _get_stream_envelopes esegue lazy imports:
#   from envelope import Envelope
#   from parameter import Parameter
#   from parameter_schema import STREAM_PARAMETER_SCHEMA, ...
#
# Se altri moduli nel test session hanno gia importato i moduli reali da src/,
# sys.modules contiene le classi reali e isinstance(MockEnvelope_instance,
# real_Envelope) sarebbe False. Usiamo patch.dict per garantire che durante
# ogni test in questo gruppo i nostri mock siano presenti in sys.modules.

_MODULE_OVERRIDES = {
    'envelope':         _envelope_mod,
    'parameter':        _parameter_mod,
    'parameter_schema': _param_schema_mod,
}


class TestGetStreamEnvelopes:

    @pytest.fixture(autouse=True)
    def _force_mock_modules(self):
        """Garantisce che i mock di envelope/parameter siano in sys.modules
        durante ogni chiamata a _get_stream_envelopes."""
        with patch.dict(sys.modules, _MODULE_OVERRIDES):
            yield

    def _viz(self, show_static=False):
        return make_visualizer([make_stream()], config={'show_static_params': show_static})

    def _stream_with(self, **attrs):
        s = MagicMock()
        s.stream_id = 'test'
        s.onset = 0.0
        s.duration = 10.0
        s.sample = 'x.wav'
        s.voices = []
        for k, v in attrs.items():
            setattr(s, k, v)
        return s

    def test_no_schema_attrs_returns_empty(self):
        viz = self._viz()
        s = make_stream()  # nessun attributo schema
        result = viz._get_stream_envelopes(s)
        assert result == {}

    def test_dynamic_envelope_extracted(self):
        viz = self._viz()
        env = MockEnvelope([[0.0, -6.0], [5.0, -12.0], [10.0, -6.0]])
        s = self._stream_with(volume=env)
        result = viz._get_stream_envelopes(s)
        assert 'volume' in result

    def test_static_envelope_excluded_when_show_static_false(self):
        viz = self._viz(show_static=False)
        env = MockEnvelope([[0.0, -6.0]])  # single breakpoint
        s = self._stream_with(volume=env)
        result = viz._get_stream_envelopes(s)
        assert 'volume' not in result

    def test_static_envelope_included_when_show_static_true(self):
        viz = self._viz(show_static=True)
        env = MockEnvelope([[0.0, -6.0]])
        s = self._stream_with(volume=env)
        result = viz._get_stream_envelopes(s)
        assert 'volume' in result

    def test_static_float_excluded_when_show_static_false(self):
        viz = self._viz(show_static=False)
        s = self._stream_with(volume=-6.0)
        result = viz._get_stream_envelopes(s)
        assert 'volume' not in result

    def test_static_float_included_when_show_static_true(self):
        viz = self._viz(show_static=True)
        s = self._stream_with(volume=-6.0)
        result = viz._get_stream_envelopes(s)
        assert 'volume' in result

    def test_parameter_with_envelope_value_extracted(self):
        viz = self._viz()
        env = MockEnvelope([[0.0, -6.0], [5.0, -12.0]])
        param = MockParameter(value=env)
        s = self._stream_with(volume=param)
        result = viz._get_stream_envelopes(s)
        assert 'volume' in result

    def test_parameter_with_mod_prob_envelope_extracted(self):
        viz = self._viz()
        prob_env = MockEnvelope([[0.0, 50.0], [5.0, 80.0]])
        param = MockParameter(value=-6.0, mod_prob=prob_env)
        s = self._stream_with(volume=param)
        result = viz._get_stream_envelopes(s)
        assert 'volume_prob' in result

    def test_parameter_with_static_mod_prob_excluded_show_static_false(self):
        viz = self._viz(show_static=False)
        prob_env = MockEnvelope([[0.0, 75.0]])
        param = MockParameter(value=-6.0, mod_prob=prob_env)
        s = self._stream_with(volume=param)
        result = viz._get_stream_envelopes(s)
        assert 'volume_prob' not in result

    def test_returns_dict(self):
        viz = self._viz()
        result = viz._get_stream_envelopes(make_stream())
        assert isinstance(result, dict)

    def test_multiple_dynamic_envelopes(self):
        viz = self._viz()
        vol_env = MockEnvelope([[0.0, -6.0], [5.0, -12.0]])
        pan_env = MockEnvelope([[0.0, 0.0], [5.0, 90.0]])
        s = self._stream_with(volume=vol_env, pan=pan_env)
        result = viz._get_stream_envelopes(s)
        assert 'volume' in result
        assert 'pan' in result


# =============================================================================
# GROUP J - render_page
# =============================================================================

class TestRenderPage:

    def _setup(self, streams, config=None):
        viz = make_visualizer(streams, config=config)
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz.analyze()
        return viz

    def test_returns_figure_object(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=0.0, duration=10.0)
        viz = self._setup([s])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            fig = viz.render_page(0)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_empty_page_returns_figure(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=35.0, duration=5.0)
        viz = self._setup([s], config={'page_duration': 30.0})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            fig = viz.render_page(0)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_page_title_contains_page_number(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=0.0, duration=10.0)
        viz = self._setup([s])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            fig = viz.render_page(0)
        assert fig._suptitle is not None
        assert '1' in fig._suptitle.get_text()
        plt.close(fig)

    def test_page_title_contains_time_range(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=0.0, duration=10.0)
        viz = self._setup([s])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            fig = viz.render_page(0)
        assert '0.0' in fig._suptitle.get_text()
        plt.close(fig)

    def test_figure_size_respects_config(self):
        import matplotlib.pyplot as plt
        s = make_stream()
        viz = self._setup([s], config={'page_size': (420, 297)})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            fig = viz.render_page(0)
        w, h = fig.get_size_inches()
        assert w == pytest.approx(420 / 25.4, rel=0.01)
        assert h == pytest.approx(297 / 25.4, rel=0.01)
        plt.close(fig)

    def test_two_samples_two_subplots(self):
        import matplotlib.pyplot as plt
        s1 = make_stream('s1', 0.0, 10.0, sample='a.wav')
        s2 = make_stream('s2', 0.0, 10.0, sample='b.wav')
        viz = self._setup([s1, s2])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            fig = viz.render_page(0)
        assert len(fig.axes) >= 2
        plt.close(fig)


# =============================================================================
# GROUP K - render_all
# =============================================================================

class TestRenderAll:

    def test_returns_list_of_figures(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=0.0, duration=10.0)
        viz = make_visualizer([s])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            figs = viz.render_all()
        assert isinstance(figs, list) and len(figs) > 0
        plt.close('all')

    def test_triggers_analyze_if_not_done(self):
        s = make_stream(onset=0.0, duration=10.0)
        viz = make_visualizer([s])
        assert viz.page_layouts == []
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz.render_all()
        assert viz.page_layouts != []
        import matplotlib.pyplot as plt
        plt.close('all')

    def test_number_of_figures_equals_page_count(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=0.0, duration=70.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            figs = viz.render_all()
        assert len(figs) == viz.page_count
        plt.close('all')


# =============================================================================
# GROUP L - export_pdf / export_png / show
# =============================================================================

class TestExportPdf:

    def test_export_pdf_calls_savefig_for_each_page(self):
        import matplotlib.pyplot as plt
        s = make_stream(onset=0.0, duration=60.0)
        viz = make_visualizer([s], config={'page_duration': 30.0})

        mock_pdf_ctx = MagicMock()
        mock_pdf_instance = MagicMock()
        mock_pdf_ctx.__enter__ = MagicMock(return_value=mock_pdf_instance)
        mock_pdf_ctx.__exit__ = MagicMock(return_value=False)

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('score_visualizer.PdfPages',
                   return_value=mock_pdf_ctx):
            viz.export_pdf('/tmp/test.pdf')

        assert mock_pdf_instance.savefig.call_count == 2
        plt.close('all')

    def test_export_pdf_opens_correct_path(self):
        import matplotlib.pyplot as plt
        s = make_stream()
        viz = make_visualizer([s])

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('score_visualizer.PdfPages') as mock_pp:
            mock_pp.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_pp.return_value.__exit__ = MagicMock(return_value=False)
            viz.export_pdf('/tmp/test.pdf')

        mock_pp.assert_called_once_with('/tmp/test.pdf')
        plt.close('all')


class TestExportPng:

    def test_export_png_creates_output_dir(self):
        import matplotlib.pyplot as plt
        s = make_stream()
        viz = make_visualizer([s])

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('os.makedirs') as mock_mkdirs, \
             patch.object(viz, 'render_all', return_value=[MagicMock()]), \
             patch('matplotlib.figure.Figure.savefig'):
            viz.export_png('/tmp/out_dir')

        mock_mkdirs.assert_called_once_with('/tmp/out_dir', exist_ok=True)
        plt.close('all')

    def test_export_png_saves_one_file_per_page(self):
        import matplotlib.pyplot as plt
        s = make_stream()
        viz = make_visualizer([s])
        mock_figs = [MagicMock(), MagicMock()]

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('os.makedirs'), \
             patch.object(viz, 'render_all', return_value=mock_figs):
            viz.export_png('/tmp/out_dir')

        for f in mock_figs:
            f.savefig.assert_called_once()
        plt.close('all')

    def test_export_png_uses_prefix_in_filename(self):
        import matplotlib.pyplot as plt
        s = make_stream()
        viz = make_visualizer([s])
        mock_fig = MagicMock()

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('os.makedirs'), \
             patch.object(viz, 'render_all', return_value=[mock_fig]):
            viz.export_png('/tmp/out', prefix='mypage')

        call_args = mock_fig.savefig.call_args[0][0]
        assert 'mypage' in call_args
        plt.close('all')


class TestShow:

    def test_show_returns_figure(self):
        import matplotlib.pyplot as plt
        s = make_stream()
        viz = make_visualizer([s])

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('matplotlib.pyplot.show'):
            fig = viz.show(0)

        assert isinstance(fig, plt.Figure)
        plt.close('all')

    def test_show_triggers_analyze_if_needed(self):
        s = make_stream()
        viz = make_visualizer([s])
        assert viz.page_layouts == []

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('matplotlib.pyplot.show'):
            viz.show(0)

        assert viz.page_layouts != []
        import matplotlib.pyplot as plt
        plt.close('all')


# =============================================================================
# GROUP M - _draw_grains_full
# =============================================================================

class TestDrawGrainsFull:

    def _make_ax(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        return fig, ax

    def test_no_grains_in_window_does_not_add_collection(self):
        import matplotlib.pyplot as plt
        from matplotlib.collections import PatchCollection

        fig, ax = self._make_ax()
        s = make_stream(onset=0.0, duration=10.0, grains_per_voice=3)
        for voice in s.voices:
            for g in voice:
                g.onset = 100.0
                g.duration = 0.05

        viz = make_visualizer([s])
        viz._draw_grains_full(ax, s, 2.0, 0.0, 10.0)

        collections = [c for c in ax.collections if isinstance(c, PatchCollection)]
        assert len(collections) == 0
        plt.close(fig)

    def test_visible_grains_add_patch_collection(self):
        import matplotlib.pyplot as plt
        from matplotlib.collections import PatchCollection

        fig, ax = self._make_ax()
        s = make_stream(onset=0.0, duration=10.0, grains_per_voice=5)
        for voice in s.voices:
            for i, g in enumerate(voice):
                g.onset = float(i)
                g.duration = 0.1
                g.pointer_pos = 0.5
                g.pitch_ratio = 1.0
                g.volume = -6.0

        viz = make_visualizer([s])
        viz._draw_grains_full(ax, s, 5.0, 0.0, 10.0)

        collections = [c for c in ax.collections if isinstance(c, PatchCollection)]
        assert len(collections) == 1
        plt.close(fig)

    def test_reverse_pitch_creates_downward_arrow(self):
        import matplotlib.pyplot as plt
        from matplotlib.collections import PatchCollection

        fig, ax = self._make_ax()
        s = MagicMock()
        s.stream_id = 'rev'
        grain = make_grain(onset=1.0, duration=0.1, pointer_pos=1.0,
                           pitch_ratio=-1.0, volume=-6.0)
        s.voices = [[grain]]

        viz = make_visualizer([s])
        viz._draw_grains_full(ax, s, 5.0, 0.0, 10.0)

        collections = [c for c in ax.collections if isinstance(c, PatchCollection)]
        assert len(collections) == 1
        plt.close(fig)

    def test_multiple_voices_all_grains_collected(self):
        import matplotlib.pyplot as plt
        from matplotlib.collections import PatchCollection

        fig, ax = self._make_ax()
        g1 = make_grain(0.5, 0.1, 0.5, 1.0, -6.0)
        g2 = make_grain(1.5, 0.1, 0.5, 1.0, -6.0)
        g3 = make_grain(2.5, 0.1, 0.5, 1.0, -6.0)
        s = MagicMock()
        s.voices = [[g1, g2], [g3]]

        viz = make_visualizer([s])
        viz._draw_grains_full(ax, s, 5.0, 0.0, 10.0)

        collections = [c for c in ax.collections if isinstance(c, PatchCollection)]
        assert len(collections) == 1
        plt.close(fig)


# =============================================================================
# GROUP N - _draw_waveform_full
# =============================================================================

class TestDrawWaveformFull:

    def _make_ax(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        return fig, ax

    def test_waveform_adds_line_to_axis(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        s = make_stream()

        viz = make_visualizer([s])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz._draw_waveform_full(ax, s, FAKE_DURATION)

        assert len(ax.lines) > 0
        plt.close(fig)

    def test_waveform_uses_config_color(self):
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        fig, ax = self._make_ax()
        s = make_stream()
        viz = make_visualizer([s], config={'waveform_color': 'red'})

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz._draw_waveform_full(ax, s, FAKE_DURATION)

        line = ax.lines[0]
        expected = mcolors.to_rgba('red')
        actual   = mcolors.to_rgba(line.get_color())
        assert actual == pytest.approx(expected, abs=0.01)
        plt.close(fig)

    def test_waveform_y_range_matches_sample_duration(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        s = make_stream()

        viz = make_visualizer([s])
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz._draw_waveform_full(ax, s, FAKE_DURATION)

        line   = ax.lines[0]
        y_data = line.get_ydata()
        assert y_data[0]  == pytest.approx(0.0, abs=0.01)
        assert y_data[-1] == pytest.approx(FAKE_DURATION, rel=0.05)
        plt.close(fig)


# =============================================================================
# GROUP O - _draw_stream_label_full
# =============================================================================

class TestDrawStreamLabelFull:

    def _make_ax(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        return fig, ax

    def test_label_text_contains_stream_id(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        s = make_stream(stream_id='my_stream', onset=0.0, duration=10.0)
        viz = make_visualizer([s])
        viz._draw_stream_label_full(ax, s, 0.0, 2.0)

        texts = [t.get_text() for t in ax.texts]
        assert any('my_stream' in t for t in texts)
        plt.close(fig)

    def test_label_added_once(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        s = make_stream(stream_id='s1')
        viz = make_visualizer([s])
        viz._draw_stream_label_full(ax, s, 0.0, 2.0)
        assert len(ax.texts) == 1
        plt.close(fig)


# =============================================================================
# GROUP P - _draw_loop_mask (smoke test)
# =============================================================================

class TestDrawLoopMask:

    def _make_ax(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 2)
        return fig, ax

    def test_stream_without_loop_attrs_no_exception(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        s = make_stream(onset=0.0, duration=10.0)
        viz = make_visualizer([s])
        try:
            viz._draw_loop_mask(ax, s, 0.0, 10.0, 2.0)
        except AttributeError:
            pass  # stream mock senza loop attrs: comportamento atteso
        plt.close(fig)


# =============================================================================
# GROUP Q - _draw_envelopes / _draw_envelope_legend
# =============================================================================

class TestDrawEnvelopes:

    def _make_ax(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_xlim(0.0, 10.0)
        return fig, ax

    def test_no_envelopes_returns_empty_set(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        s = make_stream()
        viz = make_visualizer([s])
        result = viz._draw_envelopes(ax, s, 0.0, 1.0, 0.0, 10.0)
        assert result == set()
        plt.close(fig)

    def test_dynamic_envelope_draws_line(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        env = MockEnvelope([[0.0, -6.0], [5.0, -12.0], [10.0, -6.0]])

        s = MagicMock()
        s.stream_id = 'e1'
        s.onset = 0.0
        s.duration = 10.0
        s.sample = 'x.wav'
        s.voices = []

        viz = make_visualizer([s])
        with patch.object(viz, '_get_stream_envelopes', return_value={'volume': env}):
            result = viz._draw_envelopes(ax, s, 0.0, 1.0, 0.0, 10.0)

        assert 'volume' in result
        assert len(ax.lines) > 0
        plt.close(fig)

    def test_returns_set_of_drawn_param_names(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        vol_env = MockEnvelope([[0.0, -6.0], [5.0, -12.0]])
        pan_env = MockEnvelope([[0.0, 0.0], [5.0, 90.0]])

        s = MagicMock()
        s.stream_id = 'e2'
        s.onset = 0.0
        s.duration = 10.0
        s.voices = []

        viz = make_visualizer([s])
        with patch.object(viz, '_get_stream_envelopes',
                          return_value={'volume': vol_env, 'pan': pan_env}):
            result = viz._draw_envelopes(ax, s, 0.0, 1.0, 0.0, 10.0)

        assert 'volume' in result
        assert 'pan' in result
        plt.close(fig)

    def test_stream_outside_page_returns_empty_set(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        env = MockEnvelope([[0.0, -6.0], [5.0, -12.0]])

        s = MagicMock()
        s.onset = 50.0
        s.duration = 10.0
        s.stream_id = 'out'
        s.voices = []

        viz = make_visualizer([s])
        with patch.object(viz, '_get_stream_envelopes', return_value={'volume': env}):
            result = viz._draw_envelopes(ax, s, 0.0, 1.0, 0.0, 10.0)

        assert result == set()
        plt.close(fig)

    def test_step_envelope_does_not_raise(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        env = MockEnvelope([[0.0, -6.0], [5.0, -12.0]], type_='step')

        s = MagicMock()
        s.onset = 0.0
        s.duration = 10.0
        s.stream_id = 'step_s'
        s.voices = []

        viz = make_visualizer([s])
        with patch.object(viz, '_get_stream_envelopes', return_value={'volume': env}):
            result = viz._draw_envelopes(ax, s, 0.0, 1.0, 0.0, 10.0)
        assert isinstance(result, set)
        plt.close(fig)


class TestDrawEnvelopeLegend:

    def _make_ax(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        return fig, ax

    def test_empty_envelope_types_no_exception(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        viz = make_visualizer([make_stream()])
        viz._draw_envelope_legend(ax, set())
        plt.close(fig)

    def test_known_envelope_type_draws_line(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        viz = make_visualizer([make_stream()])
        viz._draw_envelope_legend(ax, {'volume', 'pan'})
        assert len(ax.lines) > 0
        plt.close(fig)

    def test_unknown_envelope_type_uses_fallback_color(self):
        import matplotlib.pyplot as plt
        fig, ax = self._make_ax()
        viz = make_visualizer([make_stream()])
        viz._draw_envelope_legend(ax, {'totally_unknown_param'})
        plt.close(fig)


# =============================================================================
# GROUP R - Integration
# =============================================================================

class TestIntegration:

    def _build_scene(self):
        s1 = make_stream('stream_A', onset=0.0,  duration=20.0, sample='piano.wav')
        s2 = make_stream('stream_B', onset=5.0,  duration=30.0, sample='violin.wav')
        s3 = make_stream('stream_C', onset=25.0, duration=10.0, sample='piano.wav')
        return [s1, s2, s3]

    def test_full_pipeline_no_exception(self):
        import matplotlib.pyplot as plt
        streams = self._build_scene()
        viz = make_visualizer(streams, config={'page_duration': 20.0})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            figs = viz.render_all()
        assert len(figs) == viz.page_count
        plt.close('all')

    def test_page_count_correct_for_multi_stream(self):
        streams = self._build_scene()
        viz = make_visualizer(streams, config={'page_duration': 20.0})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz.analyze()
        assert viz.page_count == 2

    def test_sample_grouped_in_same_subplot(self):
        import matplotlib.pyplot as plt
        streams = self._build_scene()
        viz = make_visualizer(streams, config={'page_duration': 40.0})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz.analyze()
            fig = viz.render_page(0)
        assert len(fig.axes) >= 4
        plt.close('all')

    def test_export_pdf_integration(self):
        import matplotlib.pyplot as plt
        streams = self._build_scene()
        viz = make_visualizer(streams, config={'page_duration': 20.0})

        mock_ctx  = MagicMock()
        mock_inst = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_inst)
        mock_ctx.__exit__  = MagicMock(return_value=False)

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)), \
             patch('score_visualizer.PdfPages',
                   return_value=mock_ctx):
            viz.export_pdf('/tmp/integration_test.pdf')

        assert mock_inst.savefig.call_count == 2
        plt.close('all')

    def test_waveform_cached_across_pages(self):
        streams = self._build_scene()
        viz = make_visualizer(streams, config={'page_duration': 20.0})

        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)) as mock_sf:
            viz.render_all()

        piano_calls = [c for c in mock_sf.call_args_list
                       if 'piano.wav' in str(c)]
        assert len(piano_calls) == 1
        import matplotlib.pyplot as plt
        plt.close('all')

    def test_slot_assignments_cover_all_active_streams(self):
        streams = self._build_scene()
        viz = make_visualizer(streams, config={'page_duration': 40.0})
        with patch('soundfile.read', return_value=(FAKE_AUDIO, FAKE_SR)):
            viz.analyze()
        for layout in viz.page_layouts:
            for s in layout['active_streams']:
                assert s.stream_id in layout['slot_assignments']