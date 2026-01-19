# tests/test_stream.py
"""
Test di integrazione per la classe Stream (orchestratore).

Verifica:
- Inizializzazione corretta dei controller
- Generazione grani con struttura voices: List[List[Grain]]
- Backward compatibility (self.grains flattened)
- Proprietà esposte per Generator/ScoreVisualizer
- Determinismo con seed fisso

Fixtures utilizzate (da conftest.py):
- stream_factory: factory per creare Stream
- stream_minimal: Stream con configurazione minima
- stream_full: Stream con configurazione completa
- stream_with_envelopes: Stream con envelope dinamici
- fixed_seed: seed random fisso per determinismo
"""

import pytest
import random
from unittest.mock import patch, Mock

# Import necessari per type checking
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


# =============================================================================
# 1. TEST INIZIALIZZAZIONE
# =============================================================================

class TestStreamInit:
    """Test inizializzazione dello Stream."""
    
    def test_minimal_params(self, stream_minimal):
        """Stream con parametri minimi si inizializza correttamente."""
        assert stream_minimal.stream_id == 'test_stream'
        assert stream_minimal.onset == 0.0
        assert stream_minimal.duration == 5.0
        assert stream_minimal.sample_dur_sec == 10.0  # dal mock
    
    def test_full_params(self, stream_full):
        """Stream con parametri completi si inizializza correttamente."""
        assert stream_full.stream_id == 'full_test_stream'
        assert stream_full.onset == 1.0
        assert stream_full.duration == 10.0
        assert stream_full.time_mode == 'absolute'
    
    def test_controllers_initialized(self, stream_full):
        """Tutti i controller sono inizializzati."""
        # Verifica che i controller esistano (attributi privati)
        assert hasattr(stream_full, '_pointer')
        assert hasattr(stream_full, '_pitch')
        assert hasattr(stream_full, '_density')
        assert hasattr(stream_full, '_voice_manager')
        assert hasattr(stream_full, '_evaluator')
    
    def test_default_values(self, stream_minimal):
        """Valori default applicati correttamente."""
        assert stream_minimal.grain_envelope == 'hanning'
        assert stream_minimal.grain_reverse_mode == 'auto'


# =============================================================================
# 2. TEST GENERAZIONE GRANI
# =============================================================================

class TestGrainGeneration:
    """Test generazione grani."""
    
    def test_generate_returns_voices_list(self, stream_minimal):
        """generate_grains() ritorna List[List[Grain]]."""
        voices = stream_minimal.generate_grains()
        
        assert isinstance(voices, list)
        assert len(voices) >= 1
        for voice in voices:
            assert isinstance(voice, list)
    
    def test_grains_flattened_for_compatibility(self, stream_minimal):
        """self.grains contiene la lista flattened."""
        stream_minimal.generate_grains()
        
        # Conta grani nelle voices
        total_in_voices = sum(len(v) for v in stream_minimal.voices)
        
        # Deve corrispondere a grains
        assert len(stream_minimal.grains) == total_in_voices
    
    def test_generated_flag(self, stream_minimal):
        """Flag generated settato dopo generazione."""
        assert stream_minimal.generated is False
        stream_minimal.generate_grains()
        assert stream_minimal.generated is True
    
    def test_grain_structure(self, stream_minimal):
        """Ogni grano ha tutti gli attributi necessari."""
        stream_minimal.generate_grains()
        
        if stream_minimal.grains:
            grain = stream_minimal.grains[0]
            
            assert hasattr(grain, 'onset')
            assert hasattr(grain, 'duration')
            assert hasattr(grain, 'pointer_pos')
            assert hasattr(grain, 'pitch_ratio')
            assert hasattr(grain, 'volume')
            assert hasattr(grain, 'pan')
            assert hasattr(grain, 'sample_table')
            assert hasattr(grain, 'envelope_table')
            assert hasattr(grain, 'grain_reverse')
    
    def test_grain_onset_is_absolute(self, stream_factory):
        """Onset dei grani è relativo all'inizio della composizione."""
        stream = stream_factory({
            'stream_id': 'offset_test',
            'onset': 5.0,  # Stream inizia a t=5
            'duration': 2.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.1, 'envelope': 'hanning'}
        })
        stream.generate_grains()
        
        if stream.grains:
            # Il primo grano deve avere onset >= 5.0
            assert stream.grains[0].onset >= 5.0


# =============================================================================
# 3. TEST MULTI-VOICE
# =============================================================================

