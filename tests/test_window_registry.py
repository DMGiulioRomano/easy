"""
test_window_registry.py

Suite di test completa per src/window_registry.py.

Struttura:
    1. TestWindowSpec              - dataclass WindowSpec
    2. TestWindowRegistryGet       - get(): lookup diretto, alias, case sensitivity
    3. TestWindowRegistryAllNames  - all_names(): completezza, tipi, unicita
    4. TestWindowRegistryGetByFamily - get_by_family(): filtro per famiglia
    5. TestWindowRegistryGenerate  - generate_ftable_statement(): formato, valori, errori
    6. TestWindowRegistryIntegrity - integrita strutturale del registry
    7. TestWindowRegistryIntegration - workflow end-to-end
    8. TestWindowRegistryParametrized - test parametrizzati sistematici

Coverage atteso: 100%

Note sul registry reale (16 WINDOWS + 1 ALIAS = 17 all_names):
    family='window'    (GEN20, 9 voci): hamming, hanning, bartlett, blackman,
                                         blackman_harris, gaussian, kaiser, rectangle, sinc
    family='custom'    (GEN09, 1 voce): half_sine
    family='asymmetric'(GEN16, 6 voci): expodec, expodec_strong, exporise,
                                         exporise_strong, rexpodec, rexporise
    ALIASES: 'triangle' -> 'bartlett'

NOTA TECNICA - ISOLAMENTO DAL MOCKING:
    test_ftable_manager.py usa autouse=True che patcha sys.modules['window_registry']
    con un MockWindowRegistry. Per garantire che questi test usino sempre il modulo
    reale, si usa importlib.util.spec_from_file_location per caricare il sorgente
    direttamente dal path fisico, bypassando sys.modules. La fixture autouse
    'real_registry' aggiorna sys.modules['window_registry'] prima di ogni test.
"""

import pytest
import sys
import os
import importlib
import importlib.util

# ---------------------------------------------------------------------------
# PATH SETUP
# ---------------------------------------------------------------------------
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.normpath(os.path.join(_TEST_DIR, '..', 'src'))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


# ---------------------------------------------------------------------------
# FORCE-LOAD DEL MODULO REALE
# Carica window_registry.py direttamente dal file sorgente, bypassando
# qualsiasi entry in sys.modules (inclusi mock attivi da altri test file).
# ---------------------------------------------------------------------------

