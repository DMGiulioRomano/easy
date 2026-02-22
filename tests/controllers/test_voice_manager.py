"""
test_voice_manager.py

Suite completa di test per VoiceManager.

Coverage target: 100%

Sezioni:
  1.  Inizializzazione - default params
  2.  Inizializzazione - params custom da YAML
  3.  _calculate_max_voices - valore fisso
  4.  _calculate_max_voices - envelope (max breakpoint)
  5.  max_voices property
  6.  get_active_voices - num_voices None
  7.  get_active_voices - valore fisso
  8.  get_active_voices - envelope temporale
  9.  get_active_voices - clamp ai bounds
 10.  _get_voice_offset - pattern alternato +/-
 11.  get_voice_pitch_offset_semitones - voice 0
 12.  get_voice_pitch_offset_semitones - voci multiple
 13.  get_voice_pitch_offset_semitones - None param
 14.  get_voice_pitch_multiplier - conversione semitoni/ratio
 15.  get_voice_pointer_offset - pattern alternato
 16.  get_voice_pointer_offset - None param
 17.  get_voice_pointer_range - valore fisso e None
 18.  is_voice_active
 19.  Backward compatibility properties
 20.  __repr__
 21.  Parametrized - pattern alternato sistematico
 22.  Parametrized - pitch multiplier
 23.  Edge cases
"""

import sys
import pytest
import math
from unittest.mock import patch, MagicMock
from controllers.voice_manager import VoiceManager
from core.stream_config import StreamContext
from core.stream_config import StreamConfig
from envelopes.envelope import Envelope
from parameters.parameter import Parameter

# ---------------------------------------------------------------------------
# Helpers per costruire StreamConfig / StreamContext minimi senza toccare
# il vero file-system o i parametri Csound.
# ---------------------------------------------------------------------------

def make_stream_context(
    stream_id='test_stream',
    onset=0.0,
    duration=10.0,
    sample='test.wav',
    sample_dur_sec=5.0,
):
    return StreamContext(
        stream_id=stream_id,
        onset=onset,
        duration=duration,
        sample=sample,
        sample_dur_sec=sample_dur_sec,
    )


def make_stream_config(**kwargs):
    ctx = kwargs.pop('context', make_stream_context())
    return StreamConfig(context=ctx, **kwargs)


def make_voice_manager(params=None, config=None):
    """Costruisce un VoiceManager con params e config minimali."""
    if params is None:
        params = {}
    if config is None:
        config = make_stream_config()
    return VoiceManager(params=params, config=config)


# =============================================================================
# 1. INIZIALIZZAZIONE - DEFAULT PARAMS
# =============================================================================

class TestVoiceManagerInitDefault:
    """VoiceManager costruito con dizionario vuoto usa tutti i default."""

    def test_creates_without_error(self):
        """Costruzione con params vuoto non solleva eccezioni."""
        vm = make_voice_manager()
        assert vm is not None

    def test_has_num_voices_attribute(self):
        """num_voices esiste dopo costruzione."""
        vm = make_voice_manager()
        assert hasattr(vm, 'num_voices')

    def test_has_voice_pitch_offset_attribute(self):
        vm = make_voice_manager()
        assert hasattr(vm, 'voice_pitch_offset')

    def test_has_voice_pointer_offset_attribute(self):
        vm = make_voice_manager()
        assert hasattr(vm, 'voice_pointer_offset')

    def test_has_voice_pointer_range_attribute(self):
        vm = make_voice_manager()
        assert hasattr(vm, 'voice_pointer_range')

    def test_max_voices_default_is_one(self):
        """Default num_voices=1 -> max_voices=1."""
        vm = make_voice_manager()
        assert vm.max_voices == 1

    def test_has_orchestrator(self):
        vm = make_voice_manager()
        assert hasattr(vm, '_orchestrator')


# =============================================================================
# 2. INIZIALIZZAZIONE - PARAMS CUSTOM
# =============================================================================

