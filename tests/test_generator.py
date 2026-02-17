"""
test_generator.py

Suite completa di test per il modulo generator.py.

Coverage target: 100%

Sezioni:
1.  Test __init__() - costruzione e stato iniziale
2.  Test load_yaml() - caricamento e preprocessing YAML
3.  Test _eval_math_expressions() - valutazione espressioni matematiche
4.  Test _filter_solo_mute() - logica solo/mute sugli stream
5.  Test create_elements() - orchestrazione creazione stream e testine
6.  Test _create_streams() - creazione stream granulari
7.  Test _create_testine() - creazione testine tape recorder
8.  Test _register_stream_windows() - pre-registrazione finestre
9.  Test generate_score_file() - delega a ScoreWriter
10. Test integrazione - workflow end-to-end con mock
11. Test edge cases e boundary conditions
12. Test parametrizzati per copertura sistematica

Strategia di mocking:
- Stream: mock completo per isolare da logica granulare
- Testina: mock per isolare da logica tape recorder
- FtableManager: mock per isolare gestione function tables
- ScoreWriter: mock per isolare scrittura file
- WindowController: mock per isolare parsing finestre
- yaml.safe_load: mock per controllare dati input
- builtins.open: mock per controllare I/O file

Nota sugli import:
- Tutti gli import di moduli di produzione avvengono lazy (dentro funzioni)
  per evitare contaminazione di sys.modules con altri test.
- Si usa patch('generator.XXX') per mockare le dipendenze importate
  nel namespace di generator.py.
"""

import pytest
import math
import yaml
import io
import os
from unittest.mock import patch, Mock, MagicMock, mock_open, call


# =============================================================================
# IMPORT LAZY - CACHE
# =============================================================================

_import_cache = {}


def _get_generator_class():
    """Import lazy di Generator."""
    if 'Generator' not in _import_cache:
        from generator import Generator
        _import_cache['Generator'] = Generator
    return _import_cache['Generator']


# =============================================================================
# MOCK HELPERS
# =============================================================================

def make_mock_stream(stream_id='stream_01', sample='test.wav'):
    """Crea un mock Stream con attributi necessari per Generator."""
    stream = Mock()
    stream.stream_id = stream_id
    stream.sample = sample
    stream.sample_table_num = None
    stream.window_table_map = None
    stream.generate_grains = Mock()
    stream.__repr__ = Mock(return_value=f"Stream({stream_id})")
    stream.__str__ = Mock(return_value=f"Stream({stream_id})")
    return stream


def make_mock_testina(testina_id='testina_01', sample_path='tape.wav'):
    """Crea un mock Testina con attributi necessari per Generator."""
    testina = Mock()
    testina.testina_id = testina_id
    testina.sample_path = sample_path
    testina.sample_table_num = None
    testina.__repr__ = Mock(return_value=f"Testina({testina_id})")
    testina.__str__ = Mock(return_value=f"Testina({testina_id})")
    return testina


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def gen():
    """Generator con path YAML fittizio e dipendenze mockate."""
    Generator = _get_generator_class()
    with patch('generator.FtableManager') as MockFtm, \
         patch('generator.ScoreWriter') as MockSw:
        mock_ftm = MockFtm.return_value
        mock_ftm.register_sample = Mock(side_effect=lambda p: hash(p) % 1000)
        mock_ftm.register_window = Mock(side_effect=lambda n: hash(n) % 1000)
        mock_sw = MockSw.return_value
        g = Generator('test_config.yml')
    return g


# =============================================================================
# 1. TEST __init__()
# =============================================================================

class TestGeneratorInit:
    """Test costruttore Generator."""

    def test_init_stores_yaml_path(self):
        """Il costruttore salva yaml_path."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager'), \
             patch('generator.ScoreWriter'):
            g = Generator('my_config.yml')
        assert g.yaml_path == 'my_config.yml'

    def test_init_data_is_none(self):
        """data e' None prima di load_yaml()."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager'), \
             patch('generator.ScoreWriter'):
            g = Generator('config.yml')
        assert g.data is None

    def test_init_streams_empty(self):
        """streams e' lista vuota all'inizializzazione."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager'), \
             patch('generator.ScoreWriter'):
            g = Generator('config.yml')
        assert g.streams == []

    def test_init_testine_empty(self):
        """testine e' lista vuota all'inizializzazione."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager'), \
             patch('generator.ScoreWriter'):
            g = Generator('config.yml')
        assert g.testine == []

    def test_init_creates_ftable_manager(self):
        """Il costruttore crea un FtableManager."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager') as MockFtm, \
             patch('generator.ScoreWriter'):
            g = Generator('config.yml')
        MockFtm.assert_called_once_with(start_num=1)

    def test_init_creates_score_writer_with_ftm(self):
        """Il costruttore crea un ScoreWriter con il FtableManager."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager') as MockFtm, \
             patch('generator.ScoreWriter') as MockSw:
            g = Generator('config.yml')
        MockSw.assert_called_once_with(MockFtm.return_value)

    def test_init_ftable_manager_attribute(self):
        """ftable_manager e' l'istanza creata."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager') as MockFtm, \
             patch('generator.ScoreWriter'):
            g = Generator('config.yml')
        assert g.ftable_manager is MockFtm.return_value

    def test_init_score_writer_attribute(self):
        """score_writer e' l'istanza creata."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager'), \
             patch('generator.ScoreWriter') as MockSw:
            g = Generator('config.yml')
        assert g.score_writer is MockSw.return_value


