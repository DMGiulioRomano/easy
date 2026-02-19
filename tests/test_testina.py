# tests/test_testina.py

import pytest
from testina import Testina


# =============================================================================
# HELPERS
# =============================================================================

def make_params(**overrides):
    """Parametri minimi validi per costruire una Testina."""
    base = {
        'testina_id': 'testina_01',
        'onset': 0.0,
        'duration': 5.0,
        'sample': 'refs/audio/sample.wav',
    }
    base.update(overrides)
    return base


def parse_score_line(line):
    """Parsa una score line di TapeRecorder nei suoi campi."""
    # i "TapeRecorder" onset duration start speed volume pan loop_flag loop_start loop_end table
    parts = line.strip().split()
    return {
        'instr':       parts[0],
        'name':        parts[1],
        'onset':       float(parts[2]),
        'duration':    float(parts[3]),
        'start':       float(parts[4]),
        'speed':       float(parts[5]),
        'volume':      float(parts[6]),
        'pan':         float(parts[7]),
        'loop_flag':   int(parts[8]),
        'loop_start':  float(parts[9]),
        'loop_end':    float(parts[10]),
        'table':       int(parts[11]),
    }


# =============================================================================
# 1. TEST __init__ - parametri obbligatori
# =============================================================================

class TestInit:
    """Test costruttore Testina - attributi obbligatori."""

    def test_stores_testina_id(self):
        """testina_id viene salvato correttamente."""
        t = Testina(make_params(testina_id='my_head'))
        assert t.testina_id == 'my_head'

    def test_stores_onset(self):
        """onset viene salvato correttamente."""
        t = Testina(make_params(onset=3.14))
        assert t.onset == 3.14

    def test_stores_duration(self):
        """duration viene salvata correttamente."""
        t = Testina(make_params(duration=12.5))
        assert t.duration == 12.5

    def test_stores_sample_path(self):
        """sample_path viene estratto da 'sample'."""
        t = Testina(make_params(sample='path/to/tape.wav'))
        assert t.sample_path == 'path/to/tape.wav'

    def test_sample_table_num_is_none_at_init(self):
        """sample_table_num e' None prima dell'assegnazione da Generator."""
        t = Testina(make_params())
        assert t.sample_table_num is None


# =============================================================================
# 2. TEST __init__ - valori di default
# =============================================================================

class TestInitDefaults:
    """Test che i parametri opzionali abbiano i valori di default attesi."""

    def test_start_position_default(self):
        """start_position di default e' 0.0."""
        t = Testina(make_params())
        assert t.start_position == 0.0

    def test_speed_default(self):
        """speed di default e' 1.0."""
        t = Testina(make_params())
        assert t.speed == 1.0

    def test_loop_default(self):
        """loop di default e' False."""
        t = Testina(make_params())
        assert t.loop is False

    def test_loop_start_default(self):
        """loop_start di default e' 0.0."""
        t = Testina(make_params())
        assert t.loop_start == 0.0

    def test_loop_end_default(self):
        """loop_end di default e' None (indica fine file)."""
        t = Testina(make_params())
        assert t.loop_end is None

    def test_volume_default(self):
        """volume di default e' 0.0 dB."""
        t = Testina(make_params())
        assert t.volume == 0.0

    def test_pan_default(self):
        """pan di default e' 0.5 (centro)."""
        t = Testina(make_params())
        assert t.pan == 0.5


# =============================================================================
# 3. TEST __init__ - parametri opzionali espliciti
# =============================================================================

class TestInitOptionalParams:
    """Test che i parametri opzionali vengano salvati quando forniti."""

    def test_start_position_explicit(self):
        """start_position viene salvato se fornito."""
        t = Testina(make_params(start_position=2.5))
        assert t.start_position == 2.5

    def test_speed_explicit(self):
        """speed viene salvato se fornito."""
        t = Testina(make_params(speed=0.5))
        assert t.speed == 0.5

    def test_speed_reverse(self):
        """speed negativa (reverse) viene accettata."""
        t = Testina(make_params(speed=-1.0))
        assert t.speed == -1.0

    def test_loop_true(self):
        """loop=True viene salvato."""
        t = Testina(make_params(loop=True))
        assert t.loop is True

    def test_loop_start_explicit(self):
        """loop_start esplicito viene salvato."""
        t = Testina(make_params(loop_start=1.0))
        assert t.loop_start == 1.0

    def test_loop_end_explicit(self):
        """loop_end esplicito viene salvato."""
        t = Testina(make_params(loop_end=4.0))
        assert t.loop_end == 4.0

    def test_volume_negative_db(self):
        """volume negativo (attenuazione) viene salvato."""
        t = Testina(make_params(volume=-12.0))
        assert t.volume == -12.0

    def test_pan_left(self):
        """pan=0.0 (sinistra) viene salvato."""
        t = Testina(make_params(pan=0.0))
        assert t.pan == 0.0

    def test_pan_right(self):
        """pan=1.0 (destra) viene salvato."""
        t = Testina(make_params(pan=1.0))
        assert t.pan == 1.0


