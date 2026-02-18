# =============================================================================
# tests/test_logger.py - Suite completa di test per logger.py
# =============================================================================
"""
Test suite per src/logger.py

Copre:
- configure_clip_logger: reset stato, aggiornamento config
- get_clip_logger: lazy init, master switch, handler creation, path naming
- get_clip_log_path: ritorno path corretto o None
- log_clip_warning: logica di formattazione, bound detection, sorgente ENV/FIX
- log_config_warning: tag CONFIG, value_type
- Isolamento di stato tra test (global state reset)
"""

import logging
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# Helper per isolare lo stato globale del modulo tra i test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_logger_state():
    """
    Resetta lo stato globale di logger.py prima di ogni test.
    Il modulo usa variabili globali _clip_logger e _clip_logger_initialized,
    quindi e' necessario un reset esplicito per garantire l'isolamento.
    """
    import logger
    # Chiudi handler esistenti per non lasciare file aperti
    if logger._clip_logger is not None:
        for handler in logger._clip_logger.handlers[:]:
            handler.close()
            logger._clip_logger.removeHandler(handler)
    # Reset stato globale
    logger._clip_logger = None
    logger._clip_logger_initialized = False
    # Reset config ai valori di default
    logger.CLIP_LOG_CONFIG.update({
        'enabled': True,
        'console_enabled': True,
        'file_enabled': True,
        'log_dir': './logs',
        'log_filename': None,
        'validation_mode': 'strict',
        'log_transformations': True,
    })
    yield
    # Cleanup post-test: chiudi handler aperti
    if logger._clip_logger is not None:
        for handler in logger._clip_logger.handlers[:]:
            handler.close()
            logger._clip_logger.removeHandler(handler)
    logger._clip_logger = None
    logger._clip_logger_initialized = False


# =============================================================================
# TEST: configure_clip_logger
# =============================================================================

class TestConfigureClipLogger:
    """Test per configure_clip_logger()"""

    def test_configure_updates_enabled_flag(self):
        import logger
        logger.configure_clip_logger(enabled=False)
        assert logger.CLIP_LOG_CONFIG['enabled'] is False

    def test_configure_updates_console_enabled(self):
        import logger
        logger.configure_clip_logger(console_enabled=False)
        assert logger.CLIP_LOG_CONFIG['console_enabled'] is False

    def test_configure_updates_file_enabled(self):
        import logger
        logger.configure_clip_logger(file_enabled=False)
        assert logger.CLIP_LOG_CONFIG['file_enabled'] is False

    def test_configure_updates_log_dir(self):
        import logger
        logger.configure_clip_logger(log_dir='/tmp/test_logs')
        assert logger.CLIP_LOG_CONFIG['log_dir'] == '/tmp/test_logs'

    def test_configure_updates_yaml_name(self):
        import logger
        logger.configure_clip_logger(yaml_name='my_composition')
        assert logger.CLIP_LOG_CONFIG['yaml_name'] == 'my_composition'

    def test_configure_updates_log_transformations(self):
        import logger
        logger.configure_clip_logger(log_transformations=False)
        assert logger.CLIP_LOG_CONFIG['log_transformations'] is False

    def test_configure_resets_initialized_flag(self):
        """configure deve resettare _clip_logger_initialized per permettere re-init."""
        import logger
        logger._clip_logger_initialized = True
        logger._clip_logger = MagicMock()
        logger.configure_clip_logger(enabled=False)
        assert logger._clip_logger_initialized is False
        assert logger._clip_logger is None

    def test_configure_defaults_match_expected(self):
        """Chiamata senza argomenti usa i valori di default corretti."""
        import logger
        logger.configure_clip_logger()
        assert logger.CLIP_LOG_CONFIG['enabled'] is True
        assert logger.CLIP_LOG_CONFIG['console_enabled'] is True
        assert logger.CLIP_LOG_CONFIG['file_enabled'] is True
        assert logger.CLIP_LOG_CONFIG['log_dir'] == './logs'
        assert logger.CLIP_LOG_CONFIG['log_transformations'] is True