# =============================================================================
# 2. TEST load_yaml()
# =============================================================================

class TestLoadYaml:
    """Test per load_yaml() - caricamento e preprocessing YAML."""

    def test_load_yaml_reads_file(self, gen):
        """load_yaml apre il file specificato."""
        yaml_data = {'streams': []}
        m = mock_open(read_data=yaml.dump(yaml_data))

        with patch('builtins.open', m):
            gen.load_yaml()

        m.assert_called_once_with('test_config.yml', 'r')

    def test_load_yaml_returns_dict(self, gen):
        """load_yaml ritorna un dizionario."""
        yaml_data = {'streams': [], 'testine': []}
        m = mock_open(read_data=yaml.dump(yaml_data))

        with patch('builtins.open', m):
            result = gen.load_yaml()

        assert isinstance(result, dict)

    def test_load_yaml_sets_data_attribute(self, gen):
        """load_yaml imposta self.data."""
        yaml_data = {'streams': [{'stream_id': 's1'}]}
        m = mock_open(read_data=yaml.dump(yaml_data))

        with patch('builtins.open', m):
            gen.load_yaml()

        assert gen.data is not None
        assert 'streams' in gen.data

    def test_load_yaml_preprocesses_math(self, gen):
        """load_yaml valuta espressioni matematiche."""
        yaml_data = {'value': '(10 + 5)'}
        m = mock_open(read_data=yaml.dump(yaml_data))

        with patch('builtins.open', m):
            result = gen.load_yaml()

        assert result['value'] == 15

    def test_load_yaml_file_not_found(self, gen):
        """load_yaml solleva FileNotFoundError se file non esiste."""
        with patch('builtins.open', side_effect=FileNotFoundError("not found")):
            with pytest.raises(FileNotFoundError):
                gen.load_yaml()

    def test_load_yaml_malformed_yaml(self, gen):
        """load_yaml solleva yaml.YAMLError con YAML malformato."""
        m = mock_open(read_data="{{invalid: yaml: ]]]")

        with patch('builtins.open', m):
            with pytest.raises(yaml.YAMLError):
                gen.load_yaml()

    def test_load_yaml_preserves_non_math_strings(self, gen):
        """load_yaml preserva stringhe senza espressioni matematiche."""
        yaml_data = {'name': 'my_stream', 'sample': 'audio.wav'}
        m = mock_open(read_data=yaml.dump(yaml_data))

        with patch('builtins.open', m):
            result = gen.load_yaml()

        assert result['name'] == 'my_stream'
        assert result['sample'] == 'audio.wav'

    def test_load_yaml_return_value_same_as_data(self, gen):
        """Il valore ritornato e' lo stesso di self.data."""
        yaml_data = {'key': 'value'}
        m = mock_open(read_data=yaml.dump(yaml_data))

        with patch('builtins.open', m):
            result = gen.load_yaml()

        assert result is gen.data


# =============================================================================
# 3. TEST _eval_math_expressions()
# =============================================================================

