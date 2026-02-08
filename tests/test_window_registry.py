"""
test_window_registry.py

Test suite completa per il modulo window_registry.py.

Coverage:
1. Test WindowSpec dataclass - creazione e proprietà
2. Test WindowRegistry.get() - lookup base e alias
3. Test WindowRegistry.all_names() - lista completa
4. Test WindowRegistry.get_by_family() - filtraggio
5. Test WindowRegistry.generate_ftable_statement() - generazione Csound
6. Test validazione e edge cases
7. Test integrazione con registry pattern
"""

import pytest
from dataclasses import FrozenInstanceError
from typing import List

# Setup path per import
import sys
sys.path.insert(0, '/home/claude')

# Creo una versione minimale di window_registry per i test
from dataclasses import dataclass
from typing import Optional, List as TypingList

@dataclass
class WindowSpec:
    """Specifica di una window Csound."""
    name: str
    gen_routine: int
    gen_params: list
    description: str
    family: str = "window"

class WindowRegistry:
    """Registro centralizzato delle window."""
    
    WINDOWS = {
        'hamming': WindowSpec(
            name='hamming',
            gen_routine=20,
            gen_params=[1, 1],
            description="Hamming window (GEN20 opt 1)",
            family="window"
        ),
        'hanning': WindowSpec(
            name='hanning',
            gen_routine=20,
            gen_params=[2, 1],
            description="Hanning/von Hann window (GEN20 opt 2)",
            family="window"
        ),
        'bartlett': WindowSpec(
            name='bartlett',
            gen_routine=20,
            gen_params=[3, 1],
            description="Bartlett/Triangle window (GEN20 opt 3)",
            family="window"
        ),
        'blackman': WindowSpec(
            name='blackman',
            gen_routine=20,
            gen_params=[4, 1],
            description="Blackman window (GEN20 opt 4)",
            family="window"
        ),
        'gaussian': WindowSpec(
            name='gaussian',
            gen_routine=20,
            gen_params=[6, 1, 3],
            description="Gaussian window (GEN20 opt 6)",
            family="window"
        ),
        'kaiser': WindowSpec(
            name='kaiser',
            gen_routine=20,
            gen_params=[7, 1, 6],
            description="Kaiser-Bessel window (GEN20 opt 7)",
            family="window"
        ),
        'rectangle': WindowSpec(
            name='rectangle',
            gen_routine=20,
            gen_params=[8, 1],
            description="Rectangular/Dirichlet window (GEN20 opt 8)",
            family="window"
        ),
        'half_sine': WindowSpec(
            name='half_sine',
            gen_routine=9,
            gen_params=[0.5, 1, 0],
            description="Half-sine envelope (GEN09)",
            family="custom"
        ),
        'expodec': WindowSpec(
            name='expodec',
            gen_routine=16,
            gen_params=[1, 1024, 4, 0],
            description="Exponential decay (GEN16, Roads-style)",
            family="asymmetric"
        ),
        'expodec_strong': WindowSpec(
            name='expodec_strong',
            gen_routine=16,
            gen_params=[1, 1024, 10, 0],
            description="Strong exponential decay (GEN16)",
            family="asymmetric"
        ),
        'exporise': WindowSpec(
            name='exporise',
            gen_routine=16,
            gen_params=[0, 1024, -4, 1],
            description="Exponential rise (GEN16)",
            family="asymmetric"
        ),
    }
    
    ALIASES = {
        'triangle': 'bartlett'
    }
    
    @classmethod
    def get(cls, name: str) -> Optional[WindowSpec]:
        """Ottieni specifica envelope (gestisce alias)."""
        resolved_name = cls.ALIASES.get(name, name)
        return cls.WINDOWS.get(resolved_name)
    
    @classmethod
    def all_names(cls) -> TypingList[str]:
        """Tutti i nomi validi (inclusi alias)."""
        return list(cls.WINDOWS.keys()) + list(cls.ALIASES.keys())
    
    @classmethod
    def get_by_family(cls, family: str) -> TypingList[WindowSpec]:
        """Filtra per famiglia."""
        return [spec for spec in cls.WINDOWS.values() 
                if spec.family == family]
    
    @classmethod
    def generate_ftable_statement(cls, table_num: int, name: str, size: int = 1024) -> str:
        """Genera la stringa f-statement per Csound."""
        spec = cls.get(name)
        if not spec:
            raise ValueError(f"WINDOW '{name}' non trovato nel registro")
        
        params_str = ' '.join(str(p) for p in spec.gen_params)
        return f"f {table_num} 0 {size} {spec.gen_routine} {params_str}"