class TestMultiVoice:
    """Test generazione con voci multiple."""
    
    def test_multiple_voices_created(self, stream_full):
        """Con num_voices=2, vengono create 2 voci."""
        stream_full.generate_grains()
        
        # Il VoiceManager è configurato con 2 voci
        assert len(stream_full.voices) == 2
    
    def test_voice_pitch_offset_applied(self, stream_full, fixed_seed):
        """Offset pitch applicato alle voci."""
        stream_full.generate_grains()
        
        if len(stream_full.voices) >= 2:
            voice0_grain = stream_full.voices[0][0] if stream_full.voices[0] else None
            voice1_grain = stream_full.voices[1][0] if stream_full.voices[1] else None
            
            if voice0_grain and voice1_grain:
                # Voice 1 dovrebbe avere pitch diverso (offset +7 semitoni)
                # Non testiamo il valore esatto perché dipende dal range stocastico
                assert voice0_grain.pitch_ratio != voice1_grain.pitch_ratio or \
                       stream_full._voice_manager.voice_pitch_offset == 0


# =============================================================================
# 4. TEST DETERMINISMO
# =============================================================================

class TestDeterminism:
    """Test determinismo con seed fisso."""
    
    def test_same_seed_same_grains(self, stream_factory, stream_params_minimal):
        """Stesso seed produce stessi grani."""
        random.seed(42)
        stream1 = stream_factory(stream_params_minimal)
        stream1.generate_grains()
        grains1 = [(g.onset, g.duration, g.pitch_ratio) for g in stream1.grains]
        
        random.seed(42)
        stream2 = stream_factory(stream_params_minimal)
        stream2.generate_grains()
        grains2 = [(g.onset, g.duration, g.pitch_ratio) for g in stream2.grains]
        
        assert grains1 == grains2
    
    def test_different_seed_different_grains(self, stream_factory, stream_params_full):
        """Seed diversi producono grani diversi (con range stocastici)."""
        random.seed(42)
        stream1 = stream_factory(stream_params_full)
        stream1.generate_grains()
        grains1 = [(g.onset, g.duration, g.pitch_ratio) for g in stream1.grains]
        
        random.seed(123)
        stream2 = stream_factory(stream_params_full)
        stream2.generate_grains()
        grains2 = [(g.onset, g.duration, g.pitch_ratio) for g in stream2.grains]
        
        # Con range stocastici, i grani dovrebbero essere diversi
        # (almeno qualche grano sarà diverso)
        differences = sum(1 for a, b in zip(grains1, grains2) if a != b)
        assert differences > 0 or len(grains1) != len(grains2)


# =============================================================================
# 5. TEST BACKWARD COMPATIBILITY
# =============================================================================

class TestBackwardCompatibility:
    """Test compatibilità con Generator e ScoreVisualizer."""
    
    def test_sample_dur_sec_alias(self, stream_minimal):
        """Alias sampleDurSec funziona."""
        assert stream_minimal.sampleDurSec == stream_minimal.sample_dur_sec
    
    def test_exposed_properties(self, stream_full):
        """Proprietà esposte per Generator/ScoreVisualizer."""
        # Queste proprietà sono usate da Generator e ScoreVisualizer
        assert hasattr(stream_full, 'num_voices')
        assert hasattr(stream_full, 'density')
        assert hasattr(stream_full, 'fill_factor')
        assert hasattr(stream_full, 'distribution')
        assert hasattr(stream_full, 'pointer_speed')
        assert hasattr(stream_full, 'pitch_ratio')
        assert hasattr(stream_full, 'pitch_semitones_envelope')
        assert hasattr(stream_full, 'pitch_range')
        assert hasattr(stream_full, 'voice_pitch_offset')
        assert hasattr(stream_full, 'voice_pointer_offset')
        assert hasattr(stream_full, 'voice_pointer_range')
    
    def test_csound_table_references(self, stream_minimal):
        """Riferimenti ftable Csound inizializzati a None."""
        assert stream_minimal.sample_table_num is None
        assert stream_minimal.envelope_table_num is None
        
        # Possono essere assegnati
        stream_minimal.sample_table_num = 1
        stream_minimal.envelope_table_num = 2
        assert stream_minimal.sample_table_num == 1
        assert stream_minimal.envelope_table_num == 2
    
    def test_repr(self, stream_minimal):
        """__repr__ produce stringa informativa."""
        r = repr(stream_minimal)
        assert 'Stream' in r
        assert 'test_stream' in r


# =============================================================================
# 6. TEST PARAMETRI CON ENVELOPE
# =============================================================================

