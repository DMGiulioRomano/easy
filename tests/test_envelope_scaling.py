"""
test_envelope_scaling.py

Test suite dedicata alle funzioni di scaling temporale e di valore
introdotte per gestire la normalizzazione e i loop points.

Coverage:
1. create_scaled_envelope (Scaling Tempo / Asse X)
2. Envelope.scale_envelope_values (Scaling Valore / Asse Y)
3. Gestione formati complessi (Compact, Dict, Mixed) durante lo scaling
"""

import pytest
from envelope import Envelope, create_scaled_envelope

# =============================================================================
# 1. TEST CREATE_SCALED_ENVELOPE (SCALING TEMPO / ASSE X)
# =============================================================================

class TestTimeScaling:
    """
    Testa la funzione globale create_scaled_envelope.
    Obiettivo: Moltiplicare i tempi (t) per la durata dello stream
    quando time_mode='normalized'.
    """

    def test_scale_time_normalized_list(self):
        """Lista standard: i tempi [0-1] diventano [0-duration]."""
        raw_data = [[0.0, 0], [0.5, 1], [1.0, 0]]
        duration = 10.0
        
        env = create_scaled_envelope(raw_data, duration, time_mode='normalized')
        
        # Breakpoints attesi
        assert env.segments[0].breakpoints[0] == pytest.approx([0.0, 0])   # 0 * 10
        assert env.segments[0].breakpoints[1] == pytest.approx([5.0, 1])   # 0.5 * 10
        assert env.segments[0].breakpoints[2] == pytest.approx([10.0, 0])  # 1.0 * 10

    def test_scale_time_absolute_ignored(self):
        """Se time_mode='absolute', i tempi NON cambiano."""
        raw_data = [[0.0, 0], [0.5, 1]]
        duration = 10.0
        
        env = create_scaled_envelope(raw_data, duration, time_mode='absolute')
        
        # Rimangono uguali
        assert env.segments[0].breakpoints[1][0] == 0.5

    def test_scale_time_dict_format(self):
        """Dict format: scala i tempi dentro 'points'."""
        raw_data = {
            'type': 'cubic',
            'points': [[0.0, 0], [1.0, 10]]
        }
        duration = 4.0
        
        env = create_scaled_envelope(raw_data, duration, time_mode='normalized')
        
        assert env.type == 'cubic'
        assert env.segments[0].end_time == 4.0  # 1.0 * 4.0

    def test_scale_time_compact_format_normalized(self):
        raw_data = [[[0, 0], [100, 1]], 1.0, 4]  # total_time=1.0 (normalizzato)
        stream_duration = 60.0
        
        env = create_scaled_envelope(raw_data, stream_duration, time_mode='normalized')
        
        # ✓ Test corretto: total_time=1.0 deve scalare a 60s
        last_point_time = env.segments[0].breakpoints[-1][0]
        assert last_point_time == pytest.approx(60.0)

    def test_scale_time_compact_format_absolute(self):
        """Con time_mode='absolute', il total_time rimane invariato."""
        raw_data = [[[0, 0], [100, 1]], 0.4, 4]
        stream_duration = 60.0
        
        env = create_scaled_envelope(raw_data, stream_duration, time_mode='absolute')
        
        # Deve rispettare 0.4s del compatto, NON 60s
        last_point_time = env.segments[0].breakpoints[-1][0]
        assert last_point_time == pytest.approx(0.4)

    def test_scale_time_mixed_format(self):
        """
        Formato misto: Scala TUTTI i tempi (standard + end_time compatti).
        
        Con la NUOVA semantica end_time:
        - I breakpoint standard vengono scalati
        - Gli end_time dei formati compatti vengono scalati
        - Il risultato deve essere temporalmente coerente
        - Il formato compatto aggiunge DISCONTINUITY_OFFSET quando segue altri breakpoint
        """
        # Layout temporale normalizzato (0-1):
        # - Breakpoint a 0.5
        # - Compatto da 0.5 a 0.7 (durata 0.2)
        # - Breakpoint finale a 1.0
        
        raw_data = [
            [0.5, 10],                      # Scala a 5.0
            [[[0, 0], [100, 1]], 0.7, 1],   # end_time=0.7, scala a 7.0
            [1.0, 0]                        # Scala a 10.0
        ]
        duration = 10.0

        env = create_scaled_envelope(raw_data, duration, time_mode='normalized')
        
        # Verifica: 4 breakpoint totali (standard + compatto con discontinuità)
        points = env.breakpoints
        assert len(points) == 4
        
        assert points[0] == pytest.approx([5.0, 10])           # Primo standard
        assert points[1] == pytest.approx([5.000001, 0])       # Inizio compatto (con DISCONTINUITY_OFFSET)
        assert points[2] == pytest.approx([7.0, 1])            # Fine compatto
        assert points[3] == pytest.approx([10.0, 0])           # Ultimo standard


