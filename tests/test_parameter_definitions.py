# tests/test_parameter_definitions.py
"""
Test suite per parameter_definitions.py (Registry Pattern).

Verifica:
- Immutabilità di ParameterBounds (frozen dataclass)
- Completezza del Registry GRANULAR_PARAMETERS
- Funzione get_parameter_definition()
- Correttezza dei variation_mode per ogni parametro
"""

import pytest
from dataclasses import FrozenInstanceError


# =============================================================================
# IMPORT DEL MODULO DA TESTARE
# =============================================================================

from parameter_definitions import (
    ParameterBounds,
    GRANULAR_PARAMETERS,
    get_parameter_definition
)


# =============================================================================
# 1. TEST IMMUTABILITÀ (Value Object Pattern)
# =============================================================================

class TestParameterBoundsImmutability:
    """ParameterBounds deve essere immutabile (frozen=True)."""
    
    def test_cannot_modify_min_val(self):
        """Tentativo di modifica min_val deve fallire."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        
        with pytest.raises(FrozenInstanceError):
            bounds.min_val = 999.0
    
    def test_cannot_modify_max_val(self):
        """Tentativo di modifica max_val deve fallire."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        
        with pytest.raises(FrozenInstanceError):
            bounds.max_val = 999.0
    
    def test_cannot_modify_variation_mode(self):
        """Tentativo di modifica variation_mode deve fallire."""
        bounds = ParameterBounds(min_val=0.0, max_val=1.0, variation_mode='invert')
        
        with pytest.raises(FrozenInstanceError):
            bounds.variation_mode = 'additive'
    
    def test_hashable(self):
        """ParameterBounds deve essere hashable (usabile come chiave dict)."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        
        # Se è hashable, possiamo usarlo in un set
        bounds_set = {bounds}
        assert bounds in bounds_set


# =============================================================================
# 2. TEST VALORI DEFAULT
# =============================================================================

class TestParameterBoundsDefaults:
    """Test dei valori di default di ParameterBounds."""
    
    def test_default_min_range(self):
        """min_range default = 0.0."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        assert bounds.min_range == 0.0
    
    def test_default_max_range(self):
        """max_range default = 0.0."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        assert bounds.max_range == 0.0
    
    def test_default_jitter(self):
        """default_jitter default = 0.0."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        assert bounds.default_jitter == 0.0
    
    def test_default_variation_mode(self):
        """variation_mode default = 'additive'."""
        bounds = ParameterBounds(min_val=0.0, max_val=100.0)
        assert bounds.variation_mode == 'additive'


# =============================================================================
# 3. TEST REGISTRY COMPLETENESS
# =============================================================================

class TestRegistryCompleteness:
    """Verifica che il Registry contenga tutti i parametri attesi."""
    
    # Parametri che DEVONO esistere (backward compatibility)
    REQUIRED_PARAMS = [
        # Density & Time
        'density',
        'fill_factor',
        'distribution',
        'effective_density',
        # Grain Properties
        'grain_duration',
        'reverse',
        # Pitch
        'pitch_semitones',
        'pitch_ratio',
        # Pointer
        'pointer_speed',
        'pointer_deviation',
        'loop_dur',
        # Output
        'volume',
        'pan',
        # Voices
        'num_voices',
        'voice_pitch_offset',
        'voice_pointer_offset',
        'voice_pointer_range',
        # Probabilities
        'dephase_prob',
    ]
    
    @pytest.mark.parametrize("param_name", REQUIRED_PARAMS)
    def test_required_param_exists(self, param_name):
        """Ogni parametro richiesto deve esistere nel Registry."""
        assert param_name in GRANULAR_PARAMETERS, \
            f"Parametro '{param_name}' mancante dal Registry!"
    
    def test_all_entries_are_parameter_bounds(self):
        """Ogni entry del Registry deve essere un ParameterBounds."""
        for name, bounds in GRANULAR_PARAMETERS.items():
            assert isinstance(bounds, ParameterBounds), \
                f"'{name}' non è un ParameterBounds: {type(bounds)}"


# =============================================================================
# 4. TEST VARIATION MODES
# =============================================================================

