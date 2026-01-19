"""
Test suite per VoiceManager.
Test aggiornati per verificare che i bounds vengano presi dal ParameterEvaluator.
"""

import pytest
from unittest.mock import Mock
from envelope import Envelope
import math


# =============================================================================
# TEST INIZIALIZZAZIONE
# =============================================================================

class TestVoiceManagerInit:
    
    def test_default_single_voice(self, voice_manager_factory):
        """Default: 1 voce, offset zero."""
        manager = voice_manager_factory({})
        
        assert manager.get_max_voices() == 1
        assert manager.voice_pitch_offset == 0.0
        assert manager.voice_pointer_offset == 0.0
    
    def test_explicit_params(self, voice_manager_factory):
        """Parametri espliciti parsati correttamente."""
        manager = voice_manager_factory({
            'number': 4,
            'offset_pitch': 12.0,
            'pointer_offset': 0.5,
            'pointer_range': 0.1
        })
        
        assert manager.get_max_voices() == 4
        assert manager.voice_pitch_offset == 12.0
        assert manager.voice_pointer_offset == 0.5
        assert manager.voice_pointer_range == 0.1


# =============================================================================
# TEST MAX VOICES CON BOUNDS DA PARAMETEREVALUATOR
# =============================================================================

class TestMaxVoicesWithBounds:
    
    def test_max_voices_clipped_to_bounds(self, voice_manager_factory, mock_evaluator):
        """max_voices deve essere clippato ai bounds del ParameterEvaluator (1-20)."""
        # Configura mock_evaluator.get_bounds per restituire i bounds corretti
        from parameter_evaluator import ParameterBounds
        mock_bounds = ParameterBounds(1.0, 20.0)  # Bounds definiti in ParameterEvaluator
        
        # Sostituisci il comportamento del mock
        original_get_bounds = mock_evaluator.get_bounds
        mock_evaluator.get_bounds = Mock(return_value=mock_bounds)
        
        try:
            # Prova con un valore sopra il limite
            manager = voice_manager_factory({'number': 30})
            
            # Il max_voices dovrebbe essere 20, non 30
            assert manager.get_max_voices() == 20
            
            # Prova con un valore sotto il limite
            manager2 = voice_manager_factory({'number': 0})
            assert manager2.get_max_voices() == 1  # Clippato a min_val=1.0
        finally:
            # Ripristina
            mock_evaluator.get_bounds = original_get_bounds
    
    def test_max_voices_from_envelope_clipped(self, voice_manager_factory, mock_evaluator):
        """Envelope con valori oltre i bounds viene clippato."""
        from parameter_evaluator import ParameterBounds
        mock_bounds = ParameterBounds(1.0, 20.0)
        
        # Mock get_bounds
        original_get_bounds = mock_evaluator.get_bounds
        mock_evaluator.get_bounds = Mock(return_value=mock_bounds)
        
        try:
            # Envelope che va da 5 a 25
            env = Mock(spec=Envelope)
            env.breakpoints = [[0, 5], [5, 25], [10, 15]]
            
            manager = voice_manager_factory({'number': env})
            
            # Il massimo dell'envelope è 25, ma dovrebbe essere clippato a 20
            assert manager.get_max_voices() == 20
        finally:
            mock_evaluator.get_bounds = original_get_bounds
    
    def test_missing_bounds_raises_error(self, voice_manager_factory, mock_evaluator):
        """Se ParameterEvaluator non ha bounds per 'num_voices', deve sollevare errore."""
        # Configura get_bounds per restituire None
        original_get_bounds = mock_evaluator.get_bounds
        mock_evaluator.get_bounds = Mock(return_value=None)
        
        try:
            with pytest.raises(ValueError, match="Bounds per 'num_voices' non definiti"):
                manager = voice_manager_factory({'number': 5})
        finally:
            mock_evaluator.get_bounds = original_get_bounds


# =============================================================================
# TEST ACTIVE VOICES DINAMICO
# =============================================================================

class TestActiveVoices:
    
    def test_active_voices_static(self, voice_manager_factory):
        """Con valore statico, active_voices = quel valore."""
        manager = voice_manager_factory({'number': 3})
        
        assert manager.get_active_voices(0.0) == 3
        assert manager.get_active_voices(5.0) == 3
    
    def test_active_voices_envelope(self, voice_manager_factory):
        """Con Envelope, active_voices varia nel tempo."""
        # Envelope: 2 -> 6 in 10 secondi
        env = Mock(spec=Envelope)
        env.breakpoints = [[0, 2], [10, 6]]
        env.evaluate.side_effect = lambda t: 2 + (t / 10.0) * 4
        
        manager = voice_manager_factory({'number': env})
        
        # t=0: 2 voci
        assert manager.get_active_voices(0.0) == 2
        
        # t=5: 4 voci (2 + 0.5*4 = 4)
        assert manager.get_active_voices(5.0) == 4
        
        # t=10: 6 voci
        assert manager.get_active_voices(10.0) == 6


# =============================================================================
# TEST PATTERN ALTERNATO (+/-)
# =============================================================================

class TestAlternatingPattern:
    """
    Verifica il pattern alternato:
    Voice 0: 0
    Voice 1: +offset * 1
    Voice 2: -offset * 1
    Voice 3: +offset * 2
    Voice 4: -offset * 2
    """
    
    def test_pitch_offset_pattern(self, voice_manager_factory):
        """Verifica pattern alternato per pitch offset (semitoni)."""
        manager = voice_manager_factory({
            'number': 5,
            'offset_pitch': 7.0  # Quinta giusta
        })
        
        # Voice 0: sempre 0
        assert manager.get_voice_pitch_offset_semitones(0, 0.0) == 0.0
        
        # Voice 1: +7 * 1 = +7
        assert manager.get_voice_pitch_offset_semitones(1, 0.0) == 7.0
        
        # Voice 2: -7 * 1 = -7
        assert manager.get_voice_pitch_offset_semitones(2, 0.0) == -7.0
        
        # Voice 3: +7 * 2 = +14
        assert manager.get_voice_pitch_offset_semitones(3, 0.0) == 14.0
        
        # Voice 4: -7 * 2 = -14
        assert manager.get_voice_pitch_offset_semitones(4, 0.0) == -14.0


# =============================================================================
# TEST BOUNDS COMPLIANCE
# =============================================================================

class TestBoundsCompliance:
    """Test che tutti i metodi rispettino i bounds del ParameterEvaluator."""
    
    def test_voice_pitch_offset_bounds(self, voice_manager_factory, mock_evaluator):
        """voice_pitch_offset deve essere valutato con i bounds corretti."""
        # Configura mock per verificare che evaluate venga chiamato con i bounds giusti
        mock_evaluator.evaluate = Mock(return_value=12.0)  # Mock di base
        
        manager = voice_manager_factory({
            'number': 3,
            'offset_pitch': 12.0
        })
        
        # Chiamata a get_voice_pitch_offset_semitones
        result = manager.get_voice_pitch_offset_semitones(1, 0.0)
        
        # Verifica che evaluate sia stato chiamato con i parametri corretti
        mock_evaluator.evaluate.assert_called_with(
            12.0,  # Il valore originale
            0.0,   # elapsed_time
            'voice_pitch_offset'  # Il nome del parametro (deve avere bounds in ParameterEvaluator)
        )
        
        # Il risultato dovrebbe essere 12.0 (per voice 1: +12)
        assert result == 12.0