# =============================================================================
# 2. TEST SCALE_ENVELOPE_VALUES (SCALING VALORE / ASSE Y)
# =============================================================================

class TestValueScaling:
    """
    Testa Envelope.scale_envelope_values.
    Obiettivo: Moltiplicare i valori Y (es. posizione pointer) per un fattore (es. lunghezza sample).
    """

    def test_scale_values_standard_list(self):
        """Lista standard: scala Y, preserva X."""
        raw_data = [[0.0, 0.0], [1.0, 0.5], [2.0, 1.0]]
        scale_factor = 100.0  # Es. sample lungo 100s
        
        env = Envelope.scale_envelope_values(raw_data, scale_factor)
        
        # Y deve essere scalato
        assert env.segments[0].breakpoints[1][1] == 50.0   # 0.5 * 100
        assert env.segments[0].breakpoints[2][1] == 100.0  # 1.0 * 100
        
        # X deve rimanere invariato
        assert env.segments[0].breakpoints[1][0] == 1.0

    def test_scale_values_compact_direct(self):
        """
        Formato compatto diretto: [[[x%, y]...], time, reps].
        Deve scalare le Y dentro il pattern.
        """
        # Pattern: y va da 0 a 1
        raw_data = [[[0, 0], [100, 1]], 5.0, 1]
        scale_factor = 10.0
        
        env = Envelope.scale_envelope_values(raw_data, scale_factor)
        
        # Il valore finale del breakpoint espanso deve essere 1 * 10 = 10
        assert env.segments[0].breakpoints[-1][1] == 10.0

    def test_scale_values_compact_nested_in_list(self):
        """Formato compatto annidato in una lista."""
        raw_data = [
            [[[0, 0.5], [100, 1.0]], 1.0, 1]
        ]
        scale_factor = 4.0
        
        env = Envelope.scale_envelope_values(raw_data, scale_factor)
        
        # 0.5 * 4 = 2.0
        # 1.0 * 4 = 4.0
        assert env.segments[0].breakpoints[0][1] == 2.0
        assert env.segments[0].breakpoints[1][1] == 4.0

    def test_scale_values_dict_format(self):
        """Dict format: scala i valori dentro 'points'."""
        raw_data = {
            'type': 'step',
            'points': [[0, 0.1], [1, 0.2]]
        }
        scale_factor = 10.0
        
        env = Envelope.scale_envelope_values(raw_data, scale_factor)
        
        assert env.type == 'step'
        assert env.segments[0].breakpoints[0][1] == 1.0  # 0.1 * 10
        assert env.segments[0].breakpoints[1][1] == 2.0  # 0.2 * 10

    def test_scale_values_mixed_format(self):
        """Misto: scala Y sia per standard che per compatto."""
        raw_data = [
            [0.0, 0.1],                     # Standard
            [[[0, 0.2], [100, 0.3]], 1, 1]  # Compact
        ]
        scale_factor = 10.0
        
        env = Envelope.scale_envelope_values(raw_data, scale_factor)
        
        breakpoints = env.segments[0].breakpoints
        values = [bp[1] for bp in breakpoints]
        
        # Ci aspettiamo: 1.0 (da 0.1), 2.0 (da 0.2), 3.0 (da 0.3)
        assert 1.0 in values
        assert 2.0 in values
        assert 3.0 in values


# =============================================================================
# 3. TEST EDGE CASES E ERRORI
# =============================================================================

class TestScalingEdgeCases:
    
    def test_scale_values_invalid_format(self):
        """Errore su formato sconosciuto."""
        with pytest.raises(ValueError):
            Envelope.scale_envelope_values("invalid_string", 10.0)

    def test_create_scaled_invalid_input(self):
        """Errore su input invalido in create_scaled_envelope."""
        with pytest.raises(ValueError):
            create_scaled_envelope("invalid_string", 10.0)

    def test_scale_zero_factor(self):
        """Scaling per 0 appiattisce tutto a 0."""
        raw_data = [[0, 10], [1, 20]]
        env = Envelope.scale_envelope_values(raw_data, 0.0)
        
        assert env.evaluate(0) == 0.0
        assert env.evaluate(1) == 0.0