class TestVoiceManagerInitCustom:
    """Costruzione con parametri espliciti dallo YAML."""

    def test_num_voices_fixed(self):
        """number=3 produce max_voices=3."""
        vm = make_voice_manager(params={'number': 3})
        assert vm.max_voices == 3

    def test_pitch_offset_loaded(self):
        """offset_pitch viene caricato come attributo Parameter."""
        vm = make_voice_manager(params={'offset_pitch': 2.0})
        assert vm.voice_pitch_offset is not None
        assert isinstance(vm.voice_pitch_offset, Parameter)

    def test_pointer_offset_loaded(self):
        vm = make_voice_manager(params={'pointer_offset': 0.1})
        assert isinstance(vm.voice_pointer_offset, Parameter)

    def test_pointer_range_loaded(self):
        vm = make_voice_manager(params={'pointer_range': 0.05})
        assert isinstance(vm.voice_pointer_range, Parameter)

    def test_loaded_params_stored(self):
        """_loaded_params contiene tutte e quattro le chiavi."""
        vm = make_voice_manager(params={'number': 2})
        for key in ('num_voices', 'voice_pitch_offset',
                    'voice_pointer_offset', 'voice_pointer_range'):
            assert key in vm._loaded_params


# =============================================================================
# 3. _CALCULATE_MAX_VOICES - VALORE FISSO
# =============================================================================

class TestCalculateMaxVoicesFixed:
    """_calculate_max_voices con numero fisso."""

    def test_single_voice(self):
        vm = make_voice_manager(params={'number': 1})
        assert vm._calculate_max_voices() == 1

    def test_four_voices(self):
        vm = make_voice_manager(params={'number': 4})
        assert vm._calculate_max_voices() == 4

    def test_eight_voices(self):
        vm = make_voice_manager(params={'number': 8})
        assert vm._calculate_max_voices() == 8

    def test_num_voices_none_returns_one(self):
        """Quando num_voices e' None, max_voices deve essere 1."""
        vm = make_voice_manager()
        # Forziamo num_voices a None per testare il ramo
        vm.num_voices = None
        assert vm._calculate_max_voices() == 1


# =============================================================================
# 4. _CALCULATE_MAX_VOICES - ENVELOPE
# =============================================================================

class TestCalculateMaxVoicesEnvelope:
    """_calculate_max_voices con Envelope: prende il max dei breakpoints."""

    def test_envelope_max_is_picked(self):
        """Envelope che va da 1 a 4: max_voices == 4."""
        vm = make_voice_manager(params={'number': [[0, 1], [5, 4], [10, 2]]})
        # Il parser converte la lista in Envelope internamente
        # verifichiamo solo che max_voices sia il massimo
        assert vm.max_voices == 4

    def test_envelope_constant(self):
        """Envelope piatta a 3: max_voices == 3."""
        vm = make_voice_manager(params={'number': [[0, 3], [10, 3]]})
        assert vm.max_voices == 3

    def test_envelope_single_breakpoint(self):
        """Envelope con un solo punto."""
        vm = make_voice_manager(params={'number': [[0, 2]]})
        assert vm.max_voices == 2


# =============================================================================
# 5. MAX_VOICES PROPERTY
# =============================================================================

class TestMaxVoicesProperty:
    """max_voices e' una property che ritorna _max_voices."""

    def test_property_equals_cached_value(self):
        vm = make_voice_manager(params={'number': 5})
        assert vm.max_voices == vm._max_voices

    def test_property_is_int(self):
        vm = make_voice_manager(params={'number': 3})
        assert isinstance(vm.max_voices, int)


# =============================================================================
# 6. GET_ACTIVE_VOICES - NUM_VOICES NONE
# =============================================================================

class TestGetActiveVoicesNone:
    """Quando num_voices e' None, get_active_voices ritorna sempre 1."""

    def test_returns_one_at_t0(self):
        vm = make_voice_manager()
        vm.num_voices = None
        assert vm.get_active_voices(0.0) == 1

    def test_returns_one_at_any_time(self):
        vm = make_voice_manager()
        vm.num_voices = None
        for t in (0.0, 1.5, 5.0, 100.0):
            assert vm.get_active_voices(t) == 1