# =============================================================================
# 4. TEST to_score_line - struttura generale
# =============================================================================

class TestToScoreLineStructure:
    """Test sulla struttura della score line generata."""

    def test_starts_with_i_statement(self):
        """La score line inizia con 'i'."""
        t = Testina(make_params())
        t.sample_table_num = 1
        line = t.to_score_line()
        assert line.startswith('i')

    def test_contains_instrument_name(self):
        """La score line contiene il nome strumento TapeRecorder."""
        t = Testina(make_params())
        t.sample_table_num = 1
        line = t.to_score_line()
        assert '"TapeRecorder"' in line

    def test_ends_with_newline(self):
        """La score line termina con newline."""
        t = Testina(make_params())
        t.sample_table_num = 1
        line = t.to_score_line()
        assert line.endswith('\n')

    def test_has_eleven_fields_after_instr(self):
        """La score line ha esattamente 12 token totali."""
        t = Testina(make_params())
        t.sample_table_num = 1
        line = t.to_score_line()
        parts = line.strip().split()
        assert len(parts) == 12  # i "TapeRecorder" onset dur start speed vol pan flag ls le table

    def test_returns_string(self):
        """to_score_line ritorna una stringa."""
        t = Testina(make_params())
        t.sample_table_num = 1
        assert isinstance(t.to_score_line(), str)


# =============================================================================
# 5. TEST to_score_line - valori numerici
# =============================================================================