# =============================================================================
# TEST: get_clip_logger - master switch e lazy init
# =============================================================================

class TestGetClipLoggerMasterSwitch:
    """Test per il master switch e il pattern di lazy initialization."""

    def test_returns_none_when_disabled(self):
        import logger
        logger.configure_clip_logger(enabled=False)
        result = logger.get_clip_logger()
        assert result is None

    def test_returns_none_when_both_outputs_disabled(self):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            console_enabled=False,
            file_enabled=False
        )
        result = logger.get_clip_logger()
        assert result is None

    def test_lazy_init_returns_same_instance(self):
        """Secondo get ritorna la stessa istanza senza re-init."""
        import logger
        with patch('os.makedirs'), patch('os.path.exists', return_value=True):
            with patch('logging.FileHandler'):
                first = logger.get_clip_logger()
                second = logger.get_clip_logger()
        assert first is second

    def test_initialized_flag_set_after_first_call(self):
        import logger
        logger.configure_clip_logger(enabled=False)
        logger.get_clip_logger()
        assert logger._clip_logger_initialized is True

    def test_second_call_skips_reinit(self):
        """Se gia' inizializzato, non riesegue la logica."""
        import logger
        logger._clip_logger_initialized = True
        logger._clip_logger = None  # simula disabled
        result = logger.get_clip_logger()
        assert result is None


# =============================================================================
# TEST: get_clip_logger - creazione handler
# =============================================================================

class TestGetClipLoggerHandlers:
    """Test per la creazione di file handler e console handler."""

    def test_file_handler_created_when_file_enabled(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='test_suite'
        )
        result = logger.get_clip_logger()
        assert result is not None
        file_handlers = [h for h in result.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1

    def test_console_handler_created_when_console_enabled(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=False,
            console_enabled=True,
            log_dir=str(tmp_path)
        )
        result = logger.get_clip_logger()
        assert result is not None
        stream_handlers = [
            h for h in result.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 1

    def test_both_handlers_created_when_both_enabled(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=True,
            log_dir=str(tmp_path),
            yaml_name='both'
        )
        result = logger.get_clip_logger()
        assert result is not None
        assert len(result.handlers) == 2

    def test_no_handlers_when_file_only_disabled(self, tmp_path):
        """Solo file abilitato - solo file handler."""
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='fileonly'
        )
        result = logger.get_clip_logger()
        assert result is not None
        assert len(result.handlers) == 1
        assert isinstance(result.handlers[0], logging.FileHandler)

    def test_log_dir_created_if_not_exists(self, tmp_path):
        import logger
        new_dir = str(tmp_path / 'new_subdir')
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=new_dir,
            yaml_name='dirtest'
        )
        logger.get_clip_logger()
        assert os.path.exists(new_dir)

    def test_log_level_is_info(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='level'
        )
        result = logger.get_clip_logger()
        assert result.level == logging.INFO

    def test_handlers_cleared_before_init(self, tmp_path):
        """Non devono accumularsi handler da chiamate precedenti."""
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=True,
            log_dir=str(tmp_path),
            yaml_name='clean'
        )
        result = logger.get_clip_logger()
        # Deve avere esattamente 2 handler (file + console), non di piu'
        assert len(result.handlers) == 2


# =============================================================================
# TEST: naming del file di log
# =============================================================================