class TestVariationModes:
    """Verifica che i variation_mode siano corretti per ogni tipo di parametro."""
    
    # Parametri che DEVONO avere variation_mode='quantized' (interi)
    QUANTIZED_PARAMS = ['pitch_semitones', 'num_voices']
    
    # Parametri che DEVONO avere variation_mode='invert' (boolean flip)
    INVERT_PARAMS = ['reverse']
    
    # Tutti gli altri devono essere 'additive'
    
    @pytest.mark.parametrize("param_name", QUANTIZED_PARAMS)
    def test_quantized_params(self, param_name):
        """Parametri discreti devono avere variation_mode='quantized'."""
        bounds = GRANULAR_PARAMETERS[param_name]
        assert bounds.variation_mode == 'quantized', \
            f"'{param_name}' dovrebbe essere 'quantized', è '{bounds.variation_mode}'"
    
    @pytest.mark.parametrize("param_name", INVERT_PARAMS)
    def test_invert_params(self, param_name):
        """Parametri booleani devono avere variation_mode='invert'."""
        bounds = GRANULAR_PARAMETERS[param_name]
        assert bounds.variation_mode == 'invert', \
            f"'{param_name}' dovrebbe essere 'invert', è '{bounds.variation_mode}'"
    
    def test_valid_variation_modes_only(self):
        """Tutti i variation_mode devono essere tra quelli supportati."""
        VALID_MODES = {'additive', 'quantized', 'invert'}
        
        for name, bounds in GRANULAR_PARAMETERS.items():
            assert bounds.variation_mode in VALID_MODES, \
                f"'{name}' ha variation_mode invalido: '{bounds.variation_mode}'"


# =============================================================================
# 5. TEST get_parameter_definition()
# =============================================================================

class TestGetParameterDefinition:
    """Test della funzione di accesso al Registry."""
    
    def test_returns_correct_bounds(self):
        """Deve restituire i bounds corretti per un parametro esistente."""
        bounds = get_parameter_definition('density')
        
        assert bounds.min_val == 0.1
        assert bounds.max_val == 4000.0
    
    def test_raises_keyerror_for_unknown(self):
        """Deve sollevare KeyError per parametro inesistente."""
        with pytest.raises(KeyError) as excinfo:
            get_parameter_definition('parametro_inventato_xyz')
        
        assert 'parametro_inventato_xyz' in str(excinfo.value)
    
    def test_returns_same_object(self):
        """Deve restituire lo stesso oggetto (no copia)."""
        bounds1 = get_parameter_definition('pan')
        bounds2 = get_parameter_definition('pan')
        
        # Stesso oggetto in memoria (identity)
        assert bounds1 is bounds2


# =============================================================================
# 6. TEST BOUNDS SANITY (Valori sensati)
# =============================================================================

class TestBoundsSanity:
    """Verifica che i bounds abbiano valori sensati."""
    
    def test_min_less_than_max(self):
        """min_val deve essere < max_val per tutti i parametri."""
        for name, bounds in GRANULAR_PARAMETERS.items():
            assert bounds.min_val < bounds.max_val, \
                f"'{name}': min_val ({bounds.min_val}) >= max_val ({bounds.max_val})"
    
    def test_range_bounds_non_negative(self):
        """min_range e max_range devono essere >= 0."""
        for name, bounds in GRANULAR_PARAMETERS.items():
            assert bounds.min_range >= 0, \
                f"'{name}': min_range negativo ({bounds.min_range})"
            assert bounds.max_range >= 0, \
                f"'{name}': max_range negativo ({bounds.max_range})"
    
    def test_default_jitter_within_range(self):
        """default_jitter deve essere <= max_range (se max_range > 0)."""
        for name, bounds in GRANULAR_PARAMETERS.items():
            if bounds.max_range > 0:
                assert bounds.default_jitter <= bounds.max_range, \
                    f"'{name}': default_jitter ({bounds.default_jitter}) > max_range ({bounds.max_range})"
    
    def test_density_bounds(self):
        """Density: range realistico per sintesi granulare."""
        bounds = GRANULAR_PARAMETERS['density']
        assert bounds.min_val >= 0.1  # Almeno 0.1 grani/sec
        assert bounds.max_val <= 10000  # Max ragionevole
    
    def test_pan_bounds_support_rotation(self):
        """Pan: deve supportare valori oltre 360° per rotazione."""
        bounds = GRANULAR_PARAMETERS['pan']
        assert bounds.min_val <= -360
        assert bounds.max_val >= 360