# =============================================================================
# 7. GET_ACTIVE_VOICES - VALORE FISSO
# =============================================================================

class TestGetActiveVoicesFixed:
    """get_active_voices con numero fisso."""

    def test_fixed_two(self):
        vm = make_voice_manager(params={'number': 2})
        assert vm.get_active_voices(0.0) == 2

    def test_fixed_three_at_any_time(self):
        vm = make_voice_manager(params={'number': 3})
        for t in (0.0, 3.0, 9.99):
            assert vm.get_active_voices(t) == 3

    def test_result_is_int(self):
        vm = make_voice_manager(params={'number': 4})
        result = vm.get_active_voices(0.0)
        assert isinstance(result, int)


# =============================================================================
# 8. GET_ACTIVE_VOICES - ENVELOPE
# =============================================================================

class TestGetActiveVoicesEnvelope:
    """get_active_voices con Envelope."""

    def test_envelope_ramp_up(self):
        """Envelope 1->4: il numero di voci cresce nel tempo."""
        vm = make_voice_manager(params={'number': [[0, 1], [10, 4]]})
        v_start = vm.get_active_voices(0.0)
        v_end   = vm.get_active_voices(10.0)
        assert v_start <= v_end
        assert v_start >= 1
        assert v_end <= vm.max_voices


# =============================================================================
# 9. GET_ACTIVE_VOICES - CLAMP AI BOUNDS
# =============================================================================

class TestGetActiveVoicesClamp:
    """Verifica che il risultato sia sempre in [1, max_voices]."""

    def test_never_below_one(self):
        """Anche se il valore calcolato fosse 0 o negativo, ritorna almeno 1."""
        vm = make_voice_manager(params={'number': 1})
        # Mocka get_value per restituire 0
        vm.num_voices.get_value = lambda t: 0.0
        assert vm.get_active_voices(0.0) >= 1

    def test_never_above_max_voices(self):
        """Il risultato non supera mai max_voices."""
        vm = make_voice_manager(params={'number': 2})
        # Forza un valore eccessivo
        vm.num_voices.get_value = lambda t: 999.0
        assert vm.get_active_voices(0.0) <= vm.max_voices


# =============================================================================
# 10. _GET_VOICE_OFFSET - PATTERN ALTERNATO
# =============================================================================

class TestGetVoiceOffset:
    """Verifica il pattern +/- per le voci."""

    def setup_method(self):
        self.vm = make_voice_manager()

    def test_voice_0_always_zero(self):
        """Voice 0 ha sempre offset 0."""
        assert self.vm._get_voice_offset(0, 1.0) == 0.0

    def test_base_offset_zero_returns_zero_for_all(self):
        """Se base_offset==0, tutte le voci hanno offset 0."""
        for i in range(6):
            assert self.vm._get_voice_offset(i, 0.0) == 0.0

    def test_voice_1_positive(self):
        """Voice 1 (dispari): +offset * 1."""
        assert self.vm._get_voice_offset(1, 2.0) == pytest.approx(2.0)

    def test_voice_2_negative(self):
        """Voice 2 (pari): -offset * 1."""
        assert self.vm._get_voice_offset(2, 2.0) == pytest.approx(-2.0)

    def test_voice_3_positive_double(self):
        """Voice 3 (dispari): +offset * 2."""
        assert self.vm._get_voice_offset(3, 2.0) == pytest.approx(4.0)

    def test_voice_4_negative_double(self):
        """Voice 4 (pari): -offset * 2."""
        assert self.vm._get_voice_offset(4, 2.0) == pytest.approx(-4.0)

    def test_voice_5_positive_triple(self):
        """Voice 5 (dispari): +offset * 3."""
        assert self.vm._get_voice_offset(5, 2.0) == pytest.approx(6.0)

    def test_symmetry_pair(self):
        """Coppie 1/2, 3/4 hanno stesso modulo, segno opposto."""
        base = 3.0
        assert abs(self.vm._get_voice_offset(1, base)) == abs(self.vm._get_voice_offset(2, base))
        assert abs(self.vm._get_voice_offset(3, base)) == abs(self.vm._get_voice_offset(4, base))
        assert self.vm._get_voice_offset(1, base) > 0
        assert self.vm._get_voice_offset(2, base) < 0