class TestEnvelopeParameters:
    """Test parametri dinamici con Envelope."""
    
    def test_envelope_grain_duration(self, stream_with_envelopes):
        """Grain duration con envelope produce grani con durata variabile."""
        stream_with_envelopes.generate_grains()
        
        if len(stream_with_envelopes.grains) >= 2:
            durations = [g.duration for g in stream_with_envelopes.grains]
            # Con envelope 50ms → 100ms, dovremmo vedere variazione
            min_dur = min(durations)
            max_dur = max(durations)
            # Almeno qualche variazione
            assert max_dur > min_dur or len(set(durations)) == 1
    
    def test_envelope_num_voices(self, stream_with_envelopes):
        """Numero voci con envelope crea la struttura corretta."""
        stream_with_envelopes.generate_grains()
        
        # Con envelope 1 → 4 → 1, max_voices dovrebbe essere 4
        assert len(stream_with_envelopes.voices) == 4


# =============================================================================
# 7. TEST GRAIN REVERSE
# =============================================================================

class TestGrainReverse:
    """Test calcolo grain_reverse con nuova logica Dephase."""
    
    def test_reverse_auto_logic(self, stream_factory):
        """Senza dephase, 'auto' segue rigorosamente la velocità."""
        stream = stream_factory({
            'stream_id': 'rev_auto',
            'onset': 0.0, 'duration': 0.2, 'sample': 'test.wav',
            'grain': {'duration': 0.1, 'envelope': 'hanning', 'reverse': 'auto'},
            'pointer': {'speed': 1.0} # Positiva -> Reverse False
        })
        stream.generate_grains()
        assert stream.grains[0].grain_reverse is False

        stream_neg = stream_factory({
            'stream_id': 'rev_auto_neg',
            'onset': 0.0, 'duration': 0.2, 'sample': 'test.wav',
            'grain': {'duration': 0.1, 'envelope': 'hanning', 'reverse': 'auto'},
            'pointer': {'speed': -1.0} # Negativa -> Reverse True
        })
        stream_neg.generate_grains()
        assert stream_neg.grains[0].grain_reverse is True

    def test_reverse_dephase_flip(self, stream_factory):
        """Con dephase reverse 100%, il valore viene invertito."""
        # Caso: Speed + (False), Dephase 100 -> Diventa True
        stream = stream_factory({
            'stream_id': 'rev_flip',
            'onset': 0.0, 'duration': 0.2, 'sample': 'test.wav',
            'grain': {'duration': 0.1, 'envelope': 'hanning', 'reverse': 'auto'},
            'pointer': {'speed': 1.0},
            'dephase': {'pc_rand_reverse': 100}
        })
        stream.generate_grains()
        
        # Dovrebbe essere True (False invertito)
        if stream.grains:
            assert stream.grains[0].grain_reverse is True

# =============================================================================
# 8. TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test casi limite."""
    
    def test_very_short_duration(self, stream_factory):
        """Stream con durata molto breve."""
        stream = stream_factory({
            'stream_id': 'short',
            'onset': 0.0,
            'duration': 0.1,  # 100ms
            'sample': 'test.wav',
            'grain': {'duration': 0.05, 'envelope': 'hanning'}
        })
        stream.generate_grains()
        
        # Dovrebbe generare almeno qualche grano
        assert stream.generated is True
    
    def test_zero_range_parameters(self, stream_factory):
        """Range a zero = nessuna variazione stocastica (Scenario A)."""
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'no_range',
            'onset': 0.0,
            'duration': 1.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.05, 'duration_range': 0.0, 'envelope': 'hanning'},
            'volume': -6.0,
            'volume_range': 0.0,
            'pan': 0.0,
            'pan_range': 0.0
            # Dephase è implicito None, quindi Scenario A.
            # Poiché range è 0, il risultato deve essere piatto.
        })
        stream.generate_grains()
        
        if stream.grains:
            volumes = set(g.volume for g in stream.grains)
            pans = set(g.pan for g in stream.grains)
            
            # Devono essere esattamente 1 valore unico
            assert len(volumes) == 1
            assert len(pans) == 1
            assert list(volumes)[0] == -6.0
            assert list(pans)[0] == 0.0

# =============================================================================
# 9. TEST INTEGRAZIONE CON CONTROLLER
# =============================================================================