def _load_real_window_registry():
    src_path = os.path.join(_SRC_DIR, 'window_registry.py')
    spec = importlib.util.spec_from_file_location('_real_window_registry', src_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_REAL_MODULE = _load_real_window_registry()
_RealWindowSpec = _REAL_MODULE.WindowSpec
_RealWindowRegistry = _REAL_MODULE.WindowRegistry

# Alias usati dai test - puntano sempre al modulo reale
WindowSpec = _RealWindowSpec
WindowRegistry = _RealWindowRegistry


# ---------------------------------------------------------------------------
# FIXTURE AUTOUSE
# Garantisce che sys.modules['window_registry'] punti al modulo reale
# per ogni test, sovrascrivendo eventuali patch attive.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def real_registry(monkeypatch):
    monkeypatch.setitem(sys.modules, 'window_registry', _REAL_MODULE)
    yield _RealWindowRegistry


# ===========================================================================
# COSTANTI DI RIFERIMENTO
# ===========================================================================

EXPECTED_WINDOW_NAMES = {
    'hamming', 'hanning', 'bartlett', 'blackman', 'blackman_harris',
    'gaussian', 'kaiser', 'rectangle', 'sinc',
    'half_sine',
    'expodec', 'expodec_strong', 'exporise', 'exporise_strong',
    'rexpodec', 'rexporise',
}

EXPECTED_FAMILY_WINDOW = {
    'hamming', 'hanning', 'bartlett', 'blackman', 'blackman_harris',
    'gaussian', 'kaiser', 'rectangle', 'sinc'
}
EXPECTED_FAMILY_ASYMMETRIC = {
    'expodec', 'expodec_strong', 'exporise', 'exporise_strong',
    'rexpodec', 'rexporise'
}
EXPECTED_FAMILY_CUSTOM = {'half_sine'}

VALID_GEN_ROUTINES = {9, 16, 20}
VALID_FAMILIES = {'window', 'asymmetric', 'custom'}

EXPECTED_SPECS = {
    'hamming':         (20, [1, 1]),
    'hanning':         (20, [2, 1]),
    'bartlett':        (20, [3, 1]),
    'blackman':        (20, [4, 1]),
    'blackman_harris': (20, [5, 1]),
    'gaussian':        (20, [6, 1, 3]),
    'kaiser':          (20, [7, 1, 6]),
    'rectangle':       (20, [8, 1]),
    'sinc':            (20, [9, 1, 1]),
    'half_sine':       (9,  [0.5, 1, 0]),
    'expodec':         (16, [1, 1024, 4, 0]),
    'expodec_strong':  (16, [1, 1024, 10, 0]),
    'exporise':        (16, [0, 1024, -4, 1]),
    'exporise_strong': (16, [0, 1024, -10, 1]),
    'rexpodec':        (16, [1, 1024, -4, 0]),
    'rexporise':       (16, [0, 1024, 4, 1]),
}


# ===========================================================================
# 1. TEST WINDOWSPEC DATACLASS
# ===========================================================================

class TestWindowSpec:

    def test_create_minimal(self):
        spec = WindowSpec('test', 20, [1, 1], 'Test window')
        assert spec.name == 'test'
        assert spec.gen_routine == 20
        assert spec.gen_params == [1, 1]
        assert spec.description == 'Test window'

    def test_default_family(self):
        spec = WindowSpec('x', 20, [1, 1], 'desc')
        assert spec.family == 'window'

    def test_explicit_family(self):
        spec = WindowSpec('x', 16, [1, 1024, 4, 0], 'Expo', family='asymmetric')
        assert spec.family == 'asymmetric'

    def test_is_dataclass(self):
        spec = WindowSpec('x', 20, [1, 1], 'desc')
        assert hasattr(spec, '__dataclass_fields__')

    def test_equality(self):
        s1 = WindowSpec('hanning', 20, [2, 1], 'Hanning', 'window')
        s2 = WindowSpec('hanning', 20, [2, 1], 'Hanning', 'window')
        assert s1 == s2

    def test_inequality_different_name(self):
        s1 = WindowSpec('hanning', 20, [2, 1], 'desc')
        s2 = WindowSpec('hamming', 20, [1, 1], 'desc')
        assert s1 != s2

    def test_inequality_different_routine(self):
        s1 = WindowSpec('x', 20, [1, 1], 'desc')
        s2 = WindowSpec('x', 16, [1, 1], 'desc')
        assert s1 != s2

    def test_gen_params_is_list(self):
        params = [0.5, 1, 0]
        spec = WindowSpec('x', 9, params, 'desc')
        assert spec.gen_params == params

    def test_repr_contains_name(self):
        spec = WindowSpec('hanning', 20, [2, 1], 'Hanning')
        assert 'hanning' in repr(spec)


# ===========================================================================
# 2. TEST WINDOWREGISTRY.GET()
# ===========================================================================

class TestWindowRegistryGet:

    def test_get_returns_windowspec(self):
        spec = WindowRegistry.get('hanning')
        assert isinstance(spec, _RealWindowSpec)

    def test_get_returns_none_for_unknown(self):
        assert WindowRegistry.get('nonexistent_window') is None

    def test_get_alias_triangle(self):
        spec = WindowRegistry.get('triangle')
        assert spec is not None
        assert spec.name == 'bartlett'

    def test_get_alias_returns_same_as_target(self):
        assert WindowRegistry.get('triangle') is WindowRegistry.get('bartlett')

    def test_get_case_sensitive_upper(self):
        assert WindowRegistry.get('HANNING') is None

    def test_get_case_sensitive_mixed(self):
        assert WindowRegistry.get('Hanning') is None

    def test_get_empty_string(self):
        assert WindowRegistry.get('') is None

    def test_get_returns_correct_name_field(self):
        for name in EXPECTED_WINDOW_NAMES:
            spec = WindowRegistry.get(name)
            assert spec is not None, f"Window '{name}' non trovata"
            assert spec.name == name

    def test_get_idempotent(self):
        assert WindowRegistry.get('blackman') is WindowRegistry.get('blackman')

    @pytest.mark.parametrize("name", sorted(EXPECTED_WINDOW_NAMES))
    def test_get_all_known_windows(self, name):
        assert WindowRegistry.get(name) is not None


# ===========================================================================
# 3. TEST WINDOWREGISTRY.ALL_NAMES()
# ===========================================================================

class TestWindowRegistryAllNames:

    def test_returns_list(self):
        assert isinstance(WindowRegistry.all_names(), list)

    def test_all_elements_are_strings(self):
        assert all(isinstance(n, str) for n in WindowRegistry.all_names())

    def test_total_count(self):
        """16 finestre + 1 alias = 17."""
        assert len(WindowRegistry.all_names()) == 17

    def test_no_duplicates(self):
        names = WindowRegistry.all_names()
        assert len(names) == len(set(names))

    def test_contains_all_window_names(self):
        assert EXPECTED_WINDOW_NAMES.issubset(set(WindowRegistry.all_names()))

    def test_contains_alias(self):
        assert 'triangle' in WindowRegistry.all_names()

    def test_includes_all_families(self):
        names = WindowRegistry.all_names()
        assert 'hanning' in names      # window
        assert 'expodec' in names      # asymmetric
        assert 'half_sine' in names    # custom

    def test_every_name_is_resolvable(self):
        for name in WindowRegistry.all_names():
            assert WindowRegistry.get(name) is not None, \
                f"'{name}' in all_names() ma get() restituisce None"


# ===========================================================================
# 4. TEST WINDOWREGISTRY.GET_BY_FAMILY()
# ===========================================================================

class TestWindowRegistryGetByFamily:

    def test_returns_list(self):
        assert isinstance(WindowRegistry.get_by_family('window'), list)

    def test_elements_are_windowspec(self):
        results = WindowRegistry.get_by_family('window')
        assert all(isinstance(s, _RealWindowSpec) for s in results)

    def test_unknown_family_returns_empty_list(self):
        assert WindowRegistry.get_by_family('nonexistent') == []

    def test_family_case_sensitive(self):
        assert WindowRegistry.get_by_family('WINDOW') == []

    def test_family_window_count(self):
        assert len(WindowRegistry.get_by_family('window')) == 9

    def test_family_window_all_correct(self):
        for spec in WindowRegistry.get_by_family('window'):
            assert spec.family == 'window'

    def test_family_window_names(self):
        names = {s.name for s in WindowRegistry.get_by_family('window')}
        assert names == EXPECTED_FAMILY_WINDOW

    def test_family_asymmetric_count(self):
        assert len(WindowRegistry.get_by_family('asymmetric')) == 6

    def test_family_asymmetric_all_correct(self):
        for spec in WindowRegistry.get_by_family('asymmetric'):
            assert spec.family == 'asymmetric'

    def test_family_asymmetric_names(self):
        names = {s.name for s in WindowRegistry.get_by_family('asymmetric')}
        assert names == EXPECTED_FAMILY_ASYMMETRIC

    def test_family_custom_count(self):
        assert len(WindowRegistry.get_by_family('custom')) == 1

    def test_family_custom_is_half_sine(self):
        assert WindowRegistry.get_by_family('custom')[0].name == 'half_sine'

    def test_sum_of_families_equals_total(self):
        total = (
            len(WindowRegistry.get_by_family('window')) +
            len(WindowRegistry.get_by_family('asymmetric')) +
            len(WindowRegistry.get_by_family('custom'))
        )
        assert total == len(WindowRegistry.WINDOWS)

    def test_families_are_mutually_exclusive(self):
        w = {s.name for s in WindowRegistry.get_by_family('window')}
        a = {s.name for s in WindowRegistry.get_by_family('asymmetric')}
        c = {s.name for s in WindowRegistry.get_by_family('custom')}
        assert w.isdisjoint(a)
        assert w.isdisjoint(c)
        assert a.isdisjoint(c)


# ===========================================================================
# 5. TEST WINDOWREGISTRY.GENERATE_FTABLE_STATEMENT()
# ===========================================================================

class TestWindowRegistryGenerateFtableStatement:
    """
    Formato Csound atteso: "f {table_num} 0 {size} {gen_routine} {params...}"
    Il tempo e' sempre 0 per le tabelle statiche pre-generate a score time.
    """

    def test_hanning_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'hanning') == "f 1 0 1024 20 2 1"

    def test_hamming_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'hamming') == "f 1 0 1024 20 1 1"

    def test_bartlett_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'bartlett') == "f 1 0 1024 20 3 1"

    def test_blackman_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'blackman') == "f 1 0 1024 20 4 1"

    def test_blackman_harris_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'blackman_harris') == "f 1 0 1024 20 5 1"

    def test_gaussian_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'gaussian') == "f 1 0 1024 20 6 1 3"

    def test_kaiser_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'kaiser') == "f 1 0 1024 20 7 1 6"

    def test_rectangle_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'rectangle') == "f 1 0 1024 20 8 1"

    def test_sinc_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'sinc') == "f 1 0 1024 20 9 1 1"

    def test_half_sine_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'half_sine') == "f 1 0 1024 9 0.5 1 0"

    def test_expodec_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'expodec') == "f 1 0 1024 16 1 1024 4 0"

    def test_expodec_strong_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'expodec_strong') == "f 1 0 1024 16 1 1024 10 0"

    def test_exporise_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'exporise') == "f 1 0 1024 16 0 1024 -4 1"

    def test_exporise_strong_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'exporise_strong') == "f 1 0 1024 16 0 1024 -10 1"

    def test_rexpodec_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'rexpodec') == "f 1 0 1024 16 1 1024 -4 0"

    def test_rexporise_default(self):
        assert WindowRegistry.generate_ftable_statement(1, 'rexporise') == "f 1 0 1024 16 0 1024 4 1"

    def test_starts_with_f(self):
        stmt = WindowRegistry.generate_ftable_statement(1, 'hanning')
        assert stmt.startswith('f ')

    def test_time_field_is_zero(self):
        tokens = WindowRegistry.generate_ftable_statement(1, 'hanning').split()
        assert tokens[2] == '0'

    def test_table_num_in_output(self):
        tokens = WindowRegistry.generate_ftable_statement(42, 'hanning').split()
        assert tokens[1] == '42'

    def test_size_in_output(self):
        tokens = WindowRegistry.generate_ftable_statement(1, 'hanning', size=512).split()
        assert tokens[3] == '512'

    def test_gen_routine_in_output(self):
        tokens = WindowRegistry.generate_ftable_statement(1, 'hanning').split()
        assert tokens[4] == '20'

    def test_alias_triangle_generates_bartlett(self):
        stmt_alias = WindowRegistry.generate_ftable_statement(1, 'triangle')
        stmt_direct = WindowRegistry.generate_ftable_statement(1, 'bartlett')
        assert stmt_alias == stmt_direct

    def test_custom_table_num(self):
        assert WindowRegistry.generate_ftable_statement(99, 'hanning').startswith('f 99 ')

    def test_custom_size_2048(self):
        assert '0 2048 ' in WindowRegistry.generate_ftable_statement(1, 'hanning', size=2048)

    def test_custom_size_default_is_1024(self):
        assert '0 1024 ' in WindowRegistry.generate_ftable_statement(1, 'hanning')

    def test_raises_valueerror_for_unknown(self):
        with pytest.raises(ValueError):
            WindowRegistry.generate_ftable_statement(1, 'nonexistent')

    def test_valueerror_message_contains_name(self):
        with pytest.raises(ValueError, match='fake_window'):
            WindowRegistry.generate_ftable_statement(1, 'fake_window')

    def test_raises_for_empty_string(self):
        with pytest.raises(ValueError):
            WindowRegistry.generate_ftable_statement(1, '')