# =============================================================================
# 11-12. GET_VOICE_PITCH_OFFSET_SEMITONES
# =============================================================================

class TestGetVoicePitchOffsetSemitones:
    """Test per get_voice_pitch_offset_semitones."""

    def test_voice_0_always_zero(self):
        """Voice 0: offset sempre 0 indipendentemente dal parametro."""
        vm = make_voice_manager(params={'offset_pitch': 2.0})
        assert vm.get_voice_pitch_offset_semitones(0, 0.0) == pytest.approx(0.0)

    def test_voice_1_positive(self):
        """Voice 1: offset positivo uguale al valore base."""
        vm = make_voice_manager(params={'offset_pitch': 3.0})
        result = vm.get_voice_pitch_offset_semitones(1, 0.0)
        assert result == pytest.approx(3.0)

    def test_voice_2_negative(self):
        """Voice 2: offset negativo uguale al valore base."""
        vm = make_voice_manager(params={'offset_pitch': 3.0})
        result = vm.get_voice_pitch_offset_semitones(2, 0.0)
        assert result == pytest.approx(-3.0)

    def test_voice_3_doubled(self):
        vm = make_voice_manager(params={'offset_pitch': 1.0})
        result = vm.get_voice_pitch_offset_semitones(3, 0.0)
        assert result == pytest.approx(2.0)

    def test_none_param_returns_zero(self):
        """Se voice_pitch_offset e' None, ritorna sempre 0."""
        vm = make_voice_manager()
        vm.voice_pitch_offset = None
        for i in range(5):
            assert vm.get_voice_pitch_offset_semitones(i, 0.0) == 0.0

    def test_zero_offset_param_returns_zero(self):
        """offset_pitch=0: tutte le voci a 0."""
        vm = make_voice_manager(params={'offset_pitch': 0.0})
        for i in range(6):
            assert vm.get_voice_pitch_offset_semitones(i, 0.0) == pytest.approx(0.0)


# =============================================================================
# 13-14. GET_VOICE_PITCH_MULTIPLIER
# =============================================================================

class TestGetVoicePitchMultiplier:
    """Conversione semitoni -> ratio: 2^(semitones/12)."""

    def test_voice_0_ratio_is_one(self):
        """Voice 0: 0 semitoni -> ratio 1.0 (nessuna trasposizione)."""
        vm = make_voice_manager(params={'offset_pitch': 2.0})
        assert vm.get_voice_pitch_multiplier(0, 0.0) == pytest.approx(1.0)

    def test_octave_up(self):
        """12 semitoni -> ratio 2.0 (ottava sopra)."""
        vm = make_voice_manager(params={'offset_pitch': 12.0})
        result = vm.get_voice_pitch_multiplier(1, 0.0)
        assert result == pytest.approx(2.0, rel=1e-5)

    def test_octave_down(self):
        """Voice 2 con offset_pitch=12 -> -12 semitoni -> ratio 0.5."""
        vm = make_voice_manager(params={'offset_pitch': 12.0})
        result = vm.get_voice_pitch_multiplier(2, 0.0)
        assert result == pytest.approx(0.5, rel=1e-5)

    def test_semitone_formula(self):
        """Verifica formula generica 2^(n/12) per vari semitoni."""
        vm = make_voice_manager(params={'offset_pitch': 7.0})
        semitones = vm.get_voice_pitch_offset_semitones(1, 0.0)
        expected = 2.0 ** (semitones / 12.0)
        result = vm.get_voice_pitch_multiplier(1, 0.0)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_result_always_positive(self):
        """Il ratio e' sempre positivo (anche semitoni negativi)."""
        vm = make_voice_manager(params={'offset_pitch': 5.0})
        for i in range(6):
            assert vm.get_voice_pitch_multiplier(i, 0.0) > 0.0

    def test_no_pitch_offset_all_ones(self):
        """Senza offset pitch, tutte le voci hanno ratio 1.0."""
        vm = make_voice_manager()
        vm.voice_pitch_offset = None
        for i in range(5):
            assert vm.get_voice_pitch_multiplier(i, 0.0) == pytest.approx(1.0)