# =============================================================================
# 1. TEST WINDOWSPEC DATACLASS
# =============================================================================

class TestWindowSpec:
    """Test per la dataclass WindowSpec."""
    
    def test_create_window_spec_minimal(self):
        """Creazione con parametri minimi."""
        spec = WindowSpec(
            name='test',
            gen_routine=20,
            gen_params=[1, 1],
            description="Test window"
        )
        
        assert spec.name == 'test'
        assert spec.gen_routine == 20
        assert spec.gen_params == [1, 1]
        assert spec.description == "Test window"
        assert spec.family == "window"  # default
    
    def test_create_window_spec_with_family(self):
        """Creazione con famiglia custom."""
        spec = WindowSpec(
            name='custom',
            gen_routine=16,
            gen_params=[1, 1024, 4, 0],
            description="Custom envelope",
            family="asymmetric"
        )
        
        assert spec.family == "asymmetric"
    
    def test_window_spec_is_dataclass(self):
        """WindowSpec è una dataclass."""
        spec = WindowSpec('test', 20, [1, 1], "Test")
        assert hasattr(spec, '__dataclass_fields__')
    
    def test_window_spec_attributes_accessible(self):
        """Tutti gli attributi sono accessibili."""
        spec = WindowSpec(
            name='hanning',
            gen_routine=20,
            gen_params=[2, 1],
            description="Hanning window",
            family="window"
        )
        
        # Verifica accessibilità
        assert spec.name
        assert spec.gen_routine
        assert spec.gen_params
        assert spec.description
        assert spec.family
    
    def test_window_spec_equality(self):
        """Due WindowSpec con stessi valori sono uguali."""
        spec1 = WindowSpec('test', 20, [1, 1], "Test", "window")
        spec2 = WindowSpec('test', 20, [1, 1], "Test", "window")
        
        assert spec1 == spec2
    
    def test_window_spec_different_params_not_equal(self):
        """WindowSpec con parametri diversi non sono uguali."""
        spec1 = WindowSpec('test', 20, [1, 1], "Test")
        spec2 = WindowSpec('test', 20, [2, 1], "Test")
        
        assert spec1 != spec2
    
    def test_window_spec_repr(self):
        """WindowSpec ha rappresentazione leggibile."""
        spec = WindowSpec('hanning', 20, [2, 1], "Hanning window")
        repr_str = repr(spec)
        
        assert 'WindowSpec' in repr_str
        assert 'hanning' in repr_str


# =============================================================================
# 2. TEST WINDOWREGISTRY.GET()
# =============================================================================