class TestLogFilenaming:
    """Test per la logica di naming del file di log."""

    def test_filename_uses_yaml_name_when_provided(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='my_piece'
        )
        logger.get_clip_logger()
        log_files = list(tmp_path.glob('envelope_clips_my_piece.log'))
        assert len(log_files) == 1

    def test_filename_uses_timestamp_when_no_yaml_name(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path)
        )
        logger.get_clip_logger()
        log_files = list(tmp_path.glob('envelope_clips_*.log'))
        assert len(log_files) == 1
        # Il nome non deve contenere 'None'
        assert 'None' not in log_files[0].name

    def test_log_file_mode_is_write(self, tmp_path):
        """Il file viene aperto in modalita' 'w' (sovrascrittura)."""
        import logger
        yaml_name = 'write_mode_test'
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name=yaml_name
        )
        result = logger.get_clip_logger()
        file_handler = next(h for h in result.handlers if isinstance(h, logging.FileHandler))
        assert file_handler.mode == 'w'

    def test_log_file_encoding_is_utf8(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='encoding_test'
        )
        result = logger.get_clip_logger()
        file_handler = next(h for h in result.handlers if isinstance(h, logging.FileHandler))
        assert file_handler.encoding == 'utf-8'


# =============================================================================
# TEST: get_clip_log_path
# =============================================================================

class TestGetClipLogPath:
    """Test per get_clip_log_path()."""

    def test_returns_none_when_logger_is_none(self):
        import logger
        logger._clip_logger = None
        result = logger.get_clip_log_path()
        assert result is None

    def test_returns_path_when_file_handler_exists(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='path_test'
        )
        logger.get_clip_logger()
        path = logger.get_clip_log_path()
        assert path is not None
        assert 'envelope_clips_path_test.log' in path

    def test_returns_none_when_only_console_handler(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=False,
            console_enabled=True
        )
        logger.get_clip_logger()
        path = logger.get_clip_log_path()
        assert path is None

    def test_returned_path_is_absolute(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='abspath'
        )
        logger.get_clip_logger()
        path = logger.get_clip_log_path()
        assert os.path.isabs(path)


# =============================================================================
# TEST: log_clip_warning  (CORRETTI)
# =============================================================================