# =============================================================================
# 15-16. GET_VOICE_POINTER_OFFSET
# =============================================================================

class TestGetVoicePointerOffset:
    """Test per get_voice_pointer_offset."""

    def test_voice_0_always_zero(self):
        vm = make_voice_manager(params={'pointer_offset': 0.1})
        assert vm.get_voice_pointer_offset(0, 0.0) == pytest.approx(0.0)

    def test_voice_1_positive(self):
        vm = make_voice_manager(params={'pointer_offset': 0.1})
        result = vm.get_voice_pointer_offset(1, 0.0)
        assert result == pytest.approx(0.1)

    def test_voice_2_negative(self):
        vm = make_voice_manager(params={'pointer_offset': 0.1})
        result = vm.get_voice_pointer_offset(2, 0.0)
        assert result == pytest.approx(-0.1)

    def test_none_param_returns_zero(self):
        vm = make_voice_manager()
        vm.voice_pointer_offset = None
        for i in range(5):
            assert vm.get_voice_pointer_offset(i, 0.0) == 0.0

    def test_alternating_sign_pattern(self):
        """Voci dispari positive, pari negative (escl. voice 0)."""
        vm = make_voice_manager(params={'pointer_offset': 0.05})
        assert vm.get_voice_pointer_offset(1, 0.0) > 0
        assert vm.get_voice_pointer_offset(2, 0.0) < 0
        assert vm.get_voice_pointer_offset(3, 0.0) > 0
        assert vm.get_voice_pointer_offset(4, 0.0) < 0


# =============================================================================
# 17. GET_VOICE_POINTER_RANGE
# =============================================================================

class TestGetVoicePointerRange:
    """Test per get_voice_pointer_range."""

    def test_none_returns_zero(self):
        vm = make_voice_manager()
        vm.voice_pointer_range = None
        assert vm.get_voice_pointer_range(0.0) == 0.0

    def test_fixed_value(self):
        vm = make_voice_manager(params={'pointer_range': 0.2})
        result = vm.get_voice_pointer_range(0.0)
        assert result == pytest.approx(0.2)

    def test_zero_param(self):
        vm = make_voice_manager(params={'pointer_range': 0.0})
        assert vm.get_voice_pointer_range(0.0) == pytest.approx(0.0)


# =============================================================================
# 18. IS_VOICE_ACTIVE
# =============================================================================

class TestIsVoiceActive:
    """Test per is_voice_active."""

    def test_voice_0_always_active(self):
        """Voice 0 e' sempre attiva (anche con una sola voce)."""
        vm = make_voice_manager(params={'number': 1})
        assert vm.is_voice_active(0, 0.0) is True

    def test_voice_beyond_active_count_is_inactive(self):
        """Voci con indice >= active_voices sono inattive."""
        vm = make_voice_manager(params={'number': 2})
        # con 2 voci attive: voice 0 e voice 1 attive, voice 2 inattiva
        assert vm.is_voice_active(0, 0.0) is True
        assert vm.is_voice_active(1, 0.0) is True
        assert vm.is_voice_active(2, 0.0) is False

    def test_all_voices_active_when_max(self):
        """Tutte le voci attive quando active==max_voices."""
        n = 4
        vm = make_voice_manager(params={'number': n})
        for i in range(n):
            assert vm.is_voice_active(i, 0.0) is True

    def test_time_parameter_passed(self):
        """Il tempo viene passato correttamente a get_active_voices."""
        vm = make_voice_manager(params={'number': 3})
        # Mocka get_active_voices per registrare il tempo
        called_with = []
        original = vm.get_active_voices
        vm.get_active_voices = lambda t: (called_with.append(t), original(t))[1]
        vm.is_voice_active(0, 7.5)
        assert called_with == [7.5]


# =============================================================================
# 19. BACKWARD COMPATIBILITY PROPERTIES
# =============================================================================