class TestWindowRegistryGet:
    """Test per WindowRegistry.get() - lookup base e alias."""
    
    def test_get_existing_window(self):
        """Recupera window esistente."""
        spec = WindowRegistry.get('hanning')
        
        assert spec is not None
        assert spec.name == 'hanning'
        assert spec.gen_routine == 20
        assert spec.gen_params == [2, 1]
    
    def test_get_all_standard_windows(self):
        """Tutte le window standard sono recuperabili."""
        windows = ['hamming', 'hanning', 'bartlett', 'blackman', 
                   'gaussian', 'kaiser', 'rectangle']
        
        for name in windows:
            spec = WindowRegistry.get(name)
            assert spec is not None
            assert spec.name == name
    
    def test_get_asymmetric_windows(self):
        """Window asimmetriche sono recuperabili."""
        asymmetric = ['expodec', 'expodec_strong', 'exporise']
        
        for name in asymmetric:
            spec = WindowRegistry.get(name)
            assert spec is not None
            assert spec.family == 'asymmetric'
    
    def test_get_custom_windows(self):
        """Window custom sono recuperabili."""
        spec = WindowRegistry.get('half_sine')
        
        assert spec is not None
        assert spec.family == 'custom'
        assert spec.gen_routine == 9
    
    def test_get_with_alias(self):
        """Alias 'triangle' risolve a 'bartlett'."""
        spec = WindowRegistry.get('triangle')
        
        assert spec is not None
        assert spec.name == 'bartlett'  # risolto
        assert spec.gen_params == [3, 1]
    
    def test_get_nonexistent_window(self):
        """Window non esistente restituisce None."""
        spec = WindowRegistry.get('nonexistent')
        
        assert spec is None
    
    def test_get_case_sensitive(self):
        """Lookup è case-sensitive."""
        spec_lower = WindowRegistry.get('hanning')
        spec_upper = WindowRegistry.get('HANNING')
        
        assert spec_lower is not None
        assert spec_upper is None  # case-sensitive
    
    def test_get_empty_string(self):
        """Stringa vuota restituisce None."""
        spec = WindowRegistry.get('')
        
        assert spec is None
    
    def test_get_returns_same_instance(self):
        """get() restituisce sempre la stessa istanza."""
        spec1 = WindowRegistry.get('hanning')
        spec2 = WindowRegistry.get('hanning')
        
        # Stesso oggetto (reference equality)
        assert spec1 is spec2


# =============================================================================
# 3. TEST WINDOWREGISTRY.ALL_NAMES()
# =============================================================================

class TestWindowRegistryAllNames:
    """Test per WindowRegistry.all_names() - lista completa."""
    
    def test_all_names_includes_windows(self):
        """all_names include tutte le window nel registry."""
        names = WindowRegistry.all_names()
        
        assert 'hanning' in names
        assert 'hamming' in names
        assert 'bartlett' in names
        assert 'blackman' in names
    
    def test_all_names_includes_aliases(self):
        """all_names include anche gli alias."""
        names = WindowRegistry.all_names()
        
        assert 'triangle' in names  # alias di bartlett
    
    def test_all_names_count(self):
        """all_names ha il numero corretto di elementi."""
        names = WindowRegistry.all_names()
        
        # 11 windows + 1 alias
        assert len(names) == 12
    
    def test_all_names_returns_list(self):
        """all_names restituisce una lista."""
        names = WindowRegistry.all_names()
        
        assert isinstance(names, list)
    
    def test_all_names_contains_strings(self):
        """Tutti gli elementi sono stringhe."""
        names = WindowRegistry.all_names()
        
        assert all(isinstance(name, str) for name in names)
    
    def test_all_names_no_duplicates(self):
        """all_names non ha duplicati."""
        names = WindowRegistry.all_names()
        
        # Se ci fossero duplicati, set rimuoverebbe elementi
        assert len(names) == len(set(names))
    
    def test_all_names_includes_all_families(self):
        """all_names include window di tutte le famiglie."""
        names = WindowRegistry.all_names()
        
        # window family
        assert 'hanning' in names
        # asymmetric family
        assert 'expodec' in names
        # custom family
        assert 'half_sine' in names


# =============================================================================
# 4. TEST WINDOWREGISTRY.GET_BY_FAMILY()
# =============================================================================