class TestLogClipWarning:
    """Test per log_clip_warning()."""

    def test_no_op_when_logger_none(self):
        import logger
        with patch('logger.get_clip_logger', return_value=None):
            # Non deve sollevare eccezioni
            logger.log_clip_warning('s1', 'pitch', 1.0, 0.5, 1.0, 1.0, 2.0)

    def test_calls_logger_warning(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 0.5, 1.0, 1.0, 2.0)
        assert mock_logger.warning.called

    def test_min_bound_violation_detected(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'MIN' in msg

    def test_max_bound_violation_detected(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 3.0, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'MAX' in msg

    def test_envelope_source_tag(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 3.0, 2.0, 1.0, 2.0, is_envelope=True)
        msg = mock_logger.warning.call_args[0][0]
        assert 'ENV' in msg

    def test_fixed_source_tag(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 3.0, 2.0, 1.0, 2.0, is_envelope=False)
        msg = mock_logger.warning.call_args[0][0]
        assert 'FIX' in msg

    def test_stream_id_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('STREAM_42', 'density', 1.0, 3.0, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'STREAM_42' in msg

    def test_param_name_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'grain_duration', 1.0, 3.0, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'grain_duration' in msg

    def test_time_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 5.123, 3.0, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert '5.123' in msg

    def test_deviation_is_negative_for_min_violation(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert '-' in msg

    def test_deviation_is_positive_for_max_violation(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'pitch', 1.0, 3.0, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert '+' in msg

    @pytest.mark.parametrize("raw,clipped,min_val,max_val,expected_bound", [
        (0.0, 1.0, 1.0, 5.0, 'MIN'),
        (6.0, 5.0, 1.0, 5.0, 'MAX'),
        (-10.0, 1.0, 1.0, 5.0, 'MIN'),
        (100.0, 5.0, 1.0, 5.0, 'MAX'),
    ])
    def test_parametrized_bound_detection(self, raw, clipped, min_val, max_val, expected_bound):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_clip_warning('s1', 'p', 0.0, raw, clipped, min_val, max_val)
        msg = mock_logger.warning.call_args[0][0]
        assert expected_bound in msg


# =============================================================================
# TEST: log_config_warning  (CORRETTI)
# =============================================================================

class TestLogConfigWarning:
    """Test per log_config_warning()."""

    def test_no_op_when_logger_none(self):
        import logger
        with patch('logger.get_clip_logger', return_value=None):
            logger.log_config_warning('s1', 'pitch', 0.5, 1.0, 1.0, 2.0)

    def test_calls_logger_warning(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'pitch', 0.5, 1.0, 1.0, 2.0)
        assert mock_logger.warning.called

    def test_config_tag_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'pitch', 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'CONFIG' in msg

    def test_stream_id_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('STREAM_99', 'density', 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'STREAM_99' in msg

    def test_param_name_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'grain_duration', 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'grain_duration' in msg

    def test_default_value_type_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'pitch', 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'value' in msg

    @pytest.mark.parametrize("value_type", ['value', 'range', 'probability'])
    def test_value_type_appears_in_message(self, value_type):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'p', 0.5, 1.0, 1.0, 2.0, value_type=value_type)
        msg = mock_logger.warning.call_args[0][0]
        assert value_type in msg

    def test_min_bound_violation_in_config_warning(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'pitch', 0.5, 1.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'MIN' in msg

    def test_max_bound_violation_in_config_warning(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'pitch', 3.0, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert 'MAX' in msg

    def test_raw_and_clipped_values_in_message(self):
        import logger
        mock_logger = MagicMock()
        with patch('logger.get_clip_logger', return_value=mock_logger):
            logger.log_config_warning('s1', 'p', 3.5, 2.0, 1.0, 2.0)
        msg = mock_logger.warning.call_args[0][0]
        assert '3.5' in msg or '3.500000' in msg
        assert '2.0' in msg or '2.000000' in msg

# =============================================================================
# TEST: Integrazione - round trip configure -> get -> log
# =============================================================================

class TestIntegration:
    """Test di integrazione che verificano il flusso completo."""

    def test_full_flow_file_only(self, tmp_path):
        """configure -> get_clip_logger -> log_clip_warning -> verifica file."""
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='integration'
        )
        l = logger.get_clip_logger()
        assert l is not None
        # Forza un log attraverso log_clip_warning
        logger.log_clip_warning('s1', 'pitch', 1.0, 3.0, 2.0, 1.0, 2.0)
        # Chiudi handler per flush
        for h in l.handlers:
            h.flush()
        log_file = tmp_path / 'envelope_clips_integration.log'
        assert log_file.exists()

    def test_reconfigure_resets_logger(self, tmp_path):
        """Dopo configure il logger viene re-inizializzato."""
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='first'
        )
        first_logger = logger.get_clip_logger()

        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='second'
        )
        second_logger = logger.get_clip_logger()

        # Devono essere istanze diverse (o almeno ri-inizializzate)
        # La verifica pratica: il secondo ha il file corretto
        path = logger.get_clip_log_path()
        assert 'second' in path

    def test_disabled_logger_prevents_any_log(self, tmp_path):
        """Con enabled=False nessun file viene creato."""
        import logger
        logger.configure_clip_logger(
            enabled=False,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='disabled'
        )
        logger.get_clip_logger()
        logger.log_clip_warning('s1', 'pitch', 1.0, 3.0, 2.0, 1.0, 2.0)
        log_files = list(tmp_path.glob('*.log'))
        assert len(log_files) == 0

    def test_log_config_warning_in_full_flow(self, tmp_path):
        import logger
        logger.configure_clip_logger(
            enabled=True,
            file_enabled=True,
            console_enabled=False,
            log_dir=str(tmp_path),
            yaml_name='config_flow'
        )
        logger.get_clip_logger()
        # Non deve sollevare eccezioni
        logger.log_config_warning('s1', 'density', 0.1, 1.0, 1.0, 10.0, value_type='range')
        log_file = tmp_path / 'envelope_clips_config_flow.log'
        for h in logger._clip_logger.handlers:
            h.flush()
        assert log_file.exists()

# =============================================================================
# TEST log_loop_drift_warning
# =============================================================================

import pytest
import logging
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, 'src')

import logger as logger_module
from logger import (
    log_loop_drift_warning,
    configure_clip_logger,
    get_clip_logger,
    CLIP_LOG_CONFIG,
)


# =============================================================================
# FIXTURE: logger abilitato con handler in memoria
# =============================================================================

@pytest.fixture(autouse=True)
def reset_logger():
    """Resetta lo stato globale del logger prima di ogni test."""
    logger_module._clip_logger = None
    logger_module._clip_logger_initialized = False
    yield
    # Cleanup: chiudi handler aperti
    if logger_module._clip_logger:
        for h in logger_module._clip_logger.handlers[:]:
            h.close()
            logger_module._clip_logger.removeHandler(h)
    logger_module._clip_logger = None
    logger_module._clip_logger_initialized = False


@pytest.fixture
def memory_logger():
    """
    Configura un logger con MemoryHandler per catturare i messaggi nei test
    senza scrivere su file o console.
    """
    logger_module._clip_logger = None
    logger_module._clip_logger_initialized = False

    # Crea logger reale con handler in memoria
    log = logging.getLogger('envelope_clip_test')
    log.setLevel(logging.WARNING)
    log.handlers = []

    records = []

    class CapturingHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = CapturingHandler()
    handler.setLevel(logging.WARNING)
    log.addHandler(handler)

    # Inietta nel modulo
    logger_module._clip_logger = log
    logger_module._clip_logger_initialized = True

    return records


# =============================================================================
# GRUPPO 1: Chiamata quando logger e' None (disabilitato)
# =============================================================================

class TestLogLoopDriftWarningDisabled:
    """Quando il logger e' None, la funzione deve ritornare silenziosamente."""

    def test_returns_silently_when_logger_none(self):
        """Nessuna eccezione se il logger e' disabilitato."""
        logger_module._clip_logger = None
        logger_module._clip_logger_initialized = True

        # Non deve sollevare eccezioni
        log_loop_drift_warning(
            stream_id='test_stream',
            elapsed_time=10.0,
            pointer_pos=0.63,
            loop_start=0.84,
            loop_end=1.44,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )

    def test_no_log_emitted_when_disabled(self):
        """Nessun log emesso quando logger e' None."""
        logger_module._clip_logger = None
        logger_module._clip_logger_initialized = True

        with patch.object(logging.Logger, 'warning') as mock_warn:
            log_loop_drift_warning(
                stream_id='stream1',
                elapsed_time=5.0,
                pointer_pos=0.5,
                loop_start=1.0,
                loop_end=2.0,
                speed_ratio=0.01,
                loop_start_drift_rate=0.02,
                stream_duration=30.0
            )
            mock_warn.assert_not_called()


# =============================================================================
# GRUPPO 2: Contenuto del messaggio di log
# =============================================================================

class TestLogLoopDriftWarningContent:
    """Verifica che il messaggio contenga le informazioni diagnostiche attese."""

    def test_message_contains_loop_drift_tag(self, memory_logger):
        """Il messaggio contiene il tag [LOOP_DRIFT]."""
        log_loop_drift_warning(
            stream_id='texture1',
            elapsed_time=10.0,
            pointer_pos=0.63,
            loop_start=0.84,
            loop_end=1.44,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        assert len(memory_logger) == 1
        assert 'LOOP_DRIFT' in memory_logger[0].getMessage()

    def test_message_contains_stream_id(self, memory_logger):
        """Il messaggio contiene lo stream_id."""
        log_loop_drift_warning(
            stream_id='my_stream_42',
            elapsed_time=5.0,
            pointer_pos=0.3,
            loop_start=0.5,
            loop_end=1.0,
            speed_ratio=0.01,
            loop_start_drift_rate=0.01,
            stream_duration=20.0
        )
        assert 'my_stream_42' in memory_logger[0].getMessage()

    def test_message_contains_elapsed_time(self, memory_logger):
        """Il messaggio contiene il tempo elapsed."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=15.5,
            pointer_pos=0.1,
            loop_start=0.5,
            loop_end=1.0,
            speed_ratio=0.005,
            loop_start_drift_rate=0.02,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        assert '15' in msg  # il valore numerico e' presente

    def test_message_contains_pointer_pos(self, memory_logger):
        """Il messaggio contiene la posizione del pointer."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.6300,
            loop_start=0.84,
            loop_end=1.44,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        assert '0.6300' in msg or '0.63' in msg

    def test_message_contains_loop_bounds(self, memory_logger):
        """Il messaggio contiene loop_start e loop_end."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.2000,
            loop_end=2.4000,
            speed_ratio=0.003,
            loop_start_drift_rate=0.02,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        assert '1.2' in msg
        assert '2.4' in msg

    def test_message_contains_speed_ratio(self, memory_logger):
        """Il messaggio contiene lo speed_ratio."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.02,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        assert '0.003' in msg

    def test_message_contains_drift_rate(self, memory_logger):
        """Il messaggio contiene loop_start_drift_rate."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        assert '0.024' in msg

    def test_message_contains_ratio_actual_over_needed(self, memory_logger):
        """Il messaggio contiene il ratio speed_attuale/speed_necessaria."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        # 0.003 / 0.024 = 0.125x
        assert '0.125' in msg or '0.12' in msg

    def test_message_level_is_warning(self, memory_logger):
        """Il log e' emesso a livello WARNING."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        assert memory_logger[0].levelno == logging.WARNING


# =============================================================================
# GRUPPO 3: Calcolo del ratio speed / drift_rate
# =============================================================================

class TestLoopDriftRatioCalculation:
    """Verifica il calcolo del ratio diagnostico."""

    def test_ratio_is_one_when_speeds_equal(self, memory_logger):
        """Se speed_ratio == drift_rate, il ratio e' 1.0x."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.05,
            loop_start_drift_rate=0.05,
            stream_duration=30.0
        )
        msg = memory_logger[0].getMessage()
        assert '1.000' in msg or '1.0x' in msg or '1.00' in msg

    def test_ratio_zero_drift_rate_no_crash(self, memory_logger):
        """drift_rate=0 non solleva divisione per zero."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.0,    # caso critico
            stream_duration=30.0
        )
        # Non deve sollevare ZeroDivisionError
        assert len(memory_logger) == 1

    def test_ratio_negative_drift_no_crash(self, memory_logger):
        """drift_rate negativo (loop si sposta indietro) non causa crash."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=2.0,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=-0.003,
            loop_start_drift_rate=-0.01,
            stream_duration=30.0
        )
        assert len(memory_logger) == 1

    def test_ratio_very_slow_speed_shows_small_fraction(self, memory_logger):
        """Speed molto bassa rispetto al drift produce ratio < 1."""
        log_loop_drift_warning(
            stream_id='texture1',
            elapsed_time=10.0,
            pointer_pos=0.63,
            loop_start=0.84,
            loop_end=1.44,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        msg = memory_logger[0].getMessage()
        # 0.003/0.024 = 0.125 — un ottavo
        # Verifica che il ratio sia < 1 nella stringa
        assert '0.1' in msg  # 0.125 inizia con 0.1


# =============================================================================
# GRUPPO 4: Loop length nel messaggio
# =============================================================================

class TestLoopLengthInMessage:
    """Verifica che la lunghezza del loop sia calcolata e mostrata."""

    def test_loop_length_shown(self, memory_logger):
        """La lunghezza loop_end - loop_start appare nel messaggio."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=3.5,   # loop_length = 2.5
            speed_ratio=0.01,
            loop_start_drift_rate=0.02,
            stream_duration=30.0
        )
        msg = memory_logger[0].getMessage()
        assert '2.5' in msg or 'len=2.5' in msg

    def test_loop_length_zero_no_crash(self, memory_logger):
        """loop_start == loop_end (loop degenere) non causa crash."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=1.0,   # length = 0
            speed_ratio=0.01,
            loop_start_drift_rate=0.02,
            stream_duration=30.0
        )
        assert len(memory_logger) == 1


# =============================================================================
# GRUPPO 5: Valori al limite e edge cases
# =============================================================================

class TestLoopDriftEdgeCases:
    """Edge cases numerici e di boundary."""

    def test_elapsed_zero(self, memory_logger):
        """elapsed_time=0 e' valido (primo grano dello stream)."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=0.0,
            pointer_pos=0.2,
            loop_start=0.5,
            loop_end=1.0,
            speed_ratio=0.001,
            loop_start_drift_rate=0.0,
            stream_duration=60.0
        )
        assert len(memory_logger) == 1

    def test_pointer_inside_loop_still_logs(self, memory_logger):
        """
        Il log viene emesso anche se pointer_pos e' dentro il loop.
        La funzione e' di diagnostica pura — non giudica se ha senso.
        """
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=1.2,   # dentro [1.0, 2.0]
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.024,
            stream_duration=60.0
        )
        assert len(memory_logger) == 1

    def test_very_large_elapsed_time(self, memory_logger):
        """elapsed_time molto grande non causa overflow o crash."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=3600.0,   # 1 ora
            pointer_pos=10.0,
            loop_start=50.0,
            loop_end=60.0,
            speed_ratio=0.001,
            loop_start_drift_rate=0.013,
            stream_duration=3600.0
        )
        assert len(memory_logger) == 1

    def test_speed_ratio_positive(self, memory_logger):
        """speed_ratio positivo (avanti) funziona correttamente."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.5,
            loop_start_drift_rate=0.02,
            stream_duration=30.0
        )
        msg = memory_logger[0].getMessage()
        assert '0.5' in msg

    def test_speed_ratio_zero(self, memory_logger):
        """speed_ratio=0 (pointer fermo) non causa divisione per zero nel ratio."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=10.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.0,
            loop_start_drift_rate=0.02,
            stream_duration=30.0
        )
        assert len(memory_logger) == 1

    @pytest.mark.parametrize("stream_id", [
        'texture1', 'voice_2', 'stream-with-dashes', 'x', 'stream_123_abc'
    ])
    def test_various_stream_ids(self, stream_id, memory_logger):
        """Vari formati di stream_id vengono loggati correttamente."""
        log_loop_drift_warning(
            stream_id=stream_id,
            elapsed_time=5.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.02,
            stream_duration=30.0
        )
        assert len(memory_logger) == 1
        assert stream_id in memory_logger[0].getMessage()


# =============================================================================
# GRUPPO 6: Una sola chiamata emette un solo record
# =============================================================================

class TestLogLoopDriftSingleRecord:
    """Una chiamata deve produrre esattamente un record di log."""

    def test_single_call_single_record(self, memory_logger):
        """Una chiamata → un solo record."""
        log_loop_drift_warning(
            stream_id='s1',
            elapsed_time=5.0,
            pointer_pos=0.5,
            loop_start=1.0,
            loop_end=2.0,
            speed_ratio=0.003,
            loop_start_drift_rate=0.02,
            stream_duration=30.0
        )
        assert len(memory_logger) == 1

    def test_multiple_calls_multiple_records(self, memory_logger):
        """N chiamate → N record indipendenti."""
        for i in range(3):
            log_loop_drift_warning(
                stream_id=f'stream_{i}',
                elapsed_time=float(i * 5),
                pointer_pos=0.5,
                loop_start=1.0,
                loop_end=2.0,
                speed_ratio=0.003,
                loop_start_drift_rate=0.02,
                stream_duration=30.0
            )
        assert len(memory_logger) == 3