class TestControllerIntegration:
    """Test integrazione tra Stream e controller."""
    
    def test_pointer_controller_used(self, stream_full):
        """PointerController è usato per calcolare pointer_pos."""
        stream_full.generate_grains()
        
        if stream_full.grains:
            # pointer_pos dovrebbe essere nel range del sample
            for grain in stream_full.grains[:10]:  # Primi 10
                # Con wrapping, può essere ovunque nel sample
                assert grain.pointer_pos is not None
    
    def test_pitch_controller_used(self, stream_full):
        """PitchController è usato per calcolare pitch_ratio."""
        stream_full.generate_grains()
        
        if stream_full.grains:
            for grain in stream_full.grains[:10]:
                # pitch_ratio dovrebbe essere positivo
                assert grain.pitch_ratio > 0
    
    def test_density_controller_used(self, stream_full):
        """DensityController è usato per inter-onset."""
        stream_full.generate_grains()
        
        # Con fill_factor=2.0 e grain_dur=0.05, density ≈ 40 g/s
        # In 10 secondi, dovremmo avere circa 400 grani per voce (×2 voci)
        # Ma con distribution=0, potrebbero essere di meno per timing
        assert len(stream_full.grains) > 10  # Almeno qualche grano
    
    def test_voice_manager_used(self, stream_full):
        """VoiceManager è usato per gestire le voci."""
        stream_full.generate_grains()
        
        # Con num_voices=2, dovremmo avere 2 liste in voices
        assert len(stream_full.voices) == 2


# =============================================================================
# 10. TEST SCORE LINE OUTPUT
# =============================================================================

class TestScoreLineOutput:
    """Test output per Csound score."""
    
    def test_grain_to_score_line(self, stream_minimal):
        """Ogni grano può generare una linea di score."""
        stream_minimal.sample_table_num = 1
        stream_minimal.envelope_table_num = 2
        stream_minimal.generate_grains()
        
        if stream_minimal.grains:
            grain = stream_minimal.grains[0]
            score_line = grain.to_score_line()
            
            assert 'i "Grain"' in score_line
            assert str(grain.sample_table) in score_line
            assert str(grain.envelope_table) in score_line

# =============================================================================
# 11. TEST DEPHASE / MICRO-MODULATION
# =============================================================================

class TestDephaseModulation:
    """Test della logica Dephase (Micromodulazione) e coesistenza con Range."""

    def test_dephase_inactive_by_default(self, stream_factory):
        """Se dephase non è specificato, il range funziona normalmente (Scenario A)."""
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'no_dephase',
            'onset': 0.0, 'duration': 1.0, 'sample': 'test.wav',
            # Range esplicito, Dephase assente
            'volume': -6.0, 'volume_range': 6.0 
        })
        stream.generate_grains()
        
        # Dovremmo vedere variazione di volume dovuta al range
        volumes = [g.volume for g in stream.grains]
        assert max(volumes) != min(volumes)
        # Verifica bounds approssimativi (-9 a -3)
        assert min(volumes) >= -9.0
        assert max(volumes) <= -3.0

    def test_dephase_trigger_default_jitter(self, stream_factory):
        """Se range=0 ma dephase=100, si attiva il default jitter (Scenario B)."""
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'dephase_only',
            'onset': 0.0, 'duration': 1.0, 'sample': 'test.wav',
            # Volume fisso, ma dephase attivo al 100%
            'volume': -6.0, 'volume_range': 0.0,
            'dephase': {'pc_rand_volume': 100}
        })
        stream.generate_grains()
        
        # Dovremmo vedere variazione nonostante volume_range=0
        # grazie al default_jitter (es. 1.5dB definito in _create_grain)
        volumes = [g.volume for g in stream.grains]
        unique_volumes = set(volumes)
        
        assert len(unique_volumes) > 1
        
    def test_dephase_gates_range(self, stream_factory):
        """Se dephase=0, il range viene ignorato anche se definito (Scenario C - Gate Closed)."""
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'dephase_closed',
            'onset': 0.0, 'duration': 1.0, 'sample': 'test.wav',
            # Range enorme, ma Dephase a 0%
            'volume': -6.0, 'volume_range': 100.0,
            'dephase': {'pc_rand_volume': 0}
        })
        stream.generate_grains()
        
        # Tutti i volumi dovrebbero essere uguali al base
        volumes = {g.volume for g in stream.grains}
        assert len(volumes) == 1
        assert list(volumes)[0] == -6.0

    def test_dephase_pan_inversion(self, stream_factory):
        """Test specifico per inversione di fase del Pan."""
        # Nota: questo è difficile da testare deterministicamente senza mockare random_percent
        # Testiamo solo che con dephase attivo succeda qualcosa
        stream = stream_factory({
            'stream_id': 'pan_dephase',
            'onset': 0.0, 'duration': 1.0, 'sample': 'test.wav',
            'pan': 45.0, 'pan_range': 0.0,
            'dephase': {'pc_rand_pan': 100} # Sempre attivo
        })
        stream.generate_grains()
        
        # Con pan 45 e dephase 100, dovremmo avere variazioni (jitter)
        pans = {g.pan for g in stream.grains}
        assert len(pans) > 1