# =============================================================================
# 4. TEST _SCALE_RAW_VALUES_Y (RESTITUZIONE DATI RAW)
# =============================================================================

class TestScaleRawValuesY:
    """
    Testa Envelope._scale_raw_values_y.
    Verifica che restituisca dati raw (list/dict), non oggetti Envelope.
    """

    def test_returns_list_not_envelope(self):
        """Il risultato e' una lista, non un Envelope."""
        raw_data = [[0.0, 0.5], [1.0, 1.0]]
        result = Envelope._scale_raw_values_y(raw_data, 10.0)
        
        assert isinstance(result, list)
        assert not isinstance(result, Envelope)

    def test_returns_dict_not_envelope(self):
        """Dict in input restituisce dict, non Envelope."""
        raw_data = {'type': 'linear', 'points': [[0, 0.1], [1, 0.2]]}
        result = Envelope._scale_raw_values_y(raw_data, 10.0)
        
        assert isinstance(result, dict)
        assert not isinstance(result, Envelope)

    def test_scales_y_standard_list(self):
        """Lista standard: scala Y, preserva X."""
        raw_data = [[0.0, 0.0], [1.0, 0.5], [2.0, 1.0]]
        result = Envelope._scale_raw_values_y(raw_data, 100.0)
        
        assert result[1][1] == 50.0   # 0.5 * 100
        assert result[2][1] == 100.0  # 1.0 * 100
        assert result[1][0] == 1.0    # X invariato

    def test_scales_y_compact_direct(self):
        """Formato compatto diretto: scala Y nel pattern."""
        raw_data = [[[0, 0], [100, 1]], 5.0, 1]
        result = Envelope._scale_raw_values_y(raw_data, 10.0)
        
        assert isinstance(result, list)
        assert result[0][0][1] == 0     # 0 * 10
        assert result[0][1][1] == 10    # 1 * 10
        assert result[1] == 5.0         # tempo invariato
        assert result[2] == 1           # ripetizioni invariate

    def test_scales_y_dict_format(self):
        """Dict: scala Y dentro 'points'."""
        raw_data = {'type': 'step', 'points': [[0, 0.1], [1, 0.2]]}
        result = Envelope._scale_raw_values_y(raw_data, 10.0)
        
        assert result['type'] == 'step'
        assert result['points'][0][1] == 1.0   # 0.1 * 10
        assert result['points'][1][1] == 2.0   # 0.2 * 10

    def test_scales_y_compact_nested(self):
        """Formato compatto annidato in lista."""
        raw_data = [[[[0, 0.5], [100, 1.0]], 1.0, 1]]
        result = Envelope._scale_raw_values_y(raw_data, 4.0)
        
        assert isinstance(result, list)
        assert result[0][0][0][1] == 2.0   # 0.5 * 4
        assert result[0][0][1][1] == 4.0   # 1.0 * 4

    def test_invalid_format_raises(self):
        """Formato non supportato solleva ValueError."""
        with pytest.raises(ValueError, match="_scale_raw_values_y"):
            Envelope._scale_raw_values_y("invalid_string", 10.0)

    def test_scale_zero_factor(self):
        """Scaling per 0 azzera tutti i valori Y."""
        raw_data = [[0, 10], [1, 20]]
        result = Envelope._scale_raw_values_y(raw_data, 0.0)
        
        assert result[0][1] == 0.0
        assert result[1][1] == 0.0

    def test_does_not_modify_original(self):
        """Non modifica i dati originali (immutabilita')."""
        raw_data = [[0, 0.5], [1, 1.0]]
        original_copy = [[0, 0.5], [1, 1.0]]
        
        Envelope._scale_raw_values_y(raw_data, 10.0)
        
        assert raw_data == original_copy

    def test_consistency_with_scale_envelope_values(self):
        """I valori Y devono essere identici a scale_envelope_values."""
        raw_data = [[0.0, 0.2], [1.0, 0.8]]
        scale = 5.0
        
        raw_result = Envelope._scale_raw_values_y(raw_data, scale)
        env_result = Envelope.scale_envelope_values(raw_data, scale)
        
        assert raw_result[0][1] == env_result.breakpoints[0][1]
        assert raw_result[1][1] == env_result.breakpoints[1][1]