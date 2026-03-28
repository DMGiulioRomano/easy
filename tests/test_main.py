# tests/test_main.py
"""
Test suite per src/main.py.

Copre:
- Costanti di sicurezza a livello modulo
- main(): parsing argomenti (yaml, output, flags)
- main(): flusso normale completo
- main(): generazione visualizzazione PDF (--visualize, -v)
- main(): flag --show-static / -s
- main(): FileNotFoundError -> sys.exit(1)
- main(): eccezione generica -> sys.exit(1)
- main(): argomenti insufficienti -> sys.exit(1)
- main(): output_file di default 'output.sco'
- main(): seconda chiamata a configure_clip_logger con yaml_basename
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, patch, call


# =============================================================================
# SETUP MOCK MODULI ESTERNI
# Prima di importare main, blocchiamo le dipendenze pesanti
# =============================================================================

def _make_mock_generator_module():
    mod = types.ModuleType('generator')
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mod.Generator = mock_cls
    return mod, mock_cls, mock_instance


def _make_mock_score_visualizer_module():
    mod = types.ModuleType('score_visualizer')
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mod.ScoreVisualizer = mock_cls
    return mod, mock_cls, mock_instance


def _make_mock_logger_module():
    mod = types.ModuleType('logger')
    mod.configure_clip_logger = MagicMock()
    mod.get_clip_log_path = MagicMock(return_value='/tmp/test.log')
    return mod


# =============================================================================
# FIXTURE CENTRALE
# Ogni test ottiene mock freschi per isolamento completo
# =============================================================================

@pytest.fixture
def mocks():
    """
    Restituisce un dict con tutti i mock necessari e importa main
    in un ambiente controllato.
    """
    gen_mod, gen_cls, gen_inst = _make_mock_generator_module()
    viz_mod, viz_cls, viz_inst = _make_mock_score_visualizer_module()
    log_mod = _make_mock_logger_module()

    mock_modules = {
        'engine.generator': gen_mod,
        'rendering.score_visualizer': viz_mod,
        'shared.logger': log_mod,
        # dipendenze transitive
        'yaml': types.ModuleType('yaml'),
        'soundfile': types.ModuleType('soundfile'),
    }

    with patch.dict(sys.modules, mock_modules):
        # Forza reimport di main in ogni test per avere stato pulito
        if 'main' in sys.modules:
            del sys.modules['main']

        import importlib
        main_mod = importlib.import_module('main')

    return {
        'main': main_mod,
        'Generator': gen_cls,
        'generator_instance': gen_inst,
        'ScoreVisualizer': viz_cls,
        'visualizer_instance': viz_inst,
        'configure_clip_logger': log_mod.configure_clip_logger,
        'get_clip_log_path': log_mod.get_clip_log_path,
    }


# =============================================================================
# HELPER
# =============================================================================

def run_main(mocks, argv_list):
    """Esegue main.main() con sys.argv specificato."""
    with patch.dict(sys.modules, {
        'generator': sys.modules.get('generator', MagicMock()),
        'score_visualizer': sys.modules.get('score_visualizer', MagicMock()),
        'logger': sys.modules.get('logger', MagicMock()),
    }):
        with patch.object(sys, 'argv', argv_list):
            mocks['main'].main()


# =============================================================================
# TEST ARGOMENTI INSUFFICIENTI
# =============================================================================

class TestInsufficientArguments:
    """
    main() deve stampare l'uso e chiamare sys.exit(1)
    se sys.argv ha meno di 2 elementi.
    """

    def test_no_args_exits_with_1(self, mocks):
        with patch.object(sys, 'argv', ['main.py']):
            with pytest.raises(SystemExit) as exc_info:
                mocks['main'].main()
        assert exc_info.value.code == 1

    def test_no_args_prints_usage(self, mocks, capsys):
        with patch.object(sys, 'argv', ['main.py']):
            with pytest.raises(SystemExit):
                mocks['main'].main()
        captured = capsys.readouterr()
        assert 'python main.py' in captured.out
        assert '.yml' in captured.out


# =============================================================================
# TEST FLUSSO NORMALE
# =============================================================================

class TestNormalFlow:
    """
    Verifica il flusso nominale: yaml -> load -> create -> score file.
    """

    def test_generator_created_with_yaml_path(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['Generator'].assert_called_once_with('test.yml')

    def test_load_yaml_called(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['generator_instance'].load_yaml.assert_called_once()

    def test_create_elements_called(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['generator_instance'].create_elements.assert_called_once()

    def test_generate_score_file_called_with_output(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_called_once_with('out.sco')

    def test_default_output_file_is_output_sco(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_called_once_with('output.sco')

    def test_get_clip_log_path_called(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['get_clip_log_path'].assert_called()

    def test_score_visualizer_not_called_without_flag(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['ScoreVisualizer'].assert_not_called()

    def test_execution_order(self, mocks):
        """load_yaml deve precedere create_elements che precede generate_score_file."""
        call_order = []
        inst = mocks['generator_instance']
        inst.load_yaml.side_effect = lambda: call_order.append('load_yaml')
        inst.create_elements.side_effect = lambda: call_order.append('create_elements')
        inst.generate_score_file.side_effect = lambda x: call_order.append('generate_score_file')

        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()

        assert call_order == ['load_yaml', 'create_elements', 'generate_score_file']


# =============================================================================
# TEST CONFIGURAZIONE LOGGER
# =============================================================================

class TestLoggerConfiguration:
    """
    main() deve chiamare configure_clip_logger una seconda volta
    con yaml_basename estratto dal path del file YAML.
    """

    def test_configure_logger_called_with_yaml_basename(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'path/to/myfile.yml', 'out.sco']):
            mocks['main'].main()

        calls = mocks['configure_clip_logger'].call_args_list
        # La seconda chiamata (dentro main()) deve avere yaml_name='myfile'
        second_call_kwargs = calls[-1][1]
        assert second_call_kwargs.get('yaml_name') == 'myfile'

    def test_configure_logger_second_call_has_file_enabled(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()

        calls = mocks['configure_clip_logger'].call_args_list
        second_call_kwargs = calls[-1][1]
        assert second_call_kwargs.get('file_enabled') is True

    def test_configure_logger_second_call_console_disabled(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()

        calls = mocks['configure_clip_logger'].call_args_list
        second_call_kwargs = calls[-1][1]
        assert second_call_kwargs.get('console_enabled') is False

    def test_yaml_basename_without_directory(self, mocks):
        """Basename estratto correttamente anche senza directory."""
        with patch.object(sys, 'argv', ['main.py', 'solo.yml']):
            mocks['main'].main()

        calls = mocks['configure_clip_logger'].call_args_list
        second_call_kwargs = calls[-1][1]
        assert second_call_kwargs.get('yaml_name') == 'solo'


# =============================================================================
# TEST FLAG --visualize / -v
# =============================================================================

class TestVisualizationFlag:
    """
    Con --visualize o -v, main() deve creare ScoreVisualizer ed esportare PDF.
    """

    def test_visualize_long_flag_creates_visualizer(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--visualize']):
            mocks['main'].main()
        mocks['ScoreVisualizer'].assert_called_once()

    def test_visualize_short_flag_creates_visualizer(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '-v']):
            mocks['main'].main()
        mocks['ScoreVisualizer'].assert_called_once()

    def test_visualizer_receives_generator_instance(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--visualize']):
            mocks['main'].main()
        args, kwargs = mocks['ScoreVisualizer'].call_args
        assert args[0] is mocks['generator_instance']

    def test_visualizer_receives_config_dict(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--visualize']):
            mocks['main'].main()
        args, kwargs = mocks['ScoreVisualizer'].call_args
        assert 'config' in kwargs
        assert isinstance(kwargs['config'], dict)

    def test_visualizer_config_has_page_duration(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--visualize']):
            mocks['main'].main()
        _, kwargs = mocks['ScoreVisualizer'].call_args
        assert 'page_duration' in kwargs['config']

    def test_export_pdf_called_with_correct_path(self, mocks):
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--visualize']):
            mocks['main'].main()
        mocks['visualizer_instance'].export_pdf.assert_called_once_with('out.pdf')

    def test_export_pdf_derives_name_from_sco(self, mocks):
        """PDF deve avere lo stesso nome base del file .sco."""
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'my_score.sco', '--visualize']):
            mocks['main'].main()
        mocks['visualizer_instance'].export_pdf.assert_called_once_with('my_score.pdf')


    def test_default_output_sco_no_third_arg(self, mocks):
        """Senza terzo argomento, generate_score_file riceve 'output.sco'."""
        with patch.object(sys, 'argv', ['main.py', 'test.yml']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_called_once_with('output.sco')

# =============================================================================
# TEST FLAG --show-static / -s
# =============================================================================

class TestShowStaticFlag:
    """
    Con --show-static o -s, la config passata a ScoreVisualizer
    deve includere show_static_params=True.
    """

    def _get_viz_config(self, mocks, argv):
        with patch.object(sys, 'argv', argv):
            mocks['main'].main()
        _, kwargs = mocks['ScoreVisualizer'].call_args
        return kwargs['config']

    def test_show_static_long_flag(self, mocks):
        config = self._get_viz_config(
            mocks,
            ['main.py', 'test.yml', 'out.sco', '--visualize', '--show-static']
        )
        assert config.get('show_static_params') is True

    def test_show_static_short_flag(self, mocks):
        config = self._get_viz_config(
            mocks,
            ['main.py', 'test.yml', 'out.sco', '--visualize', '-s']
        )
        assert config.get('show_static_params') is True

    def test_show_static_false_without_flag(self, mocks):
        config = self._get_viz_config(
            mocks,
            ['main.py', 'test.yml', 'out.sco', '--visualize']
        )
        assert config.get('show_static_params') is False

    def test_show_static_without_visualize_does_not_create_visualizer(self, mocks):
        """--show-static senza --visualize non deve creare ScoreVisualizer."""
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--show-static']):
            mocks['main'].main()
        mocks['ScoreVisualizer'].assert_not_called()


# =============================================================================
# TEST GESTIONE ERRORI
# =============================================================================

class TestErrorHandling:
    """
    main() deve catturare errori e uscire con codice 1.
    """

    def test_file_not_found_exits_with_1(self, mocks):
        mocks['generator_instance'].load_yaml.side_effect = FileNotFoundError("not found")
        with patch.object(sys, 'argv', ['main.py', 'missing.yml', 'out.sco']):
            with pytest.raises(SystemExit) as exc_info:
                mocks['main'].main()
        assert exc_info.value.code == 1

    def test_file_not_found_prints_error_message(self, mocks, capsys):
        mocks['generator_instance'].load_yaml.side_effect = FileNotFoundError()
        with patch.object(sys, 'argv', ['main.py', 'missing.yml', 'out.sco']):
            with pytest.raises(SystemExit):
                mocks['main'].main()
        captured = capsys.readouterr()
        assert 'missing.yml' in captured.out

    def test_generic_exception_exits_with_1(self, mocks):
        mocks['generator_instance'].create_elements.side_effect = RuntimeError("boom")
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            with pytest.raises(SystemExit) as exc_info:
                mocks['main'].main()
        assert exc_info.value.code == 1

    def test_generic_exception_prints_error(self, mocks, capsys):
        mocks['generator_instance'].create_elements.side_effect = ValueError("bad value")
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            with pytest.raises(SystemExit):
                mocks['main'].main()
        captured = capsys.readouterr()
        assert 'bad value' in captured.out

    def test_generate_score_file_exception_exits_with_1(self, mocks):
        mocks['generator_instance'].generate_score_file.side_effect = IOError("disk full")
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            with pytest.raises(SystemExit) as exc_info:
                mocks['main'].main()
        assert exc_info.value.code == 1

    def test_visualizer_exception_exits_with_1(self, mocks):
        mocks['visualizer_instance'].export_pdf.side_effect = Exception("pdf error")
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--visualize']):
            with pytest.raises(SystemExit) as exc_info:
                mocks['main'].main()
        assert exc_info.value.code == 1


# =============================================================================
# TEST FLAG --per-stream / -p
# =============================================================================

class TestPerStreamFlag:
    """
    Con --per-stream o -p, main() deve chiamare
    generate_score_files_per_stream() invece di generate_score_file().
    """

    def test_per_stream_long_flag_calls_per_stream_method(self, mocks):
        """--per-stream chiama generate_score_files_per_stream."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--per-stream']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_files_per_stream.assert_called_once()

    def test_per_stream_short_flag_calls_per_stream_method(self, mocks):
        """-p chiama generate_score_files_per_stream."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '-p']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_files_per_stream.assert_called_once()

    def test_per_stream_does_not_call_generate_score_file(self, mocks):
        """Con --per-stream, generate_score_file non viene chiamato."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--per-stream']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_not_called()

    def test_without_per_stream_calls_generate_score_file(self, mocks):
        """Senza --per-stream, generate_score_file viene chiamato normalmente."""
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_called_once()

    def test_per_stream_passes_output_dir_from_output_file(self, mocks):
        """output_dir viene estratta dal dirname di output_file."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'scores/out.sco', '--per-stream']):
            mocks['main'].main()
        call_kwargs = mocks['generator_instance'].generate_score_files_per_stream.call_args.kwargs
        assert call_kwargs['output_dir'] == 'scores'

    def test_per_stream_passes_base_name_from_output_file(self, mocks):
        """base_name viene estratto dal basename senza estensione di output_file."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'scores/my_piece.sco', '--per-stream']):
            mocks['main'].main()
        call_kwargs = mocks['generator_instance'].generate_score_files_per_stream.call_args.kwargs
        assert call_kwargs['base_name'] == 'my_piece'

    def test_per_stream_default_output_file_uses_current_dir(self, mocks):
        """Senza output_file esplicito, output_dir e' la dir corrente."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', '--per-stream']):
            mocks['main'].main()
        call_kwargs = mocks['generator_instance'].generate_score_files_per_stream.call_args.kwargs
        assert call_kwargs['output_dir'] == '.'

    def test_per_stream_exception_exits_with_1(self, mocks):
        """Un errore in generate_score_files_per_stream causa sys.exit(1)."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(
            side_effect=IOError("disk full")
        )
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--per-stream']):
            with pytest.raises(SystemExit) as exc_info:
                mocks['main'].main()
        assert exc_info.value.code == 1# =============================================================================