# ===========================================================================
# 6. TEST INTEGRITA STRUTTURALE
# ===========================================================================

class TestWindowRegistryIntegrity:

    def test_windows_dict_not_empty(self):
        assert len(WindowRegistry.WINDOWS) > 0

    def test_windows_total_count(self):
        assert len(WindowRegistry.WINDOWS) == 16

    def test_all_names_have_valid_gen_routine(self):
        for name, spec in WindowRegistry.WINDOWS.items():
            assert spec.gen_routine in VALID_GEN_ROUTINES, \
                f"'{name}' ha gen_routine={spec.gen_routine} non valida"

    def test_all_specs_have_non_empty_gen_params(self):
        for name, spec in WindowRegistry.WINDOWS.items():
            assert len(spec.gen_params) > 0, f"'{name}' ha gen_params vuoto"

    def test_all_specs_have_description(self):
        for name, spec in WindowRegistry.WINDOWS.items():
            assert spec.description, f"'{name}' non ha description"

    def test_all_specs_have_valid_family(self):
        for name, spec in WindowRegistry.WINDOWS.items():
            assert spec.family in VALID_FAMILIES, \
                f"'{name}' ha family='{spec.family}' non valida"

    def test_no_duplicate_keys_in_windows(self):
        keys = list(WindowRegistry.WINDOWS.keys())
        assert len(keys) == len(set(keys))

    def test_aliases_target_exist_in_windows(self):
        for alias, target in WindowRegistry.ALIASES.items():
            assert target in WindowRegistry.WINDOWS, \
                f"Alias '{alias}' punta a '{target}' che non e' in WINDOWS"

    def test_aliases_not_in_windows(self):
        for alias in WindowRegistry.ALIASES:
            assert alias not in WindowRegistry.WINDOWS, \
                f"'{alias}' e' sia in ALIASES che in WINDOWS"

    def test_spec_name_matches_key(self):
        for key, spec in WindowRegistry.WINDOWS.items():
            assert spec.name == key, f"Chiave '{key}' ha spec.name='{spec.name}'"

    def test_gen_params_correct_for_all_windows(self):
        for name, (expected_gen, expected_params) in EXPECTED_SPECS.items():
            spec = WindowRegistry.get(name)
            assert spec is not None, f"'{name}' non trovata"
            assert spec.gen_routine == expected_gen, \
                f"'{name}': gen_routine atteso={expected_gen}, trovato={spec.gen_routine}"
            assert spec.gen_params == expected_params, \
                f"'{name}': gen_params attesi={expected_params}, trovati={spec.gen_params}"

    def test_gen20_windows_have_at_least_two_params(self):
        for name, spec in WindowRegistry.WINDOWS.items():
            if spec.gen_routine == 20:
                assert len(spec.gen_params) >= 2, \
                    f"'{name}' GEN20 ha solo {len(spec.gen_params)} parametro/i"

    def test_gen16_windows_have_four_params(self):
        for name, spec in WindowRegistry.WINDOWS.items():
            if spec.gen_routine == 16:
                assert len(spec.gen_params) == 4, \
                    f"'{name}' GEN16 ha {len(spec.gen_params)} parametri (attesi 4)"

    def test_registry_dict_not_modifiable_at_runtime(self):
        original_count = len(WindowRegistry.WINDOWS)
        local_copy = WindowRegistry.WINDOWS.copy()
        local_copy['injected'] = WindowSpec('injected', 20, [1, 1], 'Fake')
        assert len(WindowRegistry.WINDOWS) == original_count
        assert WindowRegistry.get('injected') is None