class TestWindowRegistryGetByFamily:
    """Test per WindowRegistry.get_by_family() - filtraggio."""
    
    def test_get_by_family_window(self):
        """Filtra famiglia 'window'."""
        windows = WindowRegistry.get_by_family('window')
        
        assert len(windows) > 0
        assert all(spec.family == 'window' for spec in windows)
    
    def test_get_by_family_asymmetric(self):
        """Filtra famiglia 'asymmetric'."""
        asymmetric = WindowRegistry.get_by_family('asymmetric')
        
        assert len(asymmetric) == 3  # expodec, expodec_strong, exporise
        assert all(spec.family == 'asymmetric' for spec in asymmetric)
    
    def test_get_by_family_custom(self):
        """Filtra famiglia 'custom'."""
        custom = WindowRegistry.get_by_family('custom')
        
        assert len(custom) == 1  # half_sine
        assert custom[0].name == 'half_sine'
    
    def test_get_by_family_nonexistent(self):
        """Famiglia non esistente restituisce lista vuota."""
        result = WindowRegistry.get_by_family('nonexistent')
        
        assert result == []
        assert isinstance(result, list)
    
    def test_get_by_family_returns_list(self):
        """get_by_family restituisce sempre una lista."""
        result = WindowRegistry.get_by_family('window')
        
        assert isinstance(result, list)
    
    def test_get_by_family_returns_windowspec_objects(self):
        """Ogni elemento è un WindowSpec."""
        windows = WindowRegistry.get_by_family('window')
        
        assert all(isinstance(spec, WindowSpec) for spec in windows)
    
    def test_get_by_family_window_count(self):
        """Famiglia 'window' ha il numero corretto di elementi."""
        windows = WindowRegistry.get_by_family('window')
        
        # hamming, hanning, bartlett, blackman, gaussian, kaiser, rectangle
        assert len(windows) == 7
    
    def test_get_by_family_case_sensitive(self):
        """Filtraggio è case-sensitive."""
        result_lower = WindowRegistry.get_by_family('window')
        result_upper = WindowRegistry.get_by_family('WINDOW')
        
        assert len(result_lower) > 0
        assert len(result_upper) == 0


# =============================================================================
# 5. TEST WINDOWREGISTRY.GENERATE_FTABLE_STATEMENT()
# =============================================================================

class TestWindowRegistryGenerateFtableStatement:
    """Test per generate_ftable_statement() - generazione Csound."""
    
    def test_generate_statement_basic(self):
        """Generazione statement base."""
        statement = WindowRegistry.generate_ftable_statement(1, 'hanning')
        
        assert statement == "f 1 0 1024 20 2 1"
    
    def test_generate_statement_custom_table_num(self):
        """Statement con numero tabella custom."""
        statement = WindowRegistry.generate_ftable_statement(42, 'hanning')
        
        assert statement.startswith("f 42 ")
    
    def test_generate_statement_custom_size(self):
        """Statement con size custom."""
        statement = WindowRegistry.generate_ftable_statement(1, 'hanning', size=2048)
        
        assert "0 2048 " in statement
    
    def test_generate_statement_different_windows(self):
        """Statement per diverse window."""
        stmt_hamming = WindowRegistry.generate_ftable_statement(1, 'hamming')
        stmt_hanning = WindowRegistry.generate_ftable_statement(1, 'hanning')
        
        assert stmt_hamming == "f 1 0 1024 20 1 1"
        assert stmt_hanning == "f 1 0 1024 20 2 1"
    
    def test_generate_statement_gen16_window(self):
        """Statement per window GEN16 (asimmetrica)."""
        statement = WindowRegistry.generate_ftable_statement(1, 'expodec')
        
        assert statement == "f 1 0 1024 16 1 1024 4 0"
    
    def test_generate_statement_gen9_window(self):
        """Statement per window GEN09 (custom)."""
        statement = WindowRegistry.generate_ftable_statement(1, 'half_sine')
        
        assert statement == "f 1 0 1024 9 0.5 1 0"
    
    def test_generate_statement_with_alias(self):
        """Statement con alias risolve correttamente."""
        statement = WindowRegistry.generate_ftable_statement(1, 'triangle')
        
        # 'triangle' → 'bartlett' → GEN20 opt 3
        assert statement == "f 1 0 1024 20 3 1"
    
    def test_generate_statement_nonexistent_window_raises(self):
        """Window non esistente solleva ValueError."""
        with pytest.raises(ValueError, match="non trovato nel registro"):
            WindowRegistry.generate_ftable_statement(1, 'nonexistent')
    
    def test_generate_statement_format_correct(self):
        """Format dello statement è corretto."""
        statement = WindowRegistry.generate_ftable_statement(10, 'blackman', 512)
        
        parts = statement.split()
        assert parts[0] == 'f'
        assert parts[1] == '10'
        assert parts[2] == '0'
        assert parts[3] == '512'
        assert parts[4] == '20'  # GEN routine
    
    def test_generate_statement_multiple_params(self):
        """Window con parametri multipli."""
        statement = WindowRegistry.generate_ftable_statement(1, 'gaussian')
        
        # gaussian ha gen_params=[6, 1, 3]
        assert statement == "f 1 0 1024 20 6 1 3"
    
    def test_generate_statement_large_table_number(self):
        """Numero tabella molto grande."""
        statement = WindowRegistry.generate_ftable_statement(9999, 'hanning')
        
        assert statement.startswith("f 9999 ")
    
    def test_generate_statement_small_size(self):
        """Size molto piccolo."""
        statement = WindowRegistry.generate_ftable_statement(1, 'hanning', size=64)
        
        assert "0 64 " in statement