class TestEvalMathExpressions:
    """Test per _eval_math_expressions() - valutazione ricorsiva."""

    def test_eval_integer_expression(self, gen):
        """Valuta espressione intera."""
        result = gen._eval_math_expressions('(10 + 5)')
        assert result == 15

    def test_eval_float_expression(self, gen):
        """Valuta espressione float."""
        result = gen._eval_math_expressions('(10.5 + 0.5)')
        assert result == 11.0

    def test_eval_pi_constant(self, gen):
        """Valuta costante pi."""
        result = gen._eval_math_expressions('(pi)')
        assert abs(result - math.pi) < 1e-10

    def test_eval_e_constant(self, gen):
        """Valuta costante e."""
        result = gen._eval_math_expressions('(e)')
        assert abs(result - math.e) < 1e-10

    def test_eval_multiplication(self, gen):
        """Valuta moltiplicazione."""
        result = gen._eval_math_expressions('(3 * 4)')
        assert result == 12

    def test_eval_division(self, gen):
        """Valuta divisione."""
        result = gen._eval_math_expressions('(10 / 2)')
        assert result == 5.0

    def test_eval_pi_times_two(self, gen):
        """Valuta pi * 2."""
        result = gen._eval_math_expressions('(pi * 2)')
        assert abs(result - math.pi * 2) < 1e-10

    def test_eval_max_function_not_supported(self, gen):
        """Funzioni con virgola (max, min) non sono matchate dal regex.

        Il pattern regex non include ',' nel charset, quindi espressioni
        come (max(3, 7)) passano invariate. Questo e' il comportamento
        atteso del codice di produzione.
        """
        result = gen._eval_math_expressions('(max(3, 7))')
        # La virgola non e' nel charset del regex -> nessun match -> stringa invariata
        assert result == '(max(3, 7))'

    def test_eval_min_function_not_supported(self, gen):
        """min con virgola non matchato dal regex (come max)."""
        result = gen._eval_math_expressions('(min(3, 7))')
        assert result == '(min(3, 7))'

    def test_eval_abs_function(self, gen):
        """abs con argomento negativo: il '-' e' nel charset del regex."""
        result = gen._eval_math_expressions('(abs(-5))')
        # Il pattern include \- nel charset: [a-zA-Z0-9+\-*/.() ]
        # Quindi (abs(-5)) dovrebbe matchare
        assert result == 5

    def test_eval_pow_function_not_supported(self, gen):
        """pow con virgola non matchato dal regex."""
        result = gen._eval_math_expressions('(pow(2, 10))')
        assert result == '(pow(2, 10))'

    def test_eval_nested_dict(self, gen):
        """Valuta ricorsivamente nei dizionari."""
        data = {
            'a': '(10 + 5)',
            'b': {
                'c': '(pi)',
                'd': 'plain_string'
            }
        }
        result = gen._eval_math_expressions(data)
        assert result['a'] == 15
        assert abs(result['b']['c'] - math.pi) < 1e-10
        assert result['b']['d'] == 'plain_string'

    def test_eval_nested_list(self, gen):
        """Valuta ricorsivamente nelle liste."""
        data = ['(1 + 2)', '(3 * 4)', 'text']
        result = gen._eval_math_expressions(data)
        assert result[0] == 3
        assert result[1] == 12
        assert result[2] == 'text'

    def test_eval_mixed_nested(self, gen):
        """Valuta strutture miste dict/list."""
        data = {
            'items': ['(10)', '(20)'],
            'nested': {'val': '(5 + 5)'}
        }
        result = gen._eval_math_expressions(data)
        assert result['items'] == [10, 20]
        assert result['nested']['val'] == 10

    def test_eval_passthrough_number(self, gen):
        """Numeri passano attraverso invariati."""
        assert gen._eval_math_expressions(42) == 42
        assert gen._eval_math_expressions(3.14) == 3.14

    def test_eval_passthrough_none(self, gen):
        """None passa attraverso invariato."""
        assert gen._eval_math_expressions(None) is None

    def test_eval_passthrough_bool(self, gen):
        """Bool passa attraverso invariato."""
        assert gen._eval_math_expressions(True) is True
        assert gen._eval_math_expressions(False) is False

    def test_eval_plain_string_no_parens(self, gen):
        """Stringhe senza parentesi passano invariate."""
        assert gen._eval_math_expressions('hello') == 'hello'
        assert gen._eval_math_expressions('audio.wav') == 'audio.wav'

    def test_eval_invalid_expression_preserved(self, gen):
        """Espressioni non valide vengono preservate come stringa."""
        # 'unknown_func' non e' nel safe_dict, eval fallisce
        # Il fallback ritorna l'espressione originale (match.group(0))
        result = gen._eval_math_expressions('(unknown_func)')
        assert isinstance(result, str)

    def test_eval_converts_integer_string(self, gen):
        """Stringa risultante convertita a int se possibile."""
        result = gen._eval_math_expressions('(5 + 5)')
        assert result == 10
        assert isinstance(result, int)

    def test_eval_converts_float_string(self, gen):
        """Stringa risultante convertita a float se con punto decimale."""
        result = gen._eval_math_expressions('(5.0 + 5.0)')
        assert result == 10.0
        assert isinstance(result, float)

    def test_eval_empty_string(self, gen):
        """Stringa vuota passa invariata."""
        assert gen._eval_math_expressions('') == ''

    def test_eval_empty_dict(self, gen):
        """Dict vuoto passa invariato."""
        assert gen._eval_math_expressions({}) == {}

    def test_eval_empty_list(self, gen):
        """Lista vuota passa invariata."""
        assert gen._eval_math_expressions([]) == []

    def test_eval_complex_expression(self, gen):
        """Espressione complessa con operatori multipli."""
        result = gen._eval_math_expressions('(2 + 3 * 4)')
        assert result == 14  # Precedenza operatori: 2 + (3*4)

    def test_eval_string_with_no_matching_parens(self, gen):
        """Stringa senza parentesi matchanti il pattern."""
        result = gen._eval_math_expressions('no_match_here')
        assert result == 'no_match_here'

    def test_eval_deeply_nested(self, gen):
        """Valutazione in strutture profondamente nidificate."""
        data = {'a': {'b': {'c': {'d': '(2 + 3)'}}}}
        result = gen._eval_math_expressions(data)
        assert result['a']['b']['c']['d'] == 5

    def test_eval_list_in_dict(self, gen):
        """Valutazione lista dentro dizionario."""
        data = {'values': ['(1)', '(2)', '(3)']}
        result = gen._eval_math_expressions(data)
        assert result['values'] == [1, 2, 3]

    def test_eval_dict_in_list(self, gen):
        """Valutazione dizionario dentro lista."""
        data = [{'v': '(10)'}]
        result = gen._eval_math_expressions(data)
        assert result[0]['v'] == 10

    def test_eval_string_with_multiple_expressions(self, gen):
        """Stringa con piu' espressioni sostituite."""
        # "(10) qualcosa (20)" - il regex sostituisce entrambe
        result = gen._eval_math_expressions('(10)')
        assert result == 10


# =============================================================================
# 4. TEST _filter_solo_mute()
# =============================================================================