# ===========================================================================
# 7. TEST INTEGRAZIONE END-TO-END
# ===========================================================================

class TestWindowRegistryIntegration:

    def test_workflow_lookup_then_generate(self):
        spec = WindowRegistry.get('blackman')
        stmt = WindowRegistry.generate_ftable_statement(5, 'blackman')
        assert stmt.split()[4] == str(spec.gen_routine)

    def test_workflow_filter_family_then_generate_all(self):
        asymmetric = WindowRegistry.get_by_family('asymmetric')
        statements = []
        for i, spec in enumerate(asymmetric, start=10):
            stmt = WindowRegistry.generate_ftable_statement(i, spec.name)
            statements.append(stmt)
            assert stmt.startswith(f'f {i} ')
        assert len(statements) == 6
        assert all('16' in s for s in statements)

    def test_workflow_validate_user_input(self):
        user_choice = 'hanning'
        assert user_choice in WindowRegistry.all_names()
        spec = WindowRegistry.get(user_choice)
        assert spec is not None
        stmt = WindowRegistry.generate_ftable_statement(1, user_choice)
        assert stmt == "f 1 0 1024 20 2 1"

    def test_workflow_alias_resolution_end_to_end(self):
        assert 'triangle' in WindowRegistry.all_names()
        spec = WindowRegistry.get('triangle')
        assert spec.name == 'bartlett'
        stmt = WindowRegistry.generate_ftable_statement(1, 'triangle')
        assert stmt == "f 1 0 1024 20 3 1"

    def test_workflow_size_variation(self):
        for size in [256, 512, 1024, 2048, 4096]:
            stmt = WindowRegistry.generate_ftable_statement(1, 'hanning', size=size)
            assert stmt.split()[3] == str(size)

    def test_workflow_generate_full_ftable_block(self):
        window_family = WindowRegistry.get_by_family('window')
        table_num = 100
        seen = set()
        for spec in window_family:
            stmt = WindowRegistry.generate_ftable_statement(table_num, spec.name)
            assert stmt not in seen, f"Statement duplicato: {stmt}"
            seen.add(stmt)
            table_num += 1

    def test_workflow_error_path(self):
        invalid_name = 'invalid_window'
        assert WindowRegistry.get(invalid_name) is None
        assert invalid_name not in WindowRegistry.all_names()
        with pytest.raises(ValueError):
            WindowRegistry.generate_ftable_statement(1, invalid_name)