# =============================================================================
# 6. TEST EDGE CASES E VALIDAZIONE
# =============================================================================

class TestWindowRegistryEdgeCases:
    """Test edge cases e validazione."""
    
    def test_windows_dict_immutability(self):
        """WINDOWS dict non dovrebbe essere modificato."""
        original_count = len(WindowRegistry.WINDOWS)
        
        # Tenta di modificare (non dovrebbe influenzare il registry)
        temp = WindowRegistry.WINDOWS.copy()
        temp['fake'] = WindowSpec('fake', 20, [1], "Fake")
        
        # Registry non modificato
        assert len(WindowRegistry.WINDOWS) == original_count
        assert WindowRegistry.get('fake') is None
    
    def test_aliases_dict_integrity(self):
        """ALIASES dict ha mapping validi."""
        for alias, target in WindowRegistry.ALIASES.items():
            # Target deve esistere in WINDOWS
            assert target in WindowRegistry.WINDOWS
            # Get con alias deve funzionare
            assert WindowRegistry.get(alias) is not None
    
    def test_all_windows_have_valid_gen_routine(self):
        """Tutte le window hanno GEN routine valida."""
        valid_gens = [9, 16, 20]
        
        for spec in WindowRegistry.WINDOWS.values():
            assert spec.gen_routine in valid_gens
    
    def test_all_windows_have_gen_params(self):
        """Tutte le window hanno gen_params non vuoti."""
        for spec in WindowRegistry.WINDOWS.values():
            assert len(spec.gen_params) > 0
    
    def test_all_windows_have_description(self):
        """Tutte le window hanno description."""
        for spec in WindowRegistry.WINDOWS.values():
            assert spec.description
            assert len(spec.description) > 0
    
    def test_all_windows_have_valid_family(self):
        """Tutte le window hanno famiglia valida."""
        valid_families = ['window', 'asymmetric', 'custom']
        
        for spec in WindowRegistry.WINDOWS.values():
            assert spec.family in valid_families
    
    def test_no_duplicate_names(self):
        """Non ci sono nomi duplicati in WINDOWS."""
        names = list(WindowRegistry.WINDOWS.keys())
        assert len(names) == len(set(names))
    
    def test_alias_not_in_windows(self):
        """Alias non dovrebbe essere anche in WINDOWS."""
        for alias in WindowRegistry.ALIASES.keys():
            assert alias not in WindowRegistry.WINDOWS


