# tests/conftest.py
"""
Fixtures e helpers condivisi tra tutte le test suite.

Contenuto:
- mock_config: StreamConfig/StreamContext mockato per i controller tests
  Usato da: test_density_controller, test_pitch_controller, test_pointer_controller
"""

import pytest
from unittest.mock import Mock
from stream_config import StreamConfig, StreamContext


@pytest.fixture
def mock_config():
    """
    StreamConfig minimale con StreamContext mockato.

    Fornisce una configurazione valida per istanziare i controller
    (DensityController, PitchController, PointerController) nei test
    senza dipendere da file audio reali o da parametri YAML.
    """
    context = Mock(spec=StreamContext)
    context.stream_id = "test_stream"
    context.sample_dur_sec = 10.0
    context.duration = 10.0

    config = Mock(spec=StreamConfig)
    config.context = context
    config.time_mode = 'absolute'
    config.distribution_mode = 'uniform'
    config.dephase = False
    config.range_always_active = False

    return config



def make_mock_stream_for_generator(stream_id='stream_01', sample='test.wav'):
    """
    Mock Stream con attributi necessari per Generator.

    Generator gestisce sample tables, window maps e generazione grani.
    Attributi: stream_id, sample, sample_table_num, window_table_map,
               generate_grains, __repr__, __str__
    """
    stream = Mock()
    stream.stream_id = stream_id
    stream.sample = sample
    stream.sample_table_num = None
    stream.window_table_map = None
    stream.generate_grains = Mock()
    stream.__repr__ = Mock(return_value=f"Stream({stream_id})")
    stream.__str__ = Mock(return_value=f"Stream({stream_id})")
    return stream


def make_mock_testina_for_generator(testina_id='testina_01', sample_path='tape.wav'):
    """
    Mock Testina con attributi necessari per Generator.

    Attributi: testina_id, sample_path, sample_table_num,
               __repr__, __str__
    """
    testina = Mock()
    testina.testina_id = testina_id
    testina.sample_path = sample_path
    testina.sample_table_num = None
    testina.__repr__ = Mock(return_value=f"Testina({testina_id})")
    testina.__str__ = Mock(return_value=f"Testina({testina_id})")
    return testina