# ===========================================================================
# 8. TEST PARAMETRIZZATI SISTEMATICI
# ===========================================================================

class TestWindowRegistryParametrized:

    @pytest.mark.parametrize("name,expected_gen", [
        ('hamming', 20), ('hanning', 20), ('bartlett', 20), ('blackman', 20),
        ('blackman_harris', 20), ('gaussian', 20), ('kaiser', 20),
        ('rectangle', 20), ('sinc', 20),
        ('half_sine', 9),
        ('expodec', 16), ('expodec_strong', 16), ('exporise', 16),
        ('exporise_strong', 16), ('rexpodec', 16), ('rexporise', 16),
    ])
    def test_gen_routine_per_window(self, name, expected_gen):
        spec = WindowRegistry.get(name)
        assert spec is not None
        assert spec.gen_routine == expected_gen

    @pytest.mark.parametrize("name,expected_family", [
        ('hamming', 'window'), ('hanning', 'window'), ('bartlett', 'window'),
        ('blackman', 'window'), ('blackman_harris', 'window'), ('gaussian', 'window'),
        ('kaiser', 'window'), ('rectangle', 'window'), ('sinc', 'window'),
        ('half_sine', 'custom'),
        ('expodec', 'asymmetric'), ('expodec_strong', 'asymmetric'),
        ('exporise', 'asymmetric'), ('exporise_strong', 'asymmetric'),
        ('rexpodec', 'asymmetric'), ('rexporise', 'asymmetric'),
    ])
    def test_family_per_window(self, name, expected_family):
        assert WindowRegistry.get(name).family == expected_family

    @pytest.mark.parametrize("table_num", [1, 10, 50, 100, 500, 999, 9999])
    def test_generate_various_table_nums(self, table_num):
        stmt = WindowRegistry.generate_ftable_statement(table_num, 'hanning')
        assert stmt.startswith(f'f {table_num} ')

    @pytest.mark.parametrize("size", [64, 128, 256, 512, 1024, 2048, 4096, 8192])
    def test_generate_various_sizes(self, size):
        stmt = WindowRegistry.generate_ftable_statement(1, 'hanning', size=size)
        assert stmt.split()[3] == str(size)

    @pytest.mark.parametrize("name", sorted(EXPECTED_WINDOW_NAMES))
    def test_generate_does_not_raise_for_valid_windows(self, name):
        stmt = WindowRegistry.generate_ftable_statement(1, name)
        assert isinstance(stmt, str) and len(stmt) > 0

    @pytest.mark.parametrize("invalid_name", [
        'HANNING', 'Hanning', 'HAMMING', '', '  ', 'triangle_window',
        'gen20', 'GEN20', 'half sine', 'halfSine'
    ])
    def test_get_returns_none_for_invalid_names(self, invalid_name):
        assert WindowRegistry.get(invalid_name) is None

    @pytest.mark.parametrize("invalid_name", [
        'HANNING', 'Hanning', '', 'nonexistent', 'gen20'
    ])
    def test_generate_raises_for_invalid_names(self, invalid_name):
        with pytest.raises(ValueError):
            WindowRegistry.generate_ftable_statement(1, invalid_name)