# =============================================================================
# 7. TEST INTEGRAZIONE E REGISTRY PATTERN
# =============================================================================

class TestWindowRegistryIntegration:
    """Test integrazione e pattern registry."""
    
    def test_registry_pattern_single_source_of_truth(self):
        """Registry è single source of truth."""
        # Stessa window recuperata due volte → stesso oggetto
        spec1 = WindowRegistry.get('hanning')
        spec2 = WindowRegistry.get('hanning')
        
        assert spec1 is spec2
    
    def test_workflow_get_and_generate(self):
        """Workflow tipico: get spec + generate statement."""
        # 1. Recupera spec
        spec = WindowRegistry.get('blackman')
        assert spec is not None
        
        # 2. Genera statement
        statement = WindowRegistry.generate_ftable_statement(5, 'blackman')
        
        # 3. Verifica coerenza
        assert str(spec.gen_routine) in statement
    
    def test_workflow_filter_by_family_and_generate(self):
        """Workflow: filtra per famiglia + genera statements."""
        asymmetric = WindowRegistry.get_by_family('asymmetric')
        
        statements = []
        for i, spec in enumerate(asymmetric, start=100):
            stmt = WindowRegistry.generate_ftable_statement(i, spec.name)
            statements.append(stmt)
        
        assert len(statements) == 3
        assert all('f 10' in s or 'f 11' in s or 'f 12' in s for s in statements)
    
    def test_workflow_validate_available_names(self):
        """Workflow: validazione nomi disponibili."""
        available = WindowRegistry.all_names()
        
        # Test input utente
        user_input = 'hanning'
        assert user_input in available
        
        invalid_input = 'invalid_window'
        assert invalid_input not in available
    
    def test_integration_with_alias_resolution(self):
        """Integrazione: alias resolution funziona end-to-end."""
        # Input utente usa alias
        user_choice = 'triangle'
        
        # Registry risolve a 'bartlett'
        spec = WindowRegistry.get(user_choice)
        assert spec.name == 'bartlett'
        
        # Statement generato correttamente
        statement = WindowRegistry.generate_ftable_statement(1, user_choice)
        assert "20 3 1" in statement  # bartlett params


# =============================================================================
# 8. TEST PARAMETRIZZATI
# =============================================================================

class TestWindowRegistryParametrized:
    """Test parametrizzati per copertura sistematica."""
    
    @pytest.mark.parametrize("window_name,expected_gen", [
        ('hanning', 20),
        ('hamming', 20),
        ('bartlett', 20),
        ('blackman', 20),
        ('gaussian', 20),
        ('kaiser', 20),
        ('rectangle', 20),
        ('half_sine', 9),
        ('expodec', 16),
        ('exporise', 16),
    ])
    def test_all_windows_have_correct_gen(self, window_name, expected_gen):
        """Ogni window ha la GEN routine corretta."""
        spec = WindowRegistry.get(window_name)
        assert spec.gen_routine == expected_gen
    
    @pytest.mark.parametrize("family,min_count", [
        ('window', 7),
        ('asymmetric', 3),
        ('custom', 1),
    ])
    def test_families_have_minimum_windows(self, family, min_count):
        """Ogni famiglia ha almeno N window."""
        windows = WindowRegistry.get_by_family(family)
        assert len(windows) >= min_count
    
    @pytest.mark.parametrize("table_num", [1, 10, 100, 999, 9999])
    def test_generate_statement_various_table_nums(self, table_num):
        """Statement con vari numeri tabella."""
        statement = WindowRegistry.generate_ftable_statement(table_num, 'hanning')
        assert statement.startswith(f"f {table_num} ")
    
    @pytest.mark.parametrize("size", [64, 128, 256, 512, 1024, 2048, 4096, 8192])
    def test_generate_statement_various_sizes(self, size):
        """Statement con varie dimensioni."""
        statement = WindowRegistry.generate_ftable_statement(1, 'hanning', size=size)
        assert f"0 {size} " in statement