class TestBackwardCompatibilityProperties:
    """Test delle property per ScoreVisualizer."""

    def test_num_voices_value_default(self):
        """num_voices_value ritorna 1 quando None."""
        vm = make_voice_manager()
        vm.num_voices = None
        assert vm.num_voices_value == 1

    def test_num_voices_value_fixed(self):
        """num_voices_value ritorna il valore base."""
        vm = make_voice_manager(params={'number': 4})
        assert vm.num_voices_value == 4

    def test_voice_pitch_offset_value_default(self):
        """voice_pitch_offset_value ritorna 0.0 quando None."""
        vm = make_voice_manager()
        vm.voice_pitch_offset = None
        assert vm.voice_pitch_offset_value == 0.0

    def test_voice_pitch_offset_value_fixed(self):
        vm = make_voice_manager(params={'offset_pitch': 2.0})
        assert vm.voice_pitch_offset_value == pytest.approx(2.0)

    def test_voice_pointer_offset_value_default(self):
        vm = make_voice_manager()
        vm.voice_pointer_offset = None
        assert vm.voice_pointer_offset_value == 0.0

    def test_voice_pointer_offset_value_fixed(self):
        vm = make_voice_manager(params={'pointer_offset': 0.1})
        assert vm.voice_pointer_offset_value == pytest.approx(0.1)

    def test_voice_pointer_range_value_default(self):
        vm = make_voice_manager()
        vm.voice_pointer_range = None
        assert vm.voice_pointer_range_value == 0.0

    def test_voice_pointer_range_value_fixed(self):
        vm = make_voice_manager(params={'pointer_range': 0.3})
        assert vm.voice_pointer_range_value == pytest.approx(0.3)


# =============================================================================
# 20. __REPR__
# =============================================================================

class TestRepr:
    """Test __repr__."""

    def test_repr_contains_max_voices(self):
        vm = make_voice_manager(params={'number': 3})
        r = repr(vm)
        assert 'max_voices=3' in r

    def test_repr_contains_class_name(self):
        vm = make_voice_manager()
        assert 'VoiceManager' in repr(vm)

    def test_repr_contains_pitch_offset(self):
        vm = make_voice_manager(params={'offset_pitch': 2.0})
        r = repr(vm)
        assert 'pitch_offset' in r

    def test_repr_contains_pointer_offset(self):
        vm = make_voice_manager(params={'pointer_offset': 0.05})
        r = repr(vm)
        assert 'pointer_offset' in r

    def test_repr_is_string(self):
        vm = make_voice_manager()
        assert isinstance(repr(vm), str)


# =============================================================================
# 21. PARAMETRIZED - PATTERN ALTERNATO SISTEMATICO
# =============================================================================

class TestVoiceOffsetParametrized:
    """Test sistematico del pattern offset per indici 0-7."""

    @pytest.mark.parametrize("voice_idx,base,expected", [
        (0, 1.0,  0.0),   # voice 0: sempre 0
        (1, 1.0,  1.0),   # dispari: +1 * ceil(1/2)=1
        (2, 1.0, -1.0),   # pari:   -1 * floor(2/2)=1
        (3, 1.0,  2.0),   # dispari: +1 * ceil(3/2)=2
        (4, 1.0, -2.0),   # pari:   -1 * floor(4/2)=2
        (5, 1.0,  3.0),   # dispari: +1 * ceil(5/2)=3
        (6, 1.0, -3.0),   # pari:   -1 * floor(6/2)=3
        (7, 1.0,  4.0),   # dispari: +1 * ceil(7/2)=4
    ])
    def test_offset_pattern(self, voice_idx, base, expected):
        vm = make_voice_manager()
        result = vm._get_voice_offset(voice_idx, base)
        assert result == pytest.approx(expected)

    @pytest.mark.parametrize("base", [0.5, 1.0, 2.0, 7.0])
    def test_voice_0_always_zero_various_bases(self, base):
        vm = make_voice_manager()
        assert vm._get_voice_offset(0, base) == 0.0

    @pytest.mark.parametrize("voice_idx,base,expected", [
        (1, 2.0,  2.0),
        (2, 2.0, -2.0),
        (3, 3.0,  6.0),
        (4, 3.0, -6.0),
    ])
    def test_scaling_with_base(self, voice_idx, base, expected):
        vm = make_voice_manager()
        assert vm._get_voice_offset(voice_idx, base) == pytest.approx(expected)


