"""
Test suite per Generator.
Verifica parsing YAML, valutazione espressioni, gestione ftable e scrittura score.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
import math

# Import necessario
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from generator import Generator

# =============================================================================
# TEST PARSING & MATH
# =============================================================================

class TestGeneratorMath:
    """Testa la valutazione delle espressioni matematiche nel YAML."""

    def test_eval_simple_math(self, generator):
        """Espressioni semplici (somma, divisione)."""
        data = {'val': '(10 + 5)', 'div': '(10 / 2)'}
        result = generator._eval_math_expressions(data)
        assert result['val'] == 15
        assert result['div'] == 5.0

    def test_eval_constants(self, generator):
        """Costanti matematiche (pi, e)."""
        data = {'pi_val': '(pi)', 'e_val': '(e)'}
        result = generator._eval_math_expressions(data)
        assert math.isclose(result['pi_val'], math.pi)
        
    def test_eval_nested_structure(self, generator):
        """Valutazione ricorsiva in liste e dict."""
        data = {
            'list': ['(1+1)', {'inner': '(3*3)'}],
            'fixed': 10
        }
        result = generator._eval_math_expressions(data)
        assert result['list'][0] == 2
        assert result['list'][1]['inner'] == 9
        assert result['fixed'] == 10

    def test_eval_error_handling(self, generator, capsys):
        """Gestione errori su espressioni invalide."""
        data = {'bad': '(1 / 0)'} # Divisione per zero
        result = generator._eval_math_expressions(data)
        # Deve ritornare la stringa originale se fallisce
        assert result['bad'] == '(1 / 0)' 
        # Verifica che stampi warning
        captured = capsys.readouterr()
        assert "Warning" in captured.out


# =============================================================================
# TEST FTABLE MANAGEMENT
# =============================================================================

class TestFtableGeneration:
    """Testa la creazione e deduplicazione delle Function Tables."""

    def test_sample_deduplication(self, generator):
        """Stesso sample path deve ritornare stesso ID tabella."""
        id1 = generator.generate_ftable_for_sample("file1.wav")
        id2 = generator.generate_ftable_for_sample("file1.wav")
        id3 = generator.generate_ftable_for_sample("file2.wav")

        assert id1 == 1
        assert id2 == 1  # Deduplicato
        assert id3 == 2  # Nuovo ID

    def test_envelope_deduplication(self, generator):
        """Stesso tipo envelope deve ritornare stesso ID tabella."""
        id1 = generator.generate_ftable_for_envelope("hanning")
        id2 = generator.generate_ftable_for_envelope("hanning")
        id3 = generator.generate_ftable_for_envelope("hamming")

        assert id1 == 1
        assert id2 == 1
        assert id3 == 2


# =============================================================================
# TEST CREATE ELEMENTS (Logic Solo/Mute)
# =============================================================================

class TestCreateElements:
    """
    Testa la logica di creazione Stream e filtraggio.
    Usa Mock per Stream per evitare I/O reale.
    """

    @patch('generator.Stream')
    def test_create_streams_simple(self, MockStream, generator):
        """Creazione standard degli stream."""
        # Mock dati YAML caricati
        generator.data = {
            'streams': [
                {'stream_id': 's1', 'sample': 'a.wav', 'grain_envelope': 'hanning'},
                {'stream_id': 's2', 'sample': 'b.wav', 'grain_envelope': 'hanning'}
            ]
        }
        
        streams, testine = generator.create_elements()
        
        assert len(streams) == 2
        assert MockStream.call_count == 2
        # Verifica che siano stati assegnati i numeri tabella
        assert streams[0].sample_table_num is not None
        assert streams[0].envelope_table_num is not None

    @patch('generator.Stream')
    def test_mute_logic(self, MockStream, generator):
        """Gli stream con 'mute' vengono ignorati."""
        generator.data = {
            'streams': [
                {'stream_id': 's1', 'sample': 'a.wav', 'grain_envelope': 'hanning'},
                {'stream_id': 's2', 'sample': 'b.wav', 'mute': True}
            ]
        }
        
        streams, _ = generator.create_elements()
        assert len(streams) == 1
        assert MockStream.call_count == 1 # s2 non istanziato

    @patch('generator.Stream')
    def test_solo_logic(self, MockStream, generator):
        """Se c'è 'solo', gli altri vengono ignorati."""
        generator.data = {
            'streams': [
                {'stream_id': 's1', 'sample': 'a.wav', 'grain_envelope': 'hanning'},
                {'stream_id': 's2_solo', 'sample': 'b.wav', 'grain_envelope': 'hanning', 'solo': True},
                {'stream_id': 's3', 'sample': 'c.wav', 'grain_envelope': 'hanning'}
            ]
        }
        
        streams, _ = generator.create_elements()
        assert len(streams) == 1
        # Verifica che il Mock sia stato chiamato con i dati del solo
        args, _ = MockStream.call_args
        assert args[0]['stream_id'] == 's2_solo'


# =============================================================================
# TEST SCORE WRITING
# =============================================================================

class TestScoreWriting:
    """Testa la scrittura dell'output Csound."""

    def test_write_ftables_content(self, generator, tmp_path):
        """Verifica che le ftable vengano scritte correttamente."""
        # Setup ftables
        generator.generate_ftable_for_envelope('hanning') # ID 1
        generator.generate_ftable_for_envelope('half_sine') # ID 2
        
        out_file = tmp_path / "out.sco"
        with open(out_file, 'w') as f:
            generator.write_score_header(f)
            
        content = out_file.read_text()
        
        # Verifica presenza GEN routine corrette
        assert "f 1 0 1024 20 2" in content # Hanning (GEN 20 opt 2)
        assert "f 2 0 1024 9 0.5" in content # Half sine (GEN 09)

    @patch('generator.Stream')
    def test_generate_full_score_file(self, MockStream, generator, tmp_path):
        """Test integrazione: genera l'intero file."""
        # Setup dati minimi
        mock_stream_instance = Mock()
        mock_stream_instance.stream_id = "test_s"
        # Mock property per evitare errori nei commenti
        mock_stream_instance.grain_duration = 0.1
        mock_stream_instance.density = 10
        mock_stream_instance.distribution = 0
        mock_stream_instance.num_voices = 1
        mock_stream_instance.voices = [] # Nessun grano per semplicità
        
        generator.streams = [mock_stream_instance]
        generator.generate_ftable_for_envelope('hanning')
        
        out_path = tmp_path / "full.sco"
        generator.generate_score_file(str(out_path))
        
        assert out_path.exists()
        content = out_path.read_text()
        assert "; CSOUND SCORE" in content
        assert "f 1" in content
        assert "; Stream: test_s" in content
        assert "e" in content # End marker