class TestToScoreLineValues:
    """Test che i valori numerici appaiano correttamente nella score line."""

    def test_onset_value(self):
        """onset appare correttamente nella score line."""
        t = Testina(make_params(onset=2.5))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['onset'] == pytest.approx(2.5)

    def test_duration_value(self):
        """duration appare correttamente."""
        t = Testina(make_params(duration=10.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['duration'] == pytest.approx(10.0)

    def test_start_position_value(self):
        """start_position appare nella posizione corretta."""
        t = Testina(make_params(start_position=1.5))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['start'] == pytest.approx(1.5)

    def test_speed_value(self):
        """speed appare correttamente."""
        t = Testina(make_params(speed=2.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['speed'] == pytest.approx(2.0)

    def test_volume_value(self):
        """volume appare correttamente."""
        t = Testina(make_params(volume=-6.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['volume'] == pytest.approx(-6.0)

    def test_pan_value(self):
        """pan appare correttamente."""
        t = Testina(make_params(pan=0.25))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['pan'] == pytest.approx(0.25)

    def test_sample_table_num_in_score(self):
        """sample_table_num assegnato appare nella score line."""
        t = Testina(make_params())
        t.sample_table_num = 42
        parsed = parse_score_line(t.to_score_line())
        assert parsed['table'] == 42


# =============================================================================
# 6. TEST to_score_line - loop semantics
# =============================================================================

class TestToScoreLineLoop:
    """Test sulla gestione del loop nella score line."""

    def test_loop_false_produces_flag_0(self):
        """loop=False genera loop_flag=0."""
        t = Testina(make_params(loop=False))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_flag'] == 0

    def test_loop_true_produces_flag_1(self):
        """loop=True genera loop_flag=1."""
        t = Testina(make_params(loop=True))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_flag'] == 1

    def test_loop_end_none_produces_minus_one(self):
        """loop_end=None produce -1 nella score line (sentinella fine file)."""
        t = Testina(make_params(loop_end=None))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_end'] == pytest.approx(-1.0)

    def test_loop_end_explicit_value(self):
        """loop_end esplicito appare correttamente."""
        t = Testina(make_params(loop_end=3.5))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_end'] == pytest.approx(3.5)

    def test_loop_start_default_in_score(self):
        """loop_start di default (0.0) appare nella score line."""
        t = Testina(make_params())
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_start'] == pytest.approx(0.0)

    def test_loop_start_explicit_in_score(self):
        """loop_start esplicito appare correttamente."""
        t = Testina(make_params(loop_start=2.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_start'] == pytest.approx(2.0)

    def test_loop_start_none_produces_minus_one(self):
        """loop_start=None produce -1 nella score line."""
        t = Testina(make_params(loop_start=None))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_start'] == pytest.approx(-1.0)

    def test_full_loop_configuration(self):
        """Loop completo con start e end espliciti, flag attivo."""
        t = Testina(make_params(loop=True, loop_start=1.0, loop_end=4.0))
        t.sample_table_num = 5
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_flag'] == 1
        assert parsed['loop_start'] == pytest.approx(1.0)
        assert parsed['loop_end'] == pytest.approx(4.0)


# =============================================================================
# 7. TEST to_score_line - formattazione numerica
# =============================================================================

class TestToScoreLineFormatting:
    """Test sulla precisione e formato dei numeri nella score line."""

    def test_onset_six_decimal_places(self):
        """onset e' formattato con 6 cifre decimali."""
        t = Testina(make_params(onset=1.0))
        t.sample_table_num = 1
        line = t.to_score_line()
        # cerca il pattern onset con 6 decimali
        assert '1.000000' in line

    def test_duration_six_decimal_places(self):
        """duration e' formattata con 6 cifre decimali."""
        t = Testina(make_params(duration=5.0))
        t.sample_table_num = 1
        line = t.to_score_line()
        assert '5.000000' in line

    def test_volume_two_decimal_places(self):
        """volume e' formattato con 2 cifre decimali."""
        t = Testina(make_params(volume=0.0))
        t.sample_table_num = 1
        line = t.to_score_line()
        assert '0.00' in line

    def test_pan_three_decimal_places(self):
        """pan e' formattato con 3 cifre decimali."""
        t = Testina(make_params(pan=0.5))
        t.sample_table_num = 1
        line = t.to_score_line()
        assert '0.500' in line

    def test_default_score_line_exact(self):
        """Score line con tutti i default produce output deterministico."""
        t = Testina(make_params(onset=0.0, duration=5.0))
        t.sample_table_num = 1
        expected = (
            'i "TapeRecorder" 0.000000 5.000000 '
            '0.000000 1.000000 '
            '0.00 0.500 '
            '0 0.000000 -1.000000 '
            '1\n'
        )
        assert t.to_score_line() == expected


# =============================================================================
# 8. TEST __repr__
# =============================================================================

class TestRepr:
    """Test sulla rappresentazione stringa della Testina."""

    def test_repr_contains_id(self):
        """__repr__ contiene testina_id."""
        t = Testina(make_params(testina_id='head_A'))
        assert 'head_A' in repr(t)

    def test_repr_contains_onset(self):
        """__repr__ contiene onset."""
        t = Testina(make_params(onset=3.0))
        assert '3.0' in repr(t)

    def test_repr_contains_duration(self):
        """__repr__ contiene duration."""
        t = Testina(make_params(duration=7.5))
        assert '7.5' in repr(t)

    def test_repr_contains_speed(self):
        """__repr__ contiene speed."""
        t = Testina(make_params(speed=0.5))
        assert '0.5' in repr(t)

    def test_repr_returns_string(self):
        """__repr__ ritorna una stringa."""
        t = Testina(make_params())
        assert isinstance(repr(t), str)

    def test_repr_contains_testina_class_name(self):
        """__repr__ contiene il nome della classe."""
        t = Testina(make_params())
        assert 'Testina' in repr(t)


# =============================================================================
# 9. TEST edge cases
# =============================================================================

class TestEdgeCases:
    """Test su valori limite e casi particolari."""

    def test_onset_zero(self):
        """onset=0.0 e' valido."""
        t = Testina(make_params(onset=0.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['onset'] == pytest.approx(0.0)

    def test_very_long_duration(self):
        """Durate molto lunghe vengono gestite correttamente."""
        t = Testina(make_params(duration=3600.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['duration'] == pytest.approx(3600.0)

    def test_speed_zero(self):
        """speed=0.0 (freeze) viene accettata."""
        t = Testina(make_params(speed=0.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['speed'] == pytest.approx(0.0)

    def test_high_table_number(self):
        """Numeri di tabella elevati vengono gestiti correttamente."""
        t = Testina(make_params())
        t.sample_table_num = 9999
        parsed = parse_score_line(t.to_score_line())
        assert parsed['table'] == 9999

    def test_fractional_onset(self):
        """onset frazionario con molti decimali viene gestito."""
        t = Testina(make_params(onset=0.123456789))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['onset'] == pytest.approx(0.123456789, abs=1e-6)

    def test_negative_onset(self):
        """onset negativo (raro ma possibile in Csound) viene passato."""
        t = Testina(make_params(onset=-1.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['onset'] == pytest.approx(-1.0)

    def test_loop_flag_independent_of_start_end(self):
        """loop=False con loop_start/end espliciti produce comunque flag=0."""
        t = Testina(make_params(loop=False, loop_start=1.0, loop_end=3.0))
        t.sample_table_num = 1
        parsed = parse_score_line(t.to_score_line())
        assert parsed['loop_flag'] == 0
        # ma i valori sono comunque scritti
        assert parsed['loop_start'] == pytest.approx(1.0)
        assert parsed['loop_end'] == pytest.approx(3.0)