# =============================================================================
# 22. PARAMETRIZED - PITCH MULTIPLIER
# =============================================================================

class TestPitchMultiplierParametrized:
    """Verifica la formula 2^(n/12) su valori noti."""

    @pytest.mark.parametrize("semitones,expected_ratio", [
        (0,   1.0),
        (12,  2.0),
        (-12, 0.5),
        (7,   2.0 ** (7/12)),
        (3,   2.0 ** (3/12)),
        (-7,  2.0 ** (-7/12)),
    ])
    def test_formula(self, semitones, expected_ratio):
        result = 2.0 ** (semitones / 12.0)
        assert result == pytest.approx(expected_ratio, rel=1e-5)

    def test_pitch_multiplier_uses_formula(self):
        """get_voice_pitch_multiplier usa esattamente 2^(s/12)."""
        vm = make_voice_manager(params={'offset_pitch': 5.0})
        for voice_idx in range(5):
            s = vm.get_voice_pitch_offset_semitones(voice_idx, 0.0)
            expected = 2.0 ** (s / 12.0)
            actual = vm.get_voice_pitch_multiplier(voice_idx, 0.0)
            assert actual == pytest.approx(expected, rel=1e-8)


# =============================================================================
# 23. EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Casi limite e scenari anomali."""

    def test_very_large_voice_index_in_offset(self):
        """Indice voce molto grande non solleva eccezioni."""
        vm = make_voice_manager()
        result = vm._get_voice_offset(100, 1.0)
        # Deve essere un numero finito
        assert math.isfinite(result)

    def test_fractional_base_offset(self):
        """base_offset frazionario mantenuto correttamente."""
        vm = make_voice_manager()
        result = vm._get_voice_offset(1, 0.333)
        assert result == pytest.approx(0.333)

    def test_negative_base_offset(self):
        """base_offset negativo inverte i segni."""
        vm = make_voice_manager()
        # voice 1 con base negativo: positivo ma ribaltato
        result_pos = vm._get_voice_offset(1, 2.0)
        result_neg = vm._get_voice_offset(1, -2.0)
        assert result_pos == pytest.approx(-result_neg)

    def test_active_voices_at_boundary_time(self):
        """get_active_voices con t=0 e t=duration non crasha."""
        ctx = make_stream_context(duration=10.0)
        config = make_stream_config(context=ctx)
        vm = make_voice_manager(params={'number': 2}, config=config)
        assert vm.get_active_voices(0.0) >= 1
        assert vm.get_active_voices(10.0) >= 1

    def test_all_params_none_graceful(self):
        """Tutti i parametri voce a None: nessuna eccezione."""
        vm = make_voice_manager()
        vm.num_voices = None
        vm.voice_pitch_offset = None
        vm.voice_pointer_offset = None
        vm.voice_pointer_range = None

        assert vm.get_active_voices(0.0) == 1
        assert vm.get_voice_pitch_multiplier(1, 0.0) == pytest.approx(1.0)
        assert vm.get_voice_pointer_offset(1, 0.0) == 0.0
        assert vm.get_voice_pointer_range(0.0) == 0.0
        assert vm.is_voice_active(0, 0.0) is True

    def test_config_with_normalized_time_mode(self):
        """VoiceManager funziona con time_mode='normalized'."""
        config = make_stream_config(time_mode='normalized')
        vm = make_voice_manager(params={'number': 3}, config=config)
        assert vm.max_voices == 3

    def test_max_voices_consistent_with_active(self):
        """get_active_voices non supera mai max_voices."""
        vm = make_voice_manager(params={'number': 4})
        for t in (0.0, 2.5, 5.0, 10.0):
            assert vm.get_active_voices(t) <= vm.max_voices