# TEST FLAG --renderer csound|numpy
# =============================================================================

class TestRendererFlag:
    """
    Verifica il parsing di --renderer e il branching corretto tra
    ramo csound (default) e ramo numpy.

    I tre moduli lazy del ramo numpy (RendererFactory, SampleRegistry,
    NumpyWindowRegistry) vengono patchati a runtime via patch.dict
    perche' sono importati dentro main() al momento dell'esecuzione,
    non al caricamento del modulo.
    """

    # -------------------------------------------------------------------------
    # HELPER INTERNI
    # -------------------------------------------------------------------------

    def _make_numpy_modules(self):
        """
        Costruisce i tre moduli mock per il ramo numpy.

        Returns:
            tuple: (mock_modules_dict, factory_cls, renderer_instance,
                    sample_reg_instance, window_reg_instance)
        """
        # RendererFactory
        factory_cls = MagicMock(name='RendererFactory')
        renderer_instance = MagicMock(name='renderer_instance')
        factory_cls.create.return_value = renderer_instance

        factory_mod = types.ModuleType('rendering.renderer_factory')
        factory_mod.RendererFactory = factory_cls

        # SampleRegistry
        sample_reg_cls = MagicMock(name='SampleRegistry')
        sample_reg_instance = MagicMock(name='sample_reg_instance')
        sample_reg_cls.return_value = sample_reg_instance

        sample_reg_mod = types.ModuleType('rendering.sample_registry')
        sample_reg_mod.SampleRegistry = sample_reg_cls

        # NumpyWindowRegistry
        window_reg_cls = MagicMock(name='NumpyWindowRegistry')
        window_reg_instance = MagicMock(name='window_reg_instance')
        window_reg_cls.return_value = window_reg_instance

        window_reg_mod = types.ModuleType('rendering.numpy_window_registry')
        window_reg_mod.NumpyWindowRegistry = window_reg_cls

        modules = {
            'rendering.renderer_factory': factory_mod,
            'rendering.sample_registry': sample_reg_mod,
            'rendering.numpy_window_registry': window_reg_mod,
        }

        return (
            modules,
            factory_cls, renderer_instance,
            sample_reg_cls, sample_reg_instance,
            window_reg_cls, window_reg_instance,
        )

    def _setup_generator_for_numpy(self, mocks, table_map=None, streams=None):
        """
        Configura il generator_instance mock per il ramo numpy.

        Args:
            table_map: dict {int: (ftype, key)} da restituire da get_all_tables().
                       Default: {1: ('sample', 'voice.wav'), 2: ('window', 'hanning')}
            streams:   lista di stream mock. Default: un solo stream con stream_id='s1'
        """
        if table_map is None:
            table_map = {
                1: ('sample', 'voice.wav'),
                2: ('window', 'hanning'),
            }
        if streams is None:
            mock_stream = MagicMock()
            mock_stream.stream_id = 's1'
            streams = [mock_stream]

        mocks['generator_instance'].ftable_manager.get_all_tables.return_value = table_map
        mocks['generator_instance'].streams = streams
        return streams

    # -------------------------------------------------------------------------
    # TEST DEFAULT E PARSING
    # -------------------------------------------------------------------------

    def test_default_renderer_is_csound(self, mocks):
        """Senza --renderer, il flusso csound rimane attivo."""
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_called_once_with('out.sco')

    def test_renderer_csound_explicit(self, mocks):
        """--renderer csound esplicito attiva il flusso csound."""
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'csound']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_file.assert_called_once_with('out.sco')

    def test_renderer_numpy_does_not_call_generate_score_file(self, mocks):
        """Con --renderer numpy, generate_score_file NON viene chiamato."""
        modules, *_ = self._make_numpy_modules()
        self._setup_generator_for_numpy(mocks)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        mocks['generator_instance'].generate_score_file.assert_not_called()

    def test_renderer_csound_does_not_call_renderer_factory(self, mocks):
        """Con --renderer csound, RendererFactory.create NON viene chiamato."""
        modules, factory_cls, *_ = self._make_numpy_modules()

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'csound']):
                mocks['main'].main()

        factory_cls.create.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST RAMO NUMPY: COSTRUZIONE RENDERER
    # -------------------------------------------------------------------------

    def test_renderer_numpy_calls_renderer_factory_create(self, mocks):
        """Con --renderer numpy, RendererFactory.create viene chiamato una volta."""
        modules, factory_cls, *_ = self._make_numpy_modules()
        self._setup_generator_for_numpy(mocks)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        factory_cls.create.assert_called_once()

    def test_renderer_numpy_factory_receives_numpy_type(self, mocks):
        """RendererFactory.create riceve 'numpy' come primo argomento."""
        modules, factory_cls, *_ = self._make_numpy_modules()
        self._setup_generator_for_numpy(mocks)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        call_args = factory_cls.create.call_args
        assert call_args.args[0] == 'numpy'

    def test_renderer_numpy_factory_receives_output_sr_48000(self, mocks):
        """RendererFactory.create riceve output_sr=48000."""
        modules, factory_cls, *_ = self._make_numpy_modules()
        self._setup_generator_for_numpy(mocks)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        call_kwargs = factory_cls.create.call_args.kwargs
        assert call_kwargs.get('output_sr') == 48000

    def test_renderer_numpy_factory_receives_table_map(self, mocks):
        """RendererFactory.create riceve il table_map da ftable_manager."""
        modules, factory_cls, *_ = self._make_numpy_modules()
        table_map = {1: ('sample', 'piano.wav')}
        self._setup_generator_for_numpy(mocks, table_map=table_map)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        call_kwargs = factory_cls.create.call_args.kwargs
        assert call_kwargs.get('table_map') == table_map

    # -------------------------------------------------------------------------
    # TEST RAMO NUMPY: CARICAMENTO SAMPLE
    # -------------------------------------------------------------------------

    def test_renderer_numpy_loads_sample_entries(self, mocks):
        """sample_reg.load viene chiamato per ogni entry 'sample' nel table_map."""
        modules, _, _, sample_reg_cls, sample_reg_instance, *_ = self._make_numpy_modules()
        table_map = {
            1: ('sample', 'voice.wav'),
            2: ('sample', 'piano.wav'),
            3: ('window', 'hanning'),
        }
        self._setup_generator_for_numpy(mocks, table_map=table_map)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        assert sample_reg_instance.load.call_count == 2
        loaded_args = [c.args[0] for c in sample_reg_instance.load.call_args_list]
        assert 'voice.wav' in loaded_args
        assert 'piano.wav' in loaded_args

    def test_renderer_numpy_does_not_load_window_entries(self, mocks):
        """sample_reg.load NON viene chiamato per entry 'window' nel table_map."""
        modules, _, _, sample_reg_cls, sample_reg_instance, *_ = self._make_numpy_modules()
        table_map = {
            1: ('window', 'hanning'),
            2: ('window', 'expodec'),
        }
        self._setup_generator_for_numpy(mocks, table_map=table_map)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        sample_reg_instance.load.assert_not_called()

    def test_renderer_numpy_empty_table_map_no_load(self, mocks):
        """table_map vuoto: sample_reg.load non viene mai chiamato."""
        modules, _, _, sample_reg_cls, sample_reg_instance, *_ = self._make_numpy_modules()
        self._setup_generator_for_numpy(mocks, table_map={})

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        sample_reg_instance.load.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST RAMO NUMPY: RENDER PER STREAM
    # -------------------------------------------------------------------------

    def test_renderer_numpy_calls_render_stream_once_per_stream(self, mocks):
        """render_stream viene chiamato una volta per ogni stream."""
        modules, _, renderer_instance, *_ = self._make_numpy_modules()

        s1 = MagicMock(); s1.stream_id = 's1'
        s2 = MagicMock(); s2.stream_id = 's2'
        s3 = MagicMock(); s3.stream_id = 's3'
        self._setup_generator_for_numpy(mocks, streams=[s1, s2, s3])

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        assert renderer_instance.render_stream.call_count == 3

    def test_renderer_numpy_aif_path_contains_stream_id(self, mocks):
        """Il path .aif passato a render_stream contiene lo stream_id."""
        modules, _, renderer_instance, *_ = self._make_numpy_modules()

        s1 = MagicMock(); s1.stream_id = 'melody'
        self._setup_generator_for_numpy(mocks, streams=[s1])

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        call_args = renderer_instance.render_stream.call_args
        aif_path = call_args.args[1]
        assert 'melody' in aif_path

    def test_renderer_numpy_aif_path_has_aif_extension(self, mocks):
        """Il path passato a render_stream ha estensione .aif."""
        modules, _, renderer_instance, *_ = self._make_numpy_modules()
        s1 = MagicMock(); s1.stream_id = 's1'
        self._setup_generator_for_numpy(mocks, streams=[s1])

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        call_args = renderer_instance.render_stream.call_args
        aif_path = call_args.args[1]
        assert aif_path.endswith('.aif')

    def test_renderer_numpy_render_stream_receives_stream_object(self, mocks):
        """render_stream riceve il corretto oggetto stream come primo argomento."""
        modules, _, renderer_instance, *_ = self._make_numpy_modules()
        s1 = MagicMock(); s1.stream_id = 's1'
        self._setup_generator_for_numpy(mocks, streams=[s1])

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        call_args = renderer_instance.render_stream.call_args
        assert call_args.args[0] is s1

    def test_renderer_numpy_no_streams_render_never_called(self, mocks):
        """Nessuno stream: render_stream non viene mai chiamato."""
        modules, _, renderer_instance, *_ = self._make_numpy_modules()
        self._setup_generator_for_numpy(mocks, streams=[])

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                mocks['main'].main()

        renderer_instance.render_stream.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST COMPATIBILITA' CON ALTRI FLAG
    # -------------------------------------------------------------------------

    def test_renderer_csound_with_per_stream_still_works(self, mocks):
        """--renderer csound + --per-stream chiama generate_score_files_per_stream."""
        mocks['generator_instance'].generate_score_files_per_stream = MagicMock(return_value=[])
        with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'csound', '--per-stream']):
            mocks['main'].main()
        mocks['generator_instance'].generate_score_files_per_stream.assert_called_once()
        mocks['generator_instance'].generate_score_file.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST GESTIONE ERRORI
    # -------------------------------------------------------------------------

    def test_renderer_numpy_exception_exits_with_1(self, mocks):
        """Un errore durante render_stream nel ramo numpy causa sys.exit(1)."""
        modules, _, renderer_instance, *_ = self._make_numpy_modules()
        renderer_instance.render_stream.side_effect = RuntimeError("render failed")
        s1 = MagicMock(); s1.stream_id = 's1'
        self._setup_generator_for_numpy(mocks, streams=[s1])

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                with pytest.raises(SystemExit) as exc_info:
                    mocks['main'].main()

        assert exc_info.value.code == 1

    def test_renderer_numpy_factory_exception_exits_with_1(self, mocks):
        """Un errore in RendererFactory.create causa sys.exit(1)."""
        modules, factory_cls, *_ = self._make_numpy_modules()
        factory_cls.create.side_effect = ValueError("unknown renderer")
        self._setup_generator_for_numpy(mocks)

        with patch.dict(sys.modules, modules):
            with patch.object(sys, 'argv', ['main.py', 'test.yml', 'out.sco', '--renderer', 'numpy']):
                with pytest.raises(SystemExit) as exc_info:
                    mocks['main'].main()

        assert exc_info.value.code == 1