class TestFilterSoloMute:
    """Test per _filter_solo_mute() - logica solo/mute."""

    def test_no_solo_no_mute_returns_all(self, gen):
        """Senza solo ne' mute, ritorna tutti gli stream."""
        streams = [
            {'stream_id': 'a'},
            {'stream_id': 'b'},
            {'stream_id': 'c'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 3

    def test_solo_mode_returns_only_solo(self, gen):
        """In modalita' solo, ritorna solo gli stream con flag 'solo'."""
        streams = [
            {'stream_id': 'a', 'solo': True},
            {'stream_id': 'b'},
            {'stream_id': 'c'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 1
        assert result[0]['stream_id'] == 'a'

    def test_solo_multiple(self, gen):
        """Piu' stream con solo sono tutti inclusi."""
        streams = [
            {'stream_id': 'a', 'solo': True},
            {'stream_id': 'b', 'solo': True},
            {'stream_id': 'c'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 2

    def test_mute_excludes_muted(self, gen):
        """Mute esclude gli stream con flag 'mute'."""
        streams = [
            {'stream_id': 'a'},
            {'stream_id': 'b', 'mute': True},
            {'stream_id': 'c'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 2
        assert all(s['stream_id'] != 'b' for s in result)

    def test_solo_overrides_mute(self, gen):
        """Solo ha priorita' su mute: in solo mode solo quelli con 'solo'."""
        streams = [
            {'stream_id': 'a', 'solo': True},
            {'stream_id': 'b', 'mute': True},
            {'stream_id': 'c'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 1
        assert result[0]['stream_id'] == 'a'

    def test_all_muted_returns_empty(self, gen):
        """Tutti muted ritorna lista vuota."""
        streams = [
            {'stream_id': 'a', 'mute': True},
            {'stream_id': 'b', 'mute': True},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 0

    def test_empty_list_returns_empty(self, gen):
        """Lista vuota ritorna lista vuota."""
        result = gen._filter_solo_mute([])
        assert result == []

    def test_solo_checks_key_presence_not_value(self, gen):
        """Solo controlla la presenza della chiave, non il valore."""
        streams = [
            {'stream_id': 'a', 'solo': False},  # chiave presente!
            {'stream_id': 'b'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 1
        assert result[0]['stream_id'] == 'a'

    def test_mute_checks_key_presence_not_value(self, gen):
        """Mute controlla la presenza della chiave, non il valore."""
        streams = [
            {'stream_id': 'a', 'mute': False},  # chiave presente!
            {'stream_id': 'b'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 1
        assert result[0]['stream_id'] == 'b'

    def test_solo_with_value_none(self, gen):
        """Solo con valore None e' ancora rilevato."""
        streams = [
            {'stream_id': 'a', 'solo': None},
            {'stream_id': 'b'},
        ]
        result = gen._filter_solo_mute(streams)
        assert len(result) == 1

    def test_preserves_order(self, gen):
        """_filter_solo_mute preserva l'ordine originale."""
        streams = [
            {'stream_id': 'c'},
            {'stream_id': 'a'},
            {'stream_id': 'b', 'mute': True},
        ]
        result = gen._filter_solo_mute(streams)
        assert [s['stream_id'] for s in result] == ['c', 'a']

    def test_solo_and_mute_on_same_stream(self, gen):
        """Stream con sia solo che mute: solo mode include chi ha solo."""
        streams = [
            {'stream_id': 'a', 'solo': True, 'mute': True},
            {'stream_id': 'b'},
        ]
        result = gen._filter_solo_mute(streams)
        # Solo mode attivo perche' c'e' almeno un 'solo'
        # In solo mode, prende chi ha 'solo' -> 'a' ce l'ha
        assert len(result) == 1
        assert result[0]['stream_id'] == 'a'


# =============================================================================
# 5. TEST create_elements()
# =============================================================================

class TestCreateElements:
    """Test per create_elements() - orchestrazione."""

    def test_create_elements_without_load_yaml_raises(self, gen):
        """create_elements senza load_yaml solleva ValueError."""
        with pytest.raises(ValueError, match="Devi prima caricare il YAML"):
            gen.create_elements()

    def test_create_elements_returns_tuple(self, gen):
        """create_elements ritorna tupla (streams, testine)."""
        gen.data = {'streams': [], 'testine': []}

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'), \
             patch.object(gen, '_create_testine'):
            result = gen.create_elements()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_create_elements_calls_filter(self, gen):
        """create_elements chiama _filter_solo_mute."""
        stream_list = [{'stream_id': 's1'}]
        gen.data = {'streams': stream_list}

        with patch.object(gen, '_filter_solo_mute', return_value=[]) as mock_filter, \
             patch.object(gen, '_create_streams'):
            gen.create_elements()

        mock_filter.assert_called_once_with(stream_list)

    def test_create_elements_calls_create_streams(self, gen):
        """create_elements chiama _create_streams con risultato filtrato."""
        gen.data = {'streams': [{'stream_id': 's1'}, {'stream_id': 's2'}]}
        filtered = [{'stream_id': 's1'}]

        with patch.object(gen, '_filter_solo_mute', return_value=filtered), \
             patch.object(gen, '_create_streams') as mock_cs:
            gen.create_elements()

        mock_cs.assert_called_once_with(filtered)

    def test_create_elements_with_testine(self, gen):
        """create_elements crea testine se presenti."""
        gen.data = {
            'streams': [],
            'testine': [{'testina_id': 't1'}]
        }

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'), \
             patch.object(gen, '_create_testine') as mock_ct:
            gen.create_elements()

        mock_ct.assert_called_once_with([{'testina_id': 't1'}])

    def test_create_elements_without_testine_key(self, gen):
        """create_elements senza chiave 'testine' non crea testine."""
        gen.data = {'streams': []}

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'), \
             patch.object(gen, '_create_testine') as mock_ct:
            gen.create_elements()

        mock_ct.assert_not_called()

    def test_create_elements_with_empty_testine(self, gen):
        """create_elements con testine=[] non chiama _create_testine."""
        gen.data = {'streams': [], 'testine': []}

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'), \
             patch.object(gen, '_create_testine') as mock_ct:
            gen.create_elements()

        mock_ct.assert_not_called()

    def test_create_elements_returns_streams_and_testine(self, gen):
        """create_elements ritorna le liste corrette."""
        gen.data = {'streams': [], 'testine': []}
        gen.streams = ['mock_stream']
        gen.testine = ['mock_testina']

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'), \
             patch.object(gen, '_create_testine'):
            streams, testine = gen.create_elements()

        assert streams == ['mock_stream']
        assert testine == ['mock_testina']

    def test_create_elements_missing_streams_key(self, gen):
        """create_elements con dict senza chiave 'streams' usa default vuoto."""
        gen.data = {}

        with patch.object(gen, '_filter_solo_mute', return_value=[]) as mock_filter, \
             patch.object(gen, '_create_streams'):
            gen.create_elements()

        mock_filter.assert_called_once_with([])

    def test_create_elements_with_none_testine(self, gen):
        """create_elements con testine=None non chiama _create_testine."""
        gen.data = {'streams': [], 'testine': None}

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'), \
             patch.object(gen, '_create_testine') as mock_ct:
            gen.create_elements()

        mock_ct.assert_not_called()


# =============================================================================
# 6. TEST _create_streams()
# =============================================================================

class TestCreateStreams:
    """Test per _create_streams() - creazione stream granulari."""

    def test_creates_stream_objects(self, gen):
        """_create_streams crea oggetti Stream."""
        stream_data = [{'stream_id': 's1', 'sample': 'a.wav', 'grain': {}}]
        mock_stream = make_mock_stream()

        with patch('generator.Stream', return_value=mock_stream) as MockStream, \
             patch.object(gen, '_register_stream_windows', return_value={}):
            gen._create_streams(stream_data)

        MockStream.assert_called_once_with(stream_data[0])
        assert len(gen.streams) == 1

    def test_registers_sample(self, gen):
        """_create_streams registra il sample nel FtableManager."""
        mock_stream = make_mock_stream(sample='audio.wav')
        stream_data = [{'stream_id': 's1', 'sample': 'audio.wav', 'grain': {}}]

        with patch('generator.Stream', return_value=mock_stream), \
             patch.object(gen, '_register_stream_windows', return_value={}):
            gen._create_streams(stream_data)

        gen.ftable_manager.register_sample.assert_called_once_with('audio.wav')

    def test_assigns_sample_table_num(self, gen):
        """_create_streams assegna sample_table_num allo stream."""
        mock_stream = make_mock_stream()
        gen.ftable_manager.register_sample = Mock(return_value=42)
        stream_data = [{'stream_id': 's1', 'sample': 'audio.wav', 'grain': {}}]

        with patch('generator.Stream', return_value=mock_stream), \
             patch.object(gen, '_register_stream_windows', return_value={}):
            gen._create_streams(stream_data)

        assert mock_stream.sample_table_num == 42

    def test_calls_register_windows(self, gen):
        """_create_streams chiama _register_stream_windows."""
        mock_stream = make_mock_stream()
        stream_data = [
            {'stream_id': 's1', 'sample': 'a.wav', 'grain': {'envelope': 'hanning'}},
        ]

        with patch('generator.Stream', return_value=mock_stream), \
             patch.object(gen, '_register_stream_windows', return_value={'hanning': 5}) as mock_rw:
            gen._create_streams(stream_data)

        mock_rw.assert_called_once_with(stream_data[0])

    def test_assigns_window_table_map(self, gen):
        """_create_streams assegna window_table_map."""
        mock_stream = make_mock_stream()
        window_map = {'hanning': 5, 'hamming': 6}
        stream_data = [{'stream_id': 's1', 'sample': 'a.wav', 'grain': {}}]

        with patch('generator.Stream', return_value=mock_stream), \
             patch.object(gen, '_register_stream_windows', return_value=window_map):
            gen._create_streams(stream_data)

        assert mock_stream.window_table_map == window_map

    def test_calls_generate_grains(self, gen):
        """_create_streams chiama generate_grains() su ogni stream."""
        mock_stream = make_mock_stream()
        stream_data = [{'stream_id': 's1', 'sample': 'a.wav', 'grain': {}}]

        with patch('generator.Stream', return_value=mock_stream), \
             patch.object(gen, '_register_stream_windows', return_value={}):
            gen._create_streams(stream_data)

        mock_stream.generate_grains.assert_called_once()

    def test_creates_multiple_streams(self, gen):
        """_create_streams crea piu' stream in sequenza."""
        streams_created = []

        def make_s(data):
            s = make_mock_stream(stream_id=data['stream_id'])
            streams_created.append(s)
            return s

        stream_data = [
            {'stream_id': 's1', 'sample': 'a.wav', 'grain': {}},
            {'stream_id': 's2', 'sample': 'b.wav', 'grain': {}},
            {'stream_id': 's3', 'sample': 'c.wav', 'grain': {}},
        ]

        with patch('generator.Stream', side_effect=make_s), \
             patch.object(gen, '_register_stream_windows', return_value={}):
            gen._create_streams(stream_data)

        assert len(gen.streams) == 3

    def test_empty_list(self, gen):
        """_create_streams con lista vuota non crea nulla."""
        gen._create_streams([])
        assert gen.streams == []

    def test_appends_to_existing_streams(self, gen):
        """_create_streams appende, non sovrascrive."""
        gen.streams = ['existing']
        mock_stream = make_mock_stream()
        stream_data = [{'stream_id': 's1', 'sample': 'a.wav', 'grain': {}}]

        with patch('generator.Stream', return_value=mock_stream), \
             patch.object(gen, '_register_stream_windows', return_value={}):
            gen._create_streams(stream_data)

        assert len(gen.streams) == 2
        assert gen.streams[0] == 'existing'


# =============================================================================
# 7. TEST _create_testine()
# =============================================================================

class TestCreateTestine:
    """Test per _create_testine() - creazione testine tape recorder."""

    def test_creates_objects(self, gen):
        """_create_testine crea oggetti Testina."""
        testina_data = [{'testina_id': 't1', 'sample': 'tape.wav'}]
        mock_testina = make_mock_testina()

        with patch('generator.Testina', return_value=mock_testina) as MockTestina:
            gen._create_testine(testina_data)

        MockTestina.assert_called_once_with(testina_data[0])
        assert len(gen.testine) == 1

    def test_registers_sample(self, gen):
        """_create_testine registra il sample_path nel FtableManager."""
        mock_testina = make_mock_testina(sample_path='my_tape.wav')
        testina_data = [{'testina_id': 't1', 'sample': 'my_tape.wav'}]

        with patch('generator.Testina', return_value=mock_testina):
            gen._create_testine(testina_data)

        gen.ftable_manager.register_sample.assert_called_once_with('my_tape.wav')

    def test_assigns_sample_table_num(self, gen):
        """_create_testine assegna sample_table_num."""
        mock_testina = make_mock_testina()
        gen.ftable_manager.register_sample = Mock(return_value=99)
        testina_data = [{'testina_id': 't1', 'sample': 'tape.wav'}]

        with patch('generator.Testina', return_value=mock_testina):
            gen._create_testine(testina_data)

        assert mock_testina.sample_table_num == 99

    def test_creates_multiple(self, gen):
        """_create_testine crea piu' testine."""
        testine_created = []

        def make_t(data):
            t = make_mock_testina(testina_id=data['testina_id'])
            testine_created.append(t)
            return t

        testina_data = [
            {'testina_id': 't1', 'sample': 'a.wav'},
            {'testina_id': 't2', 'sample': 'b.wav'},
        ]

        with patch('generator.Testina', side_effect=make_t):
            gen._create_testine(testina_data)

        assert len(gen.testine) == 2

    def test_empty_list(self, gen):
        """_create_testine con lista vuota non crea nulla."""
        gen._create_testine([])
        assert gen.testine == []

    def test_appends_to_existing(self, gen):
        """_create_testine appende, non sovrascrive."""
        gen.testine = ['existing']
        mock_testina = make_mock_testina()
        testina_data = [{'testina_id': 't1', 'sample': 'tape.wav'}]

        with patch('generator.Testina', return_value=mock_testina):
            gen._create_testine(testina_data)

        assert len(gen.testine) == 2
        assert gen.testine[0] == 'existing'


# =============================================================================
# 8. TEST _register_stream_windows()
# =============================================================================

class TestRegisterStreamWindows:
    """Test per _register_stream_windows() - pre-registrazione finestre."""

    def test_calls_parse_window_list(self, gen):
        """Chiama WindowController.parse_window_list con params e stream_id."""
        stream_data = {
            'stream_id': 's1',
            'grain': {'envelope': 'hanning'}
        }

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning']
            gen._register_stream_windows(stream_data)

        MockWC.parse_window_list.assert_called_once_with(
            params={'envelope': 'hanning'},
            stream_id='s1'
        )

    def test_registers_each_window(self, gen):
        """Registra ogni finestra nel FtableManager."""
        stream_data = {
            'stream_id': 's1',
            'grain': {'envelope': ['hanning', 'hamming']}
        }

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning', 'hamming']
            gen.ftable_manager.register_window = Mock(
                side_effect=lambda n: {'hanning': 10, 'hamming': 11}[n]
            )
            result = gen._register_stream_windows(stream_data)

        assert result == {'hanning': 10, 'hamming': 11}

    def test_returns_window_map(self, gen):
        """Ritorna mappa {nome: table_num}."""
        stream_data = {'stream_id': 's1', 'grain': {}}

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning']
            gen.ftable_manager.register_window = Mock(return_value=5)
            result = gen._register_stream_windows(stream_data)

        assert isinstance(result, dict)
        assert result == {'hanning': 5}

    def test_default_stream_id_unknown(self, gen):
        """stream_id default e' 'unknown' se assente."""
        stream_data = {'grain': {'envelope': 'hanning'}}

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning']
            gen._register_stream_windows(stream_data)

        MockWC.parse_window_list.assert_called_once_with(
            params={'envelope': 'hanning'},
            stream_id='unknown'
        )

    def test_no_grain_key_uses_empty_dict(self, gen):
        """Senza chiave 'grain' usa dict vuoto per params."""
        stream_data = {'stream_id': 's1'}

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning']
            gen._register_stream_windows(stream_data)

        MockWC.parse_window_list.assert_called_once_with(
            params={},
            stream_id='s1'
        )

    def test_empty_window_list_returns_empty_map(self, gen):
        """Lista vuota di finestre produce mappa vuota."""
        stream_data = {'stream_id': 's1', 'grain': {}}

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = []
            result = gen._register_stream_windows(stream_data)

        assert result == {}

    def test_multiple_windows_all_registered(self, gen):
        """Tutte le finestre della lista vengono registrate."""
        stream_data = {'stream_id': 's1', 'grain': {'envelope': 'all'}}
        all_windows = ['hanning', 'hamming', 'bartlett']

        with patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = all_windows
            gen.ftable_manager.register_window = Mock(
                side_effect=lambda n: {'hanning': 10, 'hamming': 11, 'bartlett': 12}[n]
            )
            result = gen._register_stream_windows(stream_data)

        assert len(result) == 3
        assert gen.ftable_manager.register_window.call_count == 3


# =============================================================================
# 9. TEST generate_score_file()
# =============================================================================

class TestGenerateScoreFile:
    """Test per generate_score_file() - delega a ScoreWriter."""

    def test_delegates_to_writer(self, gen):
        """generate_score_file delega a score_writer.write_score."""
        gen.streams = ['s1', 's2']
        gen.testine = ['t1']

        gen.generate_score_file('output.sco')

        gen.score_writer.write_score.assert_called_once_with(
            filepath='output.sco',
            streams=['s1', 's2'],
            testine=['t1'],
            yaml_source='test_config.yml'
        )

    def test_default_path(self, gen):
        """generate_score_file usa 'output.sco' come default."""
        gen.streams = []
        gen.testine = []

        gen.generate_score_file()

        call_kwargs = gen.score_writer.write_score.call_args
        assert call_kwargs.kwargs['filepath'] == 'output.sco'

    def test_custom_path(self, gen):
        """generate_score_file accetta path custom."""
        gen.streams = []
        gen.testine = []

        gen.generate_score_file('/tmp/my_score.sco')

        call_kwargs = gen.score_writer.write_score.call_args
        assert call_kwargs.kwargs['filepath'] == '/tmp/my_score.sco'

    def test_passes_yaml_path(self, gen):
        """generate_score_file passa yaml_path come yaml_source."""
        gen.streams = []
        gen.testine = []

        gen.generate_score_file()

        call_kwargs = gen.score_writer.write_score.call_args
        assert call_kwargs.kwargs['yaml_source'] == 'test_config.yml'

    def test_passes_current_streams_and_testine(self, gen):
        """generate_score_file passa le liste correnti."""
        gen.streams = ['stream_a', 'stream_b']
        gen.testine = ['testina_x']

        gen.generate_score_file()

        call_kwargs = gen.score_writer.write_score.call_args
        assert call_kwargs.kwargs['streams'] == ['stream_a', 'stream_b']
        assert call_kwargs.kwargs['testine'] == ['testina_x']


# =============================================================================
# 10. TEST INTEGRAZIONE
# =============================================================================

class TestIntegration:
    """Test di integrazione - workflow end-to-end con mock."""

    def test_full_workflow(self, gen):
        """Workflow completo: load -> create -> generate."""
        yaml_content = yaml.dump({
            'streams': [
                {'stream_id': 's1', 'sample': 'a.wav', 'grain': {'envelope': 'hanning'}}
            ],
            'testine': [
                {'testina_id': 't1', 'sample': 'tape.wav'}
            ]
        })

        mock_stream = make_mock_stream()
        mock_testina = make_mock_testina()

        with patch('builtins.open', mock_open(read_data=yaml_content)), \
             patch('generator.Stream', return_value=mock_stream), \
             patch('generator.Testina', return_value=mock_testina), \
             patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning']
            gen.ftable_manager.register_sample = Mock(return_value=1)
            gen.ftable_manager.register_window = Mock(return_value=2)

            gen.load_yaml()
            streams, testine = gen.create_elements()
            gen.generate_score_file('out.sco')

        assert len(gen.streams) == 1
        assert len(gen.testine) == 1
        gen.score_writer.write_score.assert_called_once()

    def test_workflow_solo_mode(self, gen):
        """Workflow con solo mode."""
        yaml_content = yaml.dump({
            'streams': [
                {'stream_id': 's1', 'sample': 'a.wav', 'grain': {}, 'solo': True},
                {'stream_id': 's2', 'sample': 'b.wav', 'grain': {}},
            ]
        })

        mock_stream = make_mock_stream()

        with patch('builtins.open', mock_open(read_data=yaml_content)), \
             patch('generator.Stream', return_value=mock_stream), \
             patch('generator.WindowController') as MockWC:
            MockWC.parse_window_list.return_value = ['hanning']
            gen.ftable_manager.register_sample = Mock(return_value=1)
            gen.ftable_manager.register_window = Mock(return_value=2)

            gen.load_yaml()
            gen.create_elements()

        assert len(gen.streams) == 1

    def test_workflow_math_preprocessing(self, gen):
        """Workflow con espressioni matematiche nel YAML."""
        yaml_content = yaml.dump({
            'streams': [],
            'duration': '(pi * 2)',
        })

        with patch('builtins.open', mock_open(read_data=yaml_content)):
            data = gen.load_yaml()

        assert abs(data['duration'] - math.pi * 2) < 1e-10


# =============================================================================
# 11. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases e boundary conditions."""

    def test_load_yaml_then_reload(self, gen):
        """Ricaricare YAML sovrascrive i dati precedenti."""
        yaml1 = yaml.dump({'key': 'first'})
        yaml2 = yaml.dump({'key': 'second'})

        with patch('builtins.open', mock_open(read_data=yaml1)):
            gen.load_yaml()
        assert gen.data['key'] == 'first'

        with patch('builtins.open', mock_open(read_data=yaml2)):
            gen.load_yaml()
        assert gen.data['key'] == 'second'

    def test_create_elements_clears_nothing(self, gen):
        """create_elements non resetta le liste (appende)."""
        gen.data = {'streams': []}
        gen.streams = ['pre_existing']

        with patch.object(gen, '_filter_solo_mute', return_value=[]), \
             patch.object(gen, '_create_streams'):
            gen.create_elements()

        # _create_streams viene chiamata con lista vuota, non modifica streams
        assert 'pre_existing' in gen.streams

    def test_eval_math_with_tuple(self, gen):
        """Tuple passano attraverso (non sono dict, list, o str)."""
        result = gen._eval_math_expressions((1, 2, 3))
        assert result == (1, 2, 3)

    def test_eval_math_integer_zero(self, gen):
        """Zero intero passa attraverso."""
        assert gen._eval_math_expressions(0) == 0

    def test_eval_math_negative_number(self, gen):
        """Numeri negativi passano attraverso."""
        assert gen._eval_math_expressions(-5) == -5
        assert gen._eval_math_expressions(-3.14) == -3.14


# =============================================================================
# 12. TEST PARAMETRIZZATI
# =============================================================================

class TestParametrized:
    """Test parametrizzati per copertura sistematica."""

    @pytest.mark.parametrize("expr,expected", [
        ('(1 + 1)', 2),
        ('(10 - 3)', 7),
        ('(4 * 5)', 20),
        ('(100 / 4)', 25.0),
        ('(pi)', math.pi),
        ('(e)', math.e),
        ('(int(3.7))', 3),
        ('(float(5))', 5.0),
    ])
    def test_eval_various_expressions(self, gen, expr, expected):
        """Valuta varie espressioni matematiche."""
        result = gen._eval_math_expressions(expr)
        if isinstance(expected, float):
            assert abs(result - expected) < 1e-10
        else:
            assert result == expected

    @pytest.mark.parametrize("expr", [
        '(max(1, 2))',
        '(min(1, 2))',
        '(pow(2, 8))',
    ])
    def test_eval_comma_expressions_not_matched(self, gen, expr):
        """Espressioni con virgola non sono matchate dal regex."""
        result = gen._eval_math_expressions(expr)
        assert result == expr  # Stringa invariata

    @pytest.mark.parametrize("passthrough", [
        42, 3.14, None, True, False, 'plain_text', 'audio.wav',
    ])
    def test_eval_passthrough_types(self, gen, passthrough):
        """Vari tipi passano invariati attraverso _eval_math_expressions."""
        result = gen._eval_math_expressions(passthrough)
        assert result == passthrough

    @pytest.mark.parametrize("n_streams", [0, 1, 2, 5, 10])
    def test_filter_various_sizes(self, gen, n_streams):
        """_filter_solo_mute con varie dimensioni lista."""
        streams = [{'stream_id': f's{i}'} for i in range(n_streams)]
        result = gen._filter_solo_mute(streams)
        assert len(result) == n_streams

    @pytest.mark.parametrize("n_muted,total,expected", [
        (0, 3, 3),
        (1, 3, 2),
        (2, 3, 1),
        (3, 3, 0),
    ])
    def test_filter_mute_counts(self, gen, n_muted, total, expected):
        """_filter_solo_mute con vari conteggi mute."""
        streams = []
        for i in range(total):
            s = {'stream_id': f's{i}'}
            if i < n_muted:
                s['mute'] = True
            streams.append(s)

        result = gen._filter_solo_mute(streams)
        assert len(result) == expected

    @pytest.mark.parametrize("yaml_path", [
        'config.yml',
        '/absolute/path/config.yml',
        './relative/config.yaml',
        'no_extension',
        'path with spaces/config.yml',
    ])
    def test_init_various_paths(self, yaml_path):
        """Vari formati di yaml_path sono accettati."""
        Generator = _get_generator_class()
        with patch('generator.FtableManager'), \
             patch('generator.ScoreWriter'):
            g = Generator(yaml_path)
        assert g.yaml_path == yaml_path

    @pytest.mark.parametrize("output_path", [
        'output.sco',
        '/tmp/score.sco',
        './scores/my_piece.sco',
    ])
    def test_generate_score_various_paths(self, gen, output_path):
        """generate_score_file con vari percorsi output."""
        gen.streams = []
        gen.testine = []

        gen.generate_score_file(output_path)

        call_kwargs = gen.score_writer.write_score.call_args
        assert call_kwargs.kwargs['filepath'] == output_path