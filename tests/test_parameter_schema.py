# tests/test_parameter_schema.py
"""
Test suite per parameter_schema.py

Verifica:
- ParameterSpec: costruzione, immutabilità, valori default
- STREAM_PARAMETER_SCHEMA: completezza e coerenza
- Funzioni helper: get_parameter_spec(), get_all_parameter_names()
- Coerenza con parameter_definitions.py (i nomi devono esistere lì)
"""

import pytest
from dataclasses import FrozenInstanceError


# =============================================================================
# IMPORT DEL MODULO DA TESTARE
# =============================================================================

from parameter_schema import (
    ParameterSpec,
    STREAM_PARAMETER_SCHEMA,
    get_parameter_spec,
    get_all_parameter_names
)

# Import per verificare coerenza con il Registry dei bounds
from parameter_definitions import GRANULAR_PARAMETERS


# =============================================================================
# 1. TEST ParameterSpec - COSTRUZIONE E VALORI DEFAULT
# =============================================================================

class TestParameterSpecConstruction:
    """Test costruzione di ParameterSpec."""
    
    def test_minimal_construction(self):
        """Costruzione con soli parametri obbligatori."""
        spec = ParameterSpec(
            name='test_param',
            yaml_path='test.path',
            default=42.0
        )
        
        assert spec.name == 'test_param'
        assert spec.yaml_path == 'test.path'
        assert spec.default == 42.0
    
    def test_default_range_path_is_none(self):
        """range_path default è None."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        assert spec.range_path is None
    
    def test_default_dephase_key_is_none(self):
        """dephase_key default è None."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        assert spec.dephase_key is None
    
    def test_default_is_smart_is_true(self):
        """is_smart default è True (crea Parameter object)."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        assert spec.is_smart is True
    
    def test_full_construction(self):
        """Costruzione con tutti i parametri espliciti."""
        spec = ParameterSpec(
            name='volume',
            yaml_path='output.volume',
            default=-6.0,
            range_path='output.volume_range',
            dephase_key='pc_rand_volume',
            is_smart=True
        )
        
        assert spec.name == 'volume'
        assert spec.yaml_path == 'output.volume'
        assert spec.default == -6.0
        assert spec.range_path == 'output.volume_range'
        assert spec.dephase_key == 'pc_rand_volume'
        assert spec.is_smart is True
    
    def test_is_smart_false_for_raw_values(self):
        """is_smart=False per valori raw (es. stringhe)."""
        spec = ParameterSpec(
            name='grain_envelope',
            yaml_path='grain.envelope',
            default='gaussian',
            is_smart=False
        )
        
        assert spec.is_smart is False
        assert spec.default == 'gaussian'


# =============================================================================
# 2. TEST ParameterSpec - IMMUTABILITÀ (frozen=True)
# =============================================================================

class TestParameterSpecImmutability:
    """ParameterSpec deve essere immutabile (Value Object pattern)."""
    
    def test_cannot_modify_name(self):
        """Tentativo di modifica name deve fallire."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        
        with pytest.raises(FrozenInstanceError):
            spec.name = 'modified'
    
    def test_cannot_modify_yaml_path(self):
        """Tentativo di modifica yaml_path deve fallire."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        
        with pytest.raises(FrozenInstanceError):
            spec.yaml_path = 'modified.path'
    
    def test_cannot_modify_default(self):
        """Tentativo di modifica default deve fallire."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        
        with pytest.raises(FrozenInstanceError):
            spec.default = 999
    
    def test_cannot_modify_is_smart(self):
        """Tentativo di modifica is_smart deve fallire."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        
        with pytest.raises(FrozenInstanceError):
            spec.is_smart = False
    
    def test_hashable(self):
        """ParameterSpec deve essere hashable (usabile in set/dict)."""
        spec = ParameterSpec(name='test', yaml_path='test', default=0)
        
        # Se è hashable, possiamo usarlo in un set
        spec_set = {spec}
        assert spec in spec_set


# =============================================================================
# 3. TEST ParameterSpec - TIPI DI DEFAULT
# =============================================================================

class TestParameterSpecDefaultTypes:
    """Test che default può essere di vari tipi."""
    
    def test_default_float(self):
        """Default può essere float."""
        spec = ParameterSpec(name='vol', yaml_path='vol', default=-6.0)
        assert spec.default == -6.0
        assert isinstance(spec.default, float)
    
    def test_default_int(self):
        """Default può essere int."""
        spec = ParameterSpec(name='voices', yaml_path='voices', default=1)
        assert spec.default == 1
        assert isinstance(spec.default, int)
    
    def test_default_string(self):
        """Default può essere stringa (per parametri non-smart)."""
        spec = ParameterSpec(name='env', yaml_path='env', default='hanning')
        assert spec.default == 'hanning'
        assert isinstance(spec.default, str)
    
    def test_default_none(self):
        """Default può essere None."""
        spec = ParameterSpec(name='opt', yaml_path='opt', default=None)
        assert spec.default is None


# =============================================================================
# 4. TEST STREAM_PARAMETER_SCHEMA - STRUTTURA
# =============================================================================

class TestSchemaStructure:
    """Test struttura dello schema."""
    
    def test_schema_is_list(self):
        """Lo schema deve essere una lista."""
        assert isinstance(STREAM_PARAMETER_SCHEMA, list)
    
    def test_schema_not_empty(self):
        """Lo schema non deve essere vuoto."""
        assert len(STREAM_PARAMETER_SCHEMA) > 0
    
    def test_all_entries_are_parameter_spec(self):
        """Ogni entry deve essere un ParameterSpec."""
        for entry in STREAM_PARAMETER_SCHEMA:
            assert isinstance(entry, ParameterSpec), \
                f"Entry non è ParameterSpec: {entry}"
    
    def test_no_duplicate_names(self):
        """Non ci devono essere nomi duplicati."""
        names = [spec.name for spec in STREAM_PARAMETER_SCHEMA]
        duplicates = [n for n in names if names.count(n) > 1]
        
        assert len(duplicates) == 0, \
            f"Nomi duplicati trovati: {set(duplicates)}"


# =============================================================================
# 5. TEST STREAM_PARAMETER_SCHEMA - COERENZA CON GRANULAR_PARAMETERS
# =============================================================================

class TestSchemaCoherenceWithBounds:
    """
    Verifica che ogni parametro 'smart' nello schema abbia
    i corrispondenti bounds in GRANULAR_PARAMETERS.
    """
    
    def test_smart_params_have_bounds(self):
        """Ogni parametro con is_smart=True deve avere bounds definiti."""
        missing = []
        
        for spec in STREAM_PARAMETER_SCHEMA:
            if spec.is_smart:
                if spec.name not in GRANULAR_PARAMETERS:
                    missing.append(spec.name)
        
        assert len(missing) == 0, \
            f"Parametri smart senza bounds in GRANULAR_PARAMETERS: {missing}"
    
    def test_non_smart_params_can_skip_bounds(self):
        """Parametri con is_smart=False possono non avere bounds."""
        # Questo test verifica che il sistema permette parametri raw
        # come 'grain_envelope' che sono stringhe e non hanno bounds
        
        non_smart = [s for s in STREAM_PARAMETER_SCHEMA if not s.is_smart]
        
        # Almeno uno dovrebbe esistere (grain_envelope)
        # e potrebbe non avere bounds (verifichiamo che non crashi)
        for spec in non_smart:
            # Non deve sollevare errore se manca dai bounds
            exists_in_bounds = spec.name in GRANULAR_PARAMETERS
            # Può esistere o no, non è un errore
            assert isinstance(exists_in_bounds, bool)


# =============================================================================
# 6. TEST STREAM_PARAMETER_SCHEMA - PARAMETRI ATTESI
# =============================================================================

class TestSchemaExpectedParameters:
    """Verifica che i parametri attesi siano presenti."""
    
    # Parametri che DEVONO esistere nello schema
    REQUIRED_PARAMS = [
        'volume',
        'pan',
        'grain_duration',
        'grain_envelope',
    ]
    
    @pytest.mark.parametrize("param_name", REQUIRED_PARAMS)
    def test_required_param_exists(self, param_name):
        """Ogni parametro richiesto deve esistere nello schema."""
        names = [spec.name for spec in STREAM_PARAMETER_SCHEMA]
        assert param_name in names, \
            f"Parametro richiesto '{param_name}' mancante dallo schema!"
    
    def test_volume_has_range_and_dephase(self):
        """Volume deve avere range_path e dephase_key."""
        spec = get_parameter_spec('volume')
        
        assert spec.range_path is not None, "volume deve avere range_path"
        assert spec.dephase_key is not None, "volume deve avere dephase_key"
    
    def test_pan_has_range_and_dephase(self):
        """Pan deve avere range_path e dephase_key."""
        spec = get_parameter_spec('pan')
        
        assert spec.range_path is not None, "pan deve avere range_path"
        assert spec.dephase_key is not None, "pan deve avere dephase_key"
    
    def test_grain_envelope_is_not_smart(self):
        """grain_envelope deve essere is_smart=False (è una stringa)."""
        spec = get_parameter_spec('grain_envelope')
        
        assert spec.is_smart is False


# =============================================================================
# 7. TEST YAML PATH - DOT NOTATION
# =============================================================================

class TestYamlPathFormat:
    """Test sul formato dei percorsi YAML."""
    
    def test_simple_path(self):
        """Percorsi semplici (senza dot) sono validi."""
        spec = get_parameter_spec('volume')
        assert '.' not in spec.yaml_path or spec.yaml_path.count('.') >= 0
    
    def test_nested_path(self):
        """Percorsi nested (con dot) sono validi per grain.*"""
        spec = get_parameter_spec('grain_duration')
        
        # Deve essere un path nested tipo 'grain.duration'
        assert '.' in spec.yaml_path
        assert spec.yaml_path.startswith('grain.')
    
    def test_all_paths_are_strings(self):
        """Tutti i yaml_path devono essere stringhe non vuote."""
        for spec in STREAM_PARAMETER_SCHEMA:
            assert isinstance(spec.yaml_path, str), \
                f"{spec.name}: yaml_path non è stringa"
            assert len(spec.yaml_path) > 0, \
                f"{spec.name}: yaml_path è vuoto"
    
    def test_range_paths_are_strings_or_none(self):
        """range_path deve essere stringa o None."""
        for spec in STREAM_PARAMETER_SCHEMA:
            if spec.range_path is not None:
                assert isinstance(spec.range_path, str), \
                    f"{spec.name}: range_path non è stringa"


# =============================================================================
# 8. TEST get_parameter_spec()
# =============================================================================

class TestGetParameterSpec:
    """Test della funzione di accesso allo schema."""
    
    def test_returns_correct_spec(self):
        """Deve restituire la spec corretta per un nome esistente."""
        spec = get_parameter_spec('volume')
        
        assert spec.name == 'volume'
        assert isinstance(spec, ParameterSpec)
    
    def test_raises_keyerror_for_unknown(self):
        """Deve sollevare KeyError per parametro inesistente."""
        with pytest.raises(KeyError) as excinfo:
            get_parameter_spec('parametro_inventato_xyz')
        
        assert 'parametro_inventato_xyz' in str(excinfo.value)
    
    def test_returns_same_object(self):
        """Deve restituire lo stesso oggetto (no copia)."""
        spec1 = get_parameter_spec('pan')
        spec2 = get_parameter_spec('pan')
        
        assert spec1 is spec2  # Identity check
    
    @pytest.mark.parametrize("param_name", ['volume', 'pan', 'grain_duration'])
    def test_common_params_accessible(self, param_name):
        """I parametri comuni devono essere accessibili."""
        spec = get_parameter_spec(param_name)
        assert spec.name == param_name


# =============================================================================
# 9. TEST get_all_parameter_names()
# =============================================================================

class TestGetAllParameterNames:
    """Test della funzione che ritorna tutti i nomi."""
    
    def test_returns_list(self):
        """Deve ritornare una lista."""
        names = get_all_parameter_names()
        assert isinstance(names, list)
    
    def test_returns_strings(self):
        """Deve ritornare lista di stringhe."""
        names = get_all_parameter_names()
        for name in names:
            assert isinstance(name, str)
    
    def test_count_matches_schema(self):
        """Il numero di nomi deve corrispondere allo schema."""
        names = get_all_parameter_names()
        assert len(names) == len(STREAM_PARAMETER_SCHEMA)
    
    def test_contains_expected_params(self):
        """Deve contenere i parametri attesi."""
        names = get_all_parameter_names()
        
        assert 'volume' in names
        assert 'pan' in names
        assert 'grain_duration' in names
    
    def test_no_duplicates(self):
        """Non deve contenere duplicati."""
        names = get_all_parameter_names()
        assert len(names) == len(set(names))


# =============================================================================
# 10. TEST CASI EDGE
# =============================================================================

class TestEdgeCases:
    """Test casi limite e situazioni particolari."""
    
    def test_spec_with_none_default(self):
        """ParameterSpec può avere default=None."""
        spec = ParameterSpec(
            name='optional',
            yaml_path='optional',
            default=None
        )
        assert spec.default is None
    
    def test_spec_equality(self):
        """Due ParameterSpec con stessi valori devono essere uguali."""
        spec1 = ParameterSpec(name='test', yaml_path='test', default=0)
        spec2 = ParameterSpec(name='test', yaml_path='test', default=0)
        
        assert spec1 == spec2
    
    def test_spec_inequality(self):
        """Due ParameterSpec con valori diversi devono essere diversi."""
        spec1 = ParameterSpec(name='test1', yaml_path='test', default=0)
        spec2 = ParameterSpec(name='test2', yaml_path='test', default=0)
        
        assert spec1 != spec2
    
    def test_empty_yaml_path_not_allowed_in_practice(self):
        """
        Anche se tecnicamente possibile, yaml_path vuoto non ha senso.
        Questo test documenta il comportamento.
        """
        # Costruzione tecnicamente possibile ma semanticamente sbagliata
        spec = ParameterSpec(name='bad', yaml_path='', default=0)
        assert spec.yaml_path == ''  # Permesso ma sconsigliato

# =============================================================================
# 11. TEST POINTER_PARAMETER_SCHEMA
# =============================================================================

class TestPointerParameterSchema:
    """Test per lo schema dei parametri Pointer."""
    
    def test_schema_is_list(self):
        """Lo schema deve essere una lista."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        assert isinstance(POINTER_PARAMETER_SCHEMA, list)
    
    def test_schema_not_empty(self):
        """Lo schema non deve essere vuoto."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        assert len(POINTER_PARAMETER_SCHEMA) > 0
    
    def test_all_entries_are_parameter_spec(self):
        """Ogni entry deve essere un ParameterSpec."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        for entry in POINTER_PARAMETER_SCHEMA:
            assert isinstance(entry, ParameterSpec)
    
    def test_no_duplicate_names(self):
        """Non ci devono essere nomi duplicati."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        names = [spec.name for spec in POINTER_PARAMETER_SCHEMA]
        assert len(names) == len(set(names))
    
    def test_required_params_exist(self):
        """Parametri richiesti devono esistere."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        names = [spec.name for spec in POINTER_PARAMETER_SCHEMA]
        
        assert 'pointer_start' in names
        assert 'pointer_speed' in names
        assert 'pointer_deviation' in names

    def test_pointer_start_is_not_smart(self):
        """pointer_start deve essere is_smart=False (valore raw)."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        spec = next(s for s in POINTER_PARAMETER_SCHEMA if s.name == 'pointer_start')
        
        assert spec.is_smart is False
    
    def test_other_pointer_params_are_smart(self):
        """Altri parametri pointer devono essere is_smart=True."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        
        for spec in POINTER_PARAMETER_SCHEMA:
            if spec.name != 'pointer_start':
                assert spec.is_smart is True, f"{spec.name} dovrebbe essere smart"
    
    def test_smart_params_have_bounds(self):
        """Parametri smart devono avere bounds in GRANULAR_PARAMETERS."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        
        for spec in POINTER_PARAMETER_SCHEMA:
            if spec.is_smart:
                assert spec.name in GRANULAR_PARAMETERS, \
                    f"'{spec.name}' manca da GRANULAR_PARAMETERS"
    
    def test_default_values(self):
        """Verifica valori default corretti."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        
        defaults = {s.name: s.default for s in POINTER_PARAMETER_SCHEMA}
        
        assert defaults['pointer_start'] == 0.0
        assert defaults['pointer_speed'] == 1.0
        assert defaults['pointer_deviation'] == 0.0

    def test_pointer_deviation_has_range_path_and_dephase(self):
        """pointer_deviation deve avere range_path e dephase_key."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        spec = next(s for s in POINTER_PARAMETER_SCHEMA if s.name == 'pointer_deviation')
        
        assert spec.range_path == 'offset_range'
        assert spec.dephase_key == 'pc_rand_pointer'
# =============================================================================
# 12. TEST PITCH_PARAMETER_SCHEMA
# =============================================================================

class TestPitchParameterSchema:
    """Test per lo schema dei parametri Pitch."""
    
    def test_schema_is_list(self):
        """Lo schema deve essere una lista."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        assert isinstance(PITCH_PARAMETER_SCHEMA, list)
    
    def test_schema_not_empty(self):
        """Lo schema non deve essere vuoto."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        assert len(PITCH_PARAMETER_SCHEMA) > 0
    
    def test_all_entries_are_parameter_spec(self):
        """Ogni entry deve essere un ParameterSpec."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        for entry in PITCH_PARAMETER_SCHEMA:
            assert isinstance(entry, ParameterSpec)
    
    def test_no_duplicate_names(self):
        """Non ci devono essere nomi duplicati."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        names = [spec.name for spec in PITCH_PARAMETER_SCHEMA]
        assert len(names) == len(set(names))
    
    def test_required_params_exist(self):
        """Parametri richiesti devono esistere."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        names = [spec.name for spec in PITCH_PARAMETER_SCHEMA]
        
        assert 'pitch_ratio' in names
        assert 'pitch_semitones' in names
        assert 'pitch_range' in names
    
    def test_mutually_exclusive_defaults(self):
        """pitch_semitones ha default=None (mutuamente esclusivo con ratio)."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        
        ratio_spec = next(s for s in PITCH_PARAMETER_SCHEMA if s.name == 'pitch_ratio')
        semi_spec = next(s for s in PITCH_PARAMETER_SCHEMA if s.name == 'pitch_semitones')
        
        # ratio ha default, semitones è None (indica "non presente")
        assert ratio_spec.default == 1.0
        assert semi_spec.default is None
    

    def test_smart_params_have_bounds(self):
        """Parametri smart con default non-None devono avere bounds."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        
        for spec in PITCH_PARAMETER_SCHEMA:
            if spec.is_smart and spec.default is not None:
                assert spec.name in GRANULAR_PARAMETERS, \
                    f"'{spec.name}' manca da GRANULAR_PARAMETERS"
    
    def test_default_values(self):
        """Verifica valori default corretti."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        
        defaults = {s.name: s.default for s in PITCH_PARAMETER_SCHEMA}
        
        assert defaults['pitch_ratio'] == 1.0
        assert defaults['pitch_semitones'] is None
        assert defaults['pitch_range'] == 0.0


# =============================================================================
# 13. TEST DENSITY_PARAMETER_SCHEMA
# =============================================================================

class TestDensityParameterSchema:
    """Test per lo schema dei parametri Density."""
    
    def test_schema_is_list(self):
        """Lo schema deve essere una lista."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        assert isinstance(DENSITY_PARAMETER_SCHEMA, list)
    
    def test_schema_not_empty(self):
        """Lo schema non deve essere vuoto."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        assert len(DENSITY_PARAMETER_SCHEMA) > 0
    
    def test_all_entries_are_parameter_spec(self):
        """Ogni entry deve essere un ParameterSpec."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        for entry in DENSITY_PARAMETER_SCHEMA:
            assert isinstance(entry, ParameterSpec)
    
    def test_no_duplicate_names(self):
        """Non ci devono essere nomi duplicati."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        names = [spec.name for spec in DENSITY_PARAMETER_SCHEMA]
        assert len(names) == len(set(names))
    
    def test_required_params_exist(self):
        """Parametri richiesti devono esistere."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        names = [spec.name for spec in DENSITY_PARAMETER_SCHEMA]
        
        assert 'fill_factor' in names
        assert 'density' in names
        assert 'distribution' in names
    
    def test_mutually_exclusive_defaults(self):
        """fill_factor e density hanno default=None (mutuamente esclusivi)."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        
        ff_spec = next(s for s in DENSITY_PARAMETER_SCHEMA if s.name == 'fill_factor')
        dens_spec = next(s for s in DENSITY_PARAMETER_SCHEMA if s.name == 'density')
        
        # Entrambi None: la logica di default (fill_factor=2.0) è nel Controller
        assert ff_spec.default is None
        assert dens_spec.default is None
    
    def test_distribution_has_default(self):
        """distribution ha un default valido (0.0 = sincrono)."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        
        dist_spec = next(s for s in DENSITY_PARAMETER_SCHEMA if s.name == 'distribution')
        assert dist_spec.default == 0.0
    
    def test_all_params_are_smart(self):
        """Tutti i parametri density devono essere smart."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        
        for spec in DENSITY_PARAMETER_SCHEMA:
            assert spec.is_smart is True, f"{spec.name} dovrebbe essere smart"
    
    def test_distribution_has_bounds(self):
        """distribution deve avere bounds in GRANULAR_PARAMETERS."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        
        dist_spec = next(s for s in DENSITY_PARAMETER_SCHEMA if s.name == 'distribution')
        assert dist_spec.name in GRANULAR_PARAMETERS


