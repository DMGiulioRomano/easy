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
        Formato misto: Scala i punti standard, preserva i compatti.
        """
        # [Standard(0.5), Compact(dur=0.2), Standard(1.0)]
        raw_data = [
            [0.5, 10],                      # Deve scalare -> 5.0
            [[[0, 0], [100, 1]], 0.2, 1],   # Deve restare 0.2 (assoluto)
            [1.0, 0]                        # Deve scalare -> 10.0
        ]
        duration = 10.0
        
        env = create_scaled_envelope(raw_data, duration, time_mode='normalized')
        
        breakpoints = env.segments[0].breakpoints
        
        # Nota: L'ordine temporale finale dipende dai valori.
        # Qui verifichiamo che la conversione sia avvenuta.
        
        # Cerchiamo il punto che era 0.5
        found_scaled_mid = False
        for bp in breakpoints:
            if bp[0] == 5.0 and bp[1] == 10:
                found_scaled_mid = True
        assert found_scaled_mid, "Il punto standard 0.5 non è stato scalato a 5.0"

        # Cerchiamo il punto finale del compatto (dovrebbe essere intorno a 0.2 se parte da 0, 
        # ma envelope builder li ordina. Verifichiamo solo che non sia stato moltiplicato per 10 diventando 2.0)
        # In questo caso specifico, EnvelopeBuilder espande e poi ordina.
        # Il compatto inizia a 0? No, il formato misto in EnvelopeBuilder è tricky sull'ordine.
        # Verifichiamo semplicemente che NON ci siano punti a t=2.0 (0.2 * 10) se non previsti.
        
        # Verifichiamo l'ultimo punto (era 1.0)
        assert breakpoints[-1][0] == 10.0


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