# =============================================================================
# 14. TEST VOICE_PARAMETER_SCHEMA
# =============================================================================

class TestVoiceParameterSchema:
    """Test per lo schema dei parametri Voice."""
    
    def test_schema_is_list(self):
        """Lo schema deve essere una lista."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        assert isinstance(VOICE_PARAMETER_SCHEMA, list)
    
    def test_schema_not_empty(self):
        """Lo schema non deve essere vuoto."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        assert len(VOICE_PARAMETER_SCHEMA) > 0
    
    def test_all_entries_are_parameter_spec(self):
        """Ogni entry deve essere un ParameterSpec."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        for entry in VOICE_PARAMETER_SCHEMA:
            assert isinstance(entry, ParameterSpec)
    
    def test_no_duplicate_names(self):
        """Non ci devono essere nomi duplicati."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        names = [spec.name for spec in VOICE_PARAMETER_SCHEMA]
        assert len(names) == len(set(names))
    
    def test_required_params_exist(self):
        """Parametri richiesti devono esistere."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        names = [spec.name for spec in VOICE_PARAMETER_SCHEMA]
        
        assert 'num_voices' in names
        assert 'voice_pitch_offset' in names
        assert 'voice_pointer_offset' in names
        assert 'voice_pointer_range' in names
    
    def test_all_params_are_smart(self):
        """Tutti i parametri voice devono essere smart."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        
        for spec in VOICE_PARAMETER_SCHEMA:
            assert spec.is_smart is True, f"{spec.name} dovrebbe essere smart"
    
    def test_smart_params_have_bounds(self):
        """Parametri smart devono avere bounds in GRANULAR_PARAMETERS."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        
        for spec in VOICE_PARAMETER_SCHEMA:
            if spec.is_smart:
                assert spec.name in GRANULAR_PARAMETERS, \
                    f"'{spec.name}' manca da GRANULAR_PARAMETERS"
    
    def test_default_values(self):
        """Verifica valori default corretti."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        
        defaults = {s.name: s.default for s in VOICE_PARAMETER_SCHEMA}
        
        assert defaults['num_voices'] == 1
        assert defaults['voice_pitch_offset'] == 0.0
        assert defaults['voice_pointer_offset'] == 0.0
        assert defaults['voice_pointer_range'] == 0.0
    
    def test_yaml_paths_match_yaml_structure(self):
        """yaml_path deve corrispondere alla struttura YAML (sotto 'voices')."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        
        # Verifica che i path siano semplici (non nested) perché
        # il blocco 'voices' è già estratto prima di passare allo schema
        for spec in VOICE_PARAMETER_SCHEMA:
            assert '.' not in spec.yaml_path, \
                f"{spec.name}: yaml_path non dovrebbe essere nested"


# =============================================================================
# 15. TEST ALL_SCHEMAS REGISTRY
# =============================================================================

class TestAllSchemasRegistry:
    """Test per il registry ALL_SCHEMAS."""
    
    def test_all_schemas_is_dict(self):
        """ALL_SCHEMAS deve essere un dizionario."""
        from parameter_schema import ALL_SCHEMAS
        assert isinstance(ALL_SCHEMAS, dict)
    
    def test_all_schemas_not_empty(self):
        """ALL_SCHEMAS non deve essere vuoto."""
        from parameter_schema import ALL_SCHEMAS
        assert len(ALL_SCHEMAS) > 0
    
    def test_expected_schemas_present(self):
        """Tutti gli schema attesi devono essere presenti."""
        from parameter_schema import ALL_SCHEMAS
        
        expected = ['stream', 'pointer', 'pitch', 'density', 'voice']
        for name in expected:
            assert name in ALL_SCHEMAS, f"Schema '{name}' mancante"
    
    def test_schemas_are_lists(self):
        """Ogni schema nel registry deve essere una lista."""
        from parameter_schema import ALL_SCHEMAS
        
        for name, schema in ALL_SCHEMAS.items():
            assert isinstance(schema, list), f"'{name}' non è una lista"
    
    def test_schemas_contain_parameter_specs(self):
        """Ogni schema deve contenere solo ParameterSpec."""
        from parameter_schema import ALL_SCHEMAS
        
        for name, schema in ALL_SCHEMAS.items():
            for entry in schema:
                assert isinstance(entry, ParameterSpec), \
                    f"'{name}' contiene entry non ParameterSpec"
    
    def test_no_duplicate_param_names_across_schemas(self):
        """Verifica che non ci siano nomi duplicati TRA schema diversi."""
        from parameter_schema import ALL_SCHEMAS
        
        all_names = []
        for schema in ALL_SCHEMAS.values():
            all_names.extend([spec.name for spec in schema])
        
        duplicates = [n for n in all_names if all_names.count(n) > 1]
        assert len(duplicates) == 0, f"Nomi duplicati tra schema: {set(duplicates)}"


# =============================================================================
# 16. TEST get_schema()
# =============================================================================

class TestGetSchema:
    """Test per la funzione get_schema()."""
    
    def test_returns_correct_schema(self):
        """Deve ritornare lo schema corretto."""
        from parameter_schema import get_schema, STREAM_PARAMETER_SCHEMA
        
        result = get_schema('stream')
        assert result is STREAM_PARAMETER_SCHEMA
    
    def test_returns_pointer_schema(self):
        """Deve ritornare POINTER_PARAMETER_SCHEMA."""
        from parameter_schema import get_schema, POINTER_PARAMETER_SCHEMA
        
        result = get_schema('pointer')
        assert result is POINTER_PARAMETER_SCHEMA
    
    def test_returns_pitch_schema(self):
        """Deve ritornare PITCH_PARAMETER_SCHEMA."""
        from parameter_schema import get_schema, PITCH_PARAMETER_SCHEMA
        
        result = get_schema('pitch')
        assert result is PITCH_PARAMETER_SCHEMA
    
    def test_returns_density_schema(self):
        """Deve ritornare DENSITY_PARAMETER_SCHEMA."""
        from parameter_schema import get_schema, DENSITY_PARAMETER_SCHEMA
        
        result = get_schema('density')
        assert result is DENSITY_PARAMETER_SCHEMA
    
    def test_returns_voice_schema(self):
        """Deve ritornare VOICE_PARAMETER_SCHEMA."""
        from parameter_schema import get_schema, VOICE_PARAMETER_SCHEMA
        
        result = get_schema('voice')
        assert result is VOICE_PARAMETER_SCHEMA
    
    def test_raises_keyerror_for_unknown(self):
        """Deve sollevare KeyError per schema inesistente."""
        from parameter_schema import get_schema
        
        with pytest.raises(KeyError) as excinfo:
            get_schema('schema_inventato')
        
        assert 'schema_inventato' in str(excinfo.value)
    
    def test_error_message_lists_available(self):
        """Il messaggio di errore deve elencare gli schema disponibili."""
        from parameter_schema import get_schema
        
        with pytest.raises(KeyError) as excinfo:
            get_schema('nonexistent')
        
        # Verifica che il messaggio contenga almeno uno schema valido
        assert 'stream' in str(excinfo.value) or 'Disponibili' in str(excinfo.value)


# =============================================================================
# 17. TEST get_all_schema_names()
# =============================================================================

class TestGetAllSchemaNames:
    """Test per la funzione get_all_schema_names()."""
    
    def test_returns_list(self):
        """Deve ritornare una lista."""
        from parameter_schema import get_all_schema_names
        
        result = get_all_schema_names()
        assert isinstance(result, list)
    
    def test_returns_strings(self):
        """Deve ritornare lista di stringhe."""
        from parameter_schema import get_all_schema_names
        
        for name in get_all_schema_names():
            assert isinstance(name, str)
    
    def test_contains_expected_names(self):
        """Deve contenere tutti i nomi attesi."""
        from parameter_schema import get_all_schema_names
        
        names = get_all_schema_names()
        
        assert 'stream' in names
        assert 'pointer' in names
        assert 'pitch' in names
        assert 'density' in names
        assert 'voice' in names
    
    def test_count_matches_all_schemas(self):
        """Il numero deve corrispondere a ALL_SCHEMAS."""
        from parameter_schema import get_all_schema_names, ALL_SCHEMAS
        
        assert len(get_all_schema_names()) == len(ALL_SCHEMAS)


# =============================================================================
# 18. TEST get_parameter_spec_from_schema()
# =============================================================================

class TestGetParameterSpecFromSchema:
    """Test per la funzione get_parameter_spec_from_schema()."""
    
    def test_returns_correct_spec_from_stream(self):
        """Deve ritornare la spec corretta da stream schema."""
        from parameter_schema import get_parameter_spec_from_schema
        
        spec = get_parameter_spec_from_schema('stream', 'volume')
        
        assert spec.name == 'volume'
        assert isinstance(spec, ParameterSpec)
    
    def test_returns_correct_spec_from_pointer(self):
        """Deve ritornare la spec corretta da pointer schema."""
        from parameter_schema import get_parameter_spec_from_schema
        
        spec = get_parameter_spec_from_schema('pointer', 'pointer_speed')
        
        assert spec.name == 'pointer_speed'
    
    def test_returns_correct_spec_from_pitch(self):
        """Deve ritornare la spec corretta da pitch schema."""
        from parameter_schema import get_parameter_spec_from_schema
        
        spec = get_parameter_spec_from_schema('pitch', 'pitch_ratio')
        
        assert spec.name == 'pitch_ratio'
    
    def test_returns_correct_spec_from_density(self):
        """Deve ritornare la spec corretta da density schema."""
        from parameter_schema import get_parameter_spec_from_schema
        
        spec = get_parameter_spec_from_schema('density', 'distribution')
        
        assert spec.name == 'distribution'
    
    def test_returns_correct_spec_from_voice(self):
        """Deve ritornare la spec corretta da voice schema."""
        from parameter_schema import get_parameter_spec_from_schema
        
        spec = get_parameter_spec_from_schema('voice', 'num_voices')
        
        assert spec.name == 'num_voices'
    
    def test_raises_keyerror_for_unknown_schema(self):
        """Deve sollevare KeyError per schema inesistente."""
        from parameter_schema import get_parameter_spec_from_schema
        
        with pytest.raises(KeyError):
            get_parameter_spec_from_schema('unknown_schema', 'volume')
    
    def test_raises_keyerror_for_unknown_param(self):
        """Deve sollevare KeyError per parametro inesistente."""
        from parameter_schema import get_parameter_spec_from_schema
        
        with pytest.raises(KeyError) as excinfo:
            get_parameter_spec_from_schema('stream', 'param_inventato')
        
        assert 'param_inventato' in str(excinfo.value)
    
    def test_error_includes_schema_name(self):
        """Il messaggio di errore deve includere il nome dello schema."""
        from parameter_schema import get_parameter_spec_from_schema
        
        with pytest.raises(KeyError) as excinfo:
            get_parameter_spec_from_schema('pointer', 'nonexistent')
        
        assert 'pointer' in str(excinfo.value)


# =============================================================================
# 19. TEST YAML PATH CONSISTENCY
# =============================================================================

class TestYamlPathConsistency:
    """Test che i yaml_path siano coerenti con la struttura YAML attesa."""
    
    def test_stream_paths_are_top_level_or_grain(self):
        """Stream paths: top-level o sotto 'grain'."""
        from parameter_schema import STREAM_PARAMETER_SCHEMA
        
        for spec in STREAM_PARAMETER_SCHEMA:
            # Path validi: 'volume', 'pan', 'grain.duration', etc.
            parts = spec.yaml_path.split('.')
            if len(parts) > 1:
                assert parts[0] == 'grain', \
                    f"{spec.name}: path nested dovrebbe essere sotto 'grain'"
    
    def test_pointer_paths_are_simple(self):
        """Pointer paths: semplici (il blocco 'pointer' è già estratto)."""
        from parameter_schema import POINTER_PARAMETER_SCHEMA
        
        for spec in POINTER_PARAMETER_SCHEMA:
            assert '.' not in spec.yaml_path, \
                f"{spec.name}: pointer path non dovrebbe essere nested"
    
    def test_pitch_paths_are_simple(self):
        """Pitch paths: semplici (il blocco 'pitch' è già estratto)."""
        from parameter_schema import PITCH_PARAMETER_SCHEMA
        
        for spec in PITCH_PARAMETER_SCHEMA:
            assert '.' not in spec.yaml_path, \
                f"{spec.name}: pitch path non dovrebbe essere nested"
    
    def test_density_paths_are_top_level(self):
        """Density paths: top-level (density/fill_factor/distribution)."""
        from parameter_schema import DENSITY_PARAMETER_SCHEMA
        
        for spec in DENSITY_PARAMETER_SCHEMA:
            assert '.' not in spec.yaml_path, \
                f"{spec.name}: density path non dovrebbe essere nested"
    
    def test_voice_paths_are_simple(self):
        """Voice paths: semplici (il blocco 'voices' è già estratto)."""
        from parameter_schema import VOICE_PARAMETER_SCHEMA
        
        for spec in VOICE_PARAMETER_SCHEMA:
            assert '.' not in spec.yaml_path, \
                f"{spec.name}: voice path non dovrebbe essere nested"


# =============================================================================
# 20. TEST SPECIAL CASES
# =============================================================================

class TestSchemaSpecialCases:
    """Test casi speciali e situazioni particolari."""
    
    def test_none_defaults_are_intentional(self):
        """Verifica che i default=None siano intenzionali (mutuamente esclusivi)."""
        from parameter_schema import (
            PITCH_PARAMETER_SCHEMA,
            DENSITY_PARAMETER_SCHEMA
        )
        
        # Pitch: semitones=None significa "usa ratio invece"
        semi = next(s for s in PITCH_PARAMETER_SCHEMA if s.name == 'pitch_semitones')
        assert semi.default is None
        
        # Density: fill_factor=None e density=None → logica nel Controller
        ff = next(s for s in DENSITY_PARAMETER_SCHEMA if s.name == 'fill_factor')
        dens = next(s for s in DENSITY_PARAMETER_SCHEMA if s.name == 'density')
        assert ff.default is None
        assert dens.default is None
    
    def test_non_smart_params_documented(self):
        """Parametri non-smart devono essere pochi e giustificati."""
        from parameter_schema import (
            STREAM_PARAMETER_SCHEMA,
            POINTER_PARAMETER_SCHEMA,
            PITCH_PARAMETER_SCHEMA,
            DENSITY_PARAMETER_SCHEMA,
            VOICE_PARAMETER_SCHEMA
        )
        
        all_schemas = [
            STREAM_PARAMETER_SCHEMA,
            POINTER_PARAMETER_SCHEMA,
            PITCH_PARAMETER_SCHEMA,
            DENSITY_PARAMETER_SCHEMA,
            VOICE_PARAMETER_SCHEMA
        ]
        
        non_smart = []
        for schema in all_schemas:
            non_smart.extend([s.name for s in schema if not s.is_smart])
        
        # Dovrebbero essere pochi: grain_envelope, pointer_start
        expected_non_smart = {'grain_envelope', 'pointer_start', 'pitch_range'}
        assert set(non_smart) == expected_non_smart, \
            f"Non-smart params inattesi: {set(non_smart) - expected_non_smart}"
        