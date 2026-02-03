"""
test_pointer_controller_bidirectional.py

Suite di test completa per PointerController con supporto bidirezionale.
Copre tutti i casi edge con speed_ratio positivo, negativo, ed envelope.

Test Coverage:
- Movimento lineare (forward/backward/envelope/zero)
- Entrata nel loop (da entrambe le direzioni)
- Wrap modulare unificato (forward/backward/multiplo)
- Reset direction-aware quando bounds cambiano
- Loop dinamici con envelope
- Inversioni di direzione durante il loop
- Edge cases estremi
"""

import pytest
from unittest.mock import Mock, patch
from pointer_controller import PointerController
from stream_config import StreamConfig, StreamContext
from parameter import Parameter
from parameter_definitions import ParameterBounds


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_config():
    """Config minimale per i test."""
    context = Mock(spec=StreamContext)
    context.stream_id = "test_stream"
    context.sample_dur_sec = 10.0
    
    config = Mock(spec=StreamConfig)
    config.context = context
    config.time_mode = 'absolute'
    
    return config


@pytest.fixture
def pointer_factory(mock_config):
    """
    Factory per creare PointerController con configurazioni custom.
    Usa Parameter reali con ParameterBounds corretti dal registry.
    
    Usage:
        pointer = pointer_factory({'start': 0, 'speed_ratio': 1.0})
    """
    from parameter import Parameter
    from parameter_definitions import ParameterBounds
    
    def _create(params: dict, sample_dur: float = None):
        if sample_dur:
            mock_config.context.sample_dur_sec = sample_dur
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            # ParameterBounds reali dal registry
            bounds_speed = ParameterBounds(
                min_val=-100.0,
                max_val=100.0
            )
            
            bounds_deviation = ParameterBounds(
                min_val=0.0,
                max_val=1.0,
                min_range=0.0,
                max_range=1.0,
                default_jitter=0.2,
                variation_mode='additive'
            )
            
            bounds_loop = ParameterBounds(
                min_val=0.0,
                max_val=100.0
            )
            
            bounds_loop_dur = ParameterBounds(
                min_val=0.005,
                max_val=100.0
            )
            
            # Crea Parameter REALI per ogni parametro
            real_params = {}
            
            # Parametri obbligatori con defaults
            start_value = params.get('start', 0.0)
            speed_value = params.get('speed_ratio', 1.0)
            
            # pointer_start: NON è uno smart parameter (is_smart=False)
            # Il ParameterOrchestrator restituisce il valore raw direttamente
            real_params['pointer_start'] = start_value
            
            # pointer_speed_ratio: Parameter reale con bounds
            real_params['pointer_speed_ratio'] = Parameter(
                value=speed_value,
                name='pointer_speed_ratio',
                bounds=bounds_speed,
                owner_id='test_stream'
            )
            
            # pointer_deviation: Parameter reale con bounds
            real_params['pointer_deviation'] = Parameter(
                value=0.0,
                name='pointer_deviation',
                bounds=bounds_deviation,
                owner_id='test_stream'
            )
            
            # Parametri loop opzionali
            if 'loop_start' in params:
                real_params['loop_start'] = Parameter(
                    value=params['loop_start'],
                    name='loop_start',
                    bounds=bounds_loop,
                    owner_id='test_stream'
                )
            else:
                real_params['loop_start'] = None
            
            if 'loop_end' in params:
                real_params['loop_end'] = Parameter(
                    value=params['loop_end'],
                    name='loop_end',
                    bounds=bounds_loop,
                    owner_id='test_stream'
                )
            else:
                real_params['loop_end'] = None
            
            if 'loop_dur' in params:
                real_params['loop_dur'] = Parameter(
                    value=params['loop_dur'],
                    name='loop_dur',
                    bounds=bounds_loop_dur,
                    owner_id='test_stream'
                )
            else:
                real_params['loop_dur'] = None
            
            mock_orch.create_all_parameters.return_value = real_params
            
            return PointerController(params, mock_config)
    
    return _create


# =============================================================================
# GRUPPO 1: MOVIMENTO LINEARE BASE
# =============================================================================

class TestLinearMovement:
    """Test movimento lineare senza loop."""
    
    def test_forward_constant_speed(self, pointer_factory):
        """Speed positivo costante."""
        pointer = pointer_factory({'start': 0.0, 'speed_ratio': 1.0})
        
        assert pointer.calculate(0.0) == pytest.approx(0.0)
        assert pointer.calculate(1.0) == pytest.approx(1.0)
        assert pointer.calculate(2.5) == pytest.approx(2.5)
    
    def test_backward_constant_speed(self, pointer_factory):
        """Speed negativo costante - movimento all'indietro."""
        pointer = pointer_factory({'start': 5.0, 'speed_ratio': -1.0})
        
        # t=0: pos = 5.0 + 0*(-1) = 5.0
        assert pointer.calculate(0.0) == pytest.approx(5.0)
        
        # t=1: pos = 5.0 + 1*(-1) = 4.0
        assert pointer.calculate(1.0) == pytest.approx(4.0)
        
        # t=2.5: pos = 5.0 + 2.5*(-1) = 2.5
        assert pointer.calculate(2.5) == pytest.approx(2.5)
    
    def test_backward_wraps_at_zero(self, pointer_factory):
        """Speed negativo wrappa quando raggiunge 0."""
        pointer = pointer_factory({'start': 3.0, 'speed_ratio': -1.0}, sample_dur=10.0)
        
        # t=5: pos = 3.0 + 5*(-1) = -2.0
        # wrap: -2.0 % 10.0 = 8.0
        pos = pointer.calculate(5.0)
        assert pos == pytest.approx(8.0)
    
    def test_zero_speed(self, pointer_factory):
        """Speed zero - posizione fissa."""
        pointer = pointer_factory({'start': 3.0, 'speed_ratio': 0.0})
        
        assert pointer.calculate(0.0) == pytest.approx(3.0)
        assert pointer.calculate(100.0) == pytest.approx(3.0)
    
    def test_very_high_forward_speed(self, pointer_factory):
        """Speed molto alto wrappa correttamente."""
        pointer = pointer_factory({'start': 0.0, 'speed_ratio': 100.0}, sample_dur=5.0)
        
        # t=1: pos = 100, wrap: 100 % 5 = 0
        pos = pointer.calculate(1.0)
        assert 0.0 <= pos < 5.0
    
    def test_very_high_backward_speed(self, pointer_factory):
        """Speed molto negativo wrappa correttamente."""
        pointer = pointer_factory({'start': 0.0, 'speed_ratio': -100.0}, sample_dur=5.0)
        
        # t=1: pos = -100, wrap: -100 % 5 = 0 (in Python)
        pos = pointer.calculate(1.0)
        assert 0.0 <= pos < 5.0


# =============================================================================
# GRUPPO 2: ENTRATA NEL LOOP
# =============================================================================

class TestLoopEntry:
    """Test entrata nel loop da diverse direzioni."""
    
    def test_entry_forward_motion(self, pointer_factory):
        """Entrata nel loop con movimento in avanti."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        # Prima dell'entrata
        assert pointer.in_loop is False
        pos = pointer.calculate(1.5)
        assert pos == pytest.approx(1.5)
        assert pointer.in_loop is False
        
        # Momento dell'entrata (linear_pos = 2.5)
        pos = pointer.calculate(2.5)
        assert pos == pytest.approx(2.5)
        assert pointer.in_loop is True
    
    def test_entry_backward_motion(self, pointer_factory):
        """Entrata nel loop con movimento all'indietro."""
        pointer = pointer_factory({
            'start': 8.0,
            'speed_ratio': -1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        # Prima dell'entrata (pos = 8.0 - 2 = 6.0, fuori loop)
        pos = pointer.calculate(2.0)
        assert pointer.in_loop is False
        
        # Entrata nel loop (pos = 8.0 - 4 = 4.0, dentro [2.0, 5.0])
        pos = pointer.calculate(4.0)
        assert pos == pytest.approx(4.0)
        assert pointer.in_loop is True
    
    def test_never_enters_loop_forward(self, pointer_factory):
        """Pointer non entra mai nel loop (troppo lento)."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 0.1,
            'loop_start': 5.0,
            'loop_end': 8.0
        })
        
        # t=10: pos = 1.0 (ancora prima del loop)
        pos = pointer.calculate(10.0)
        assert pointer.in_loop is False
        assert 0.0 <= pos < 10.0
    
    def test_never_enters_loop_backward(self, pointer_factory):
        """Pointer va all'indietro ma parte già dopo il loop."""
        pointer = pointer_factory({
            'start': 9.0,
            'speed_ratio': -0.1,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        # t=10: pos = 9.0 - 1.0 = 8.0 (ancora dopo il loop)
        pos = pointer.calculate(10.0)
        assert pointer.in_loop is False


# =============================================================================
# GRUPPO 3: WRAP MODULARE UNIFICATO (bounds stabili)
# =============================================================================

class TestUnifiedModularWrap:
    """Test wrap modulare quando bounds sono stabili."""
    
    def test_wrap_forward_single(self, pointer_factory):
        """Wrap forward singolo - supera loop_end."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0  # loop_length = 3.0
        })
        
        # Entra nel loop
        pointer.calculate(2.5)
        assert pointer.in_loop is True
        
        # Supera loop_end (linear = 5.5)
        # rel = 5.5 - 2.0 = 3.5
        # wrap = 3.5 % 3.0 = 0.5
        # pos = 2.0 + 0.5 = 2.5
        pos = pointer.calculate(5.5)
        assert pos == pytest.approx(2.5)
    
    def test_wrap_backward_single(self, pointer_factory):
        """Wrap backward singolo - sotto loop_start."""
        pointer = pointer_factory({
            'start': 4.0,
            'speed_ratio': -1.0,
            'loop_start': 2.0,
            'loop_end': 5.0  # loop_length = 3.0
        })
        
        # Entra nel loop
        pointer.calculate(0.0)
        assert pointer.in_loop is True
        
        # Esce sotto loop_start (linear = 4.0 - 2.5 = 1.5)
        # rel = 1.5 - 2.0 = -0.5
        # wrap = -0.5 % 3.0 = 2.5 (Python modulo)
        # pos = 2.0 + 2.5 = 4.5
        pos = pointer.calculate(2.5)
        assert pos == pytest.approx(4.5)
    
    def test_wrap_forward_multiple(self, pointer_factory):
        """Wrap forward multiplo - molti loop completi."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 10.0,  # Veloce!
            'loop_start': 2.0,
            'loop_end': 5.0  # loop_length = 3.0
        })
        
        # Entra nel loop
        pointer.calculate(0.25)
        
        # t=1: linear = 10.0 (supera di molto loop_end)
        # Ha fatto ~2.6 loop completi
        # rel = 10.0 - 2.0 = 8.0
        # wrap = 8.0 % 3.0 = 2.0
        # pos = 2.0 + 2.0 = 4.0
        pos = pointer.calculate(1.0)
        assert pos == pytest.approx(4.0)
        assert 2.0 <= pos < 5.0
    
    def test_wrap_backward_multiple(self, pointer_factory):
        """Wrap backward multiplo - molti loop indietro."""
        pointer = pointer_factory({
            'start': 4.0,
            'speed_ratio': -10.0,  # Molto veloce indietro!
            'loop_start': 2.0,
            'loop_end': 5.0  # loop_length = 3.0
        })
        
        # Entra nel loop
        pointer.calculate(0.0)
        
        # t=1: linear = 4.0 - 10.0 = -6.0
        # rel = -6.0 - 2.0 = -8.0
        # wrap = -8.0 % 3.0 = 1.0
        # pos = 2.0 + 1.0 = 3.0
        pos = pointer.calculate(1.0)
        assert pos == pytest.approx(3.0)
        assert 2.0 <= pos < 5.0
    
    def test_wrap_exactly_at_loop_end(self, pointer_factory):
        """Pointer arriva esattamente a loop_end."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        pointer.calculate(2.5)  # Entra
        
        # Esattamente a loop_end
        pos = pointer.calculate(5.0)
        # Dovrebbe wrappare a loop_start
        assert pos == pytest.approx(2.0)
    
    def test_wrap_exactly_at_loop_start_backward(self, pointer_factory):
        """Pointer arriva esattamente a loop_start andando indietro."""
        pointer = pointer_factory({
            'start': 4.0,
            'speed_ratio': -1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        pointer.calculate(0.0)  # Entra
        
        # Esattamente a loop_start (linear = 4.0 - 2.0 = 2.0)
        pos = pointer.calculate(2.0)
        # Dovrebbe essere valido (2.0 è dentro [2.0, 5.0))
        assert pos == pytest.approx(2.0)


# =============================================================================
# GRUPPO 4: RESET DIRECTION-AWARE (bounds cambiano)
# =============================================================================

class TestDirectionAwareReset:
    """Test reset direction-aware quando i bounds del loop cambiano."""
    
    def test_reset_forward_motion(self, pointer_factory):
        """Bounds cambiano mentre pointer va avanti → reset a loop_start."""
        # Setup con loop_start dinamico (envelope mock)
        params = {
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            # Mock parameters
            mock_params = {}
            
            # start (raw value, is_smart=False)
            mock_params['pointer_start'] = 0.0
            
            # speed_ratio
            param = Mock()
            param.value = 1.0
            param.get_value = Mock(return_value=1.0)
            mock_params['pointer_speed_ratio'] = param
            
            # deviation
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            # loop_start DINAMICO
            param = Mock()
            param.value = 2.0
            # Prima restituisce 2.0, poi 4.0 (bounds cambiano!)
            param.get_value = Mock(side_effect=[2.0, 2.0, 4.0, 4.0, 4.0, 4.0, 4.0])
            mock_params['loop_start'] = param
            
            # loop_end
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Entra nel loop con loop_start = 2.0
            pointer.calculate(2.5)
            assert pointer.in_loop is True
            
            # Avanza (delta_pos positivo)
            pointer.calculate(3.0)
            
            # Bounds cambiano: loop_start diventa 4.0
            # Pointer è a 3.5, fuori dai nuovi bounds [4.0, 5.0]
            # delta_pos > 0 → reset a loop_start (4.0)
            pos = pointer.calculate(3.5)
            
            # Dopo reset, pointer dovrebbe essere a 4.0
            assert pos == pytest.approx(4.0)
    
    def test_reset_backward_motion(self, pointer_factory):
        """Bounds cambiano mentre pointer va indietro → reset a loop_end."""
        params = {
            'start': 4.0,
            'speed_ratio': -1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            # start (raw value, is_smart=False)
            mock_params['pointer_start'] = 4.0
            
            # speed_ratio NEGATIVO
            param = Mock()
            param.value = -1.0
            param.get_value = Mock(return_value=-1.0)
            mock_params['pointer_speed_ratio'] = param
            
            # deviation
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            # loop_start DINAMICO
            param = Mock()
            param.value = 2.0
            # Prima 2.0, poi 3.0 (bounds cambiano!)
            # Aggiungiamo valori ripetuti per coprire tutte le chiamate successive
            param.get_value = Mock(side_effect=[2.0, 2.0, 3.0, 3.0, 3.0, 3.0, 3.0])
            mock_params['loop_start'] = param
            
            # loop_end
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Entra nel loop
            pointer.calculate(0.0)
            
            # Va indietro (delta_pos negativo)
            pointer.calculate(0.5)
            
            # Bounds cambiano: loop_start → 3.0
            # linear = 4.0 + 1.5*(-1) = 2.5
            # Pointer è a 3.5 + (-1.0) = 2.5, fuori [3.0, 5.0]
            # delta_pos < 0 → reset a loop_END (5.0)
            # MA: loop_end è boundary esclusivo, quindi 5.0 viene immediatamente
            # wrappato a loop_start (3.0) da wrap_fn
            pos = pointer.calculate(1.5)
            
            # Dopo reset e wrap, il pointer è a loop_start
            assert pos == pytest.approx(3.0)
    
    def test_bounds_change_but_pointer_inside(self, pointer_factory):
        """Bounds cambiano ma pointer resta dentro → NO reset."""
        params = {
            'start': 0.0,
            'speed_ratio': 0.5,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 0.0
            
            param = Mock()
            param.value = 0.5
            param.get_value = Mock(return_value=0.5)
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            # loop_start cambia ma pointer resta dentro
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(side_effect=[2.0, 2.0, 2.5, 2.5, 2.5, 2.5, 2.5])
            mock_params['loop_start'] = param
            
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Entra a 2.5
            pointer.calculate(5.0)
            
            # Avanza a ~3.0
            pointer.calculate(6.0)
            
            # Bounds cambiano: loop_start → 2.5
            # Pointer è a ~3.25, DENTRO [2.5, 5.0]
            # NO reset!
            pos = pointer.calculate(6.5)
            assert 2.5 <= pos < 5.0
            # Posizione continua progressione, non reset


# =============================================================================
# GRUPPO 5: INVERSIONE DI DIREZIONE DURANTE IL LOOP
# =============================================================================

class TestDirectionReversal:
    """Test inversione di speed_ratio durante il loop."""
    
    def test_forward_to_backward(self, pointer_factory):
        """Speed passa da positivo a negativo durante il loop."""
        params = {
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 0.0
            
            # speed_ratio che INVERTE
            param = Mock()
            param.value = 1.0
            param.get_value = Mock(side_effect=[1.0, 1.0, -1.0, -1.0, -1.0, -1.0, -1.0])
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(return_value=2.0)
            mock_params['loop_start'] = param
            
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            # Mock _calculate_linear_position per simulare inversione
            pointer = PointerController(params, config)
            
            # Entra nel loop andando avanti
            pointer._calculate_linear_position = Mock(return_value=2.5)
            pointer.calculate(2.5)
            assert pointer.in_loop is True
            
            # Avanza
            pointer._calculate_linear_position = Mock(return_value=3.5)
            pos1 = pointer.calculate(3.0)
            assert pos1 == pytest.approx(3.5)
            
            # INVERSIONE! linear_pos diventa minore (va indietro)
            pointer._calculate_linear_position = Mock(return_value=3.0)
            pos2 = pointer.calculate(3.5)
            
            # delta_pos negativo, dovrebbe gestire correttamente
            assert 2.0 <= pos2 < 5.0
    
    def test_backward_to_forward(self, pointer_factory):
        """Speed passa da negativo a positivo."""
        params = {
            'start': 4.0,
            'speed_ratio': -1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 4.0
            
            param = Mock()
            param.value = -1.0
            param.get_value = Mock(side_effect=[-1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(return_value=2.0)
            mock_params['loop_start'] = param
            
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Entra andando indietro
            pointer._calculate_linear_position = Mock(return_value=4.0)
            pointer.calculate(0.0)
            
            # Va indietro
            pointer._calculate_linear_position = Mock(return_value=3.0)
            pos1 = pointer.calculate(1.0)
            assert pos1 == pytest.approx(3.0)
            
            # INVERSIONE! Ora va avanti
            pointer._calculate_linear_position = Mock(return_value=3.5)
            pos2 = pointer.calculate(1.5)
            
            assert 2.0 <= pos2 < 5.0
    
    def test_oscillating_speed(self, pointer_factory):
        """Speed oscilla avanti/indietro continuamente."""
        params = {
            'start': 3.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 3.0
            
            param = Mock()
            param.value = 1.0
            param.get_value = Mock(return_value=1.0)
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(return_value=2.0)
            mock_params['loop_start'] = param
            
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Simula oscillazioni
            positions = [3.0, 3.5, 3.2, 3.8, 3.4, 4.0]
            
            for i, linear_pos in enumerate(positions):
                pointer._calculate_linear_position = Mock(return_value=linear_pos)
                pos = pointer.calculate(float(i))
                
                # Deve sempre restare dentro bounds
                assert 2.0 <= pos < 5.0


# =============================================================================
# GRUPPO 6: LOOP DINAMICI
# =============================================================================

class TestDynamicLoops:
    """Test loop con bounds che cambiano nel tempo (envelope)."""
    
    def test_shrinking_loop_dur(self, pointer_factory):
        """loop_dur diminuisce gradualmente."""
        params = {
            'start': 0.0,
            'speed_ratio': 0.5,
            'loop_start': 2.0,
            'loop_dur': 3.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 0.0
            
            param = Mock()
            param.value = 0.5
            param.get_value = Mock(return_value=0.5)
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(return_value=2.0)
            mock_params['loop_start'] = param
            
            # loop_dur che diminuisce
            param = Mock()
            param.value = 3.0
            param.get_value = Mock(side_effect=[3.0, 3.0, 2.5, 2.0, 1.5, 1.5, 1.5, 1.5])
            mock_params['loop_dur'] = param

            
            # loop_end opzionale (None quando si usa loop_dur)
            
            mock_params['loop_end'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Entra nel loop
            pointer.calculate(5.0)
            
            # Loop si restringe ma pointer deve restare valido
            pos1 = pointer.calculate(6.0)
            pos2 = pointer.calculate(7.0)
            pos3 = pointer.calculate(8.0)
            
            # Tutte le posizioni devono essere valide
            for pos in [pos1, pos2, pos3]:
                assert 2.0 <= pos < 10.0
    
    def test_moving_loop_start(self, pointer_factory):
        """loop_start si muove gradualmente."""
        params = {
            'start': 0.0,
            'speed_ratio': 0.5,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 0.0
            
            param = Mock()
            param.value = 0.5
            param.get_value = Mock(return_value=0.5)
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            # loop_start che si muove
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(side_effect=[2.0, 2.0, 2.5, 3.0, 3.5, 3.5, 3.5, 3.5])
            mock_params['loop_start'] = param
            
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Sequenza di calcoli con loop_start che si muove
            positions = []
            for i in range(5):
                pos = pointer.calculate(float(i * 2))
                positions.append(pos)
            
            # Tutte le posizioni devono essere valide (dentro sample)
            for pos in positions:
                assert 0.0 <= pos < 10.0


# =============================================================================
# GRUPPO 7: EDGE CASES ESTREMI
# =============================================================================

class TestExtremeEdgeCases:
    """Test casi limite estremi."""
    
    def test_minimum_loop_length(self, pointer_factory):
        """Loop minimo (0.001s - clamped nel codice)."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 2.0001  # Quasi zero
        })
        
        # Dovrebbe funzionare senza crash
        pos = pointer.calculate(5.0)
        assert 0.0 <= pos < 10.0
    
    def test_loop_at_sample_boundaries(self, pointer_factory):
        """Loop copre l'intero sample."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 0.0,
            'loop_end': 10.0
        }, sample_dur=10.0)
        
        pointer.calculate(1.0)
        assert pointer.in_loop is True
        
        # Dovrebbe wrappare correttamente
        pos = pointer.calculate(15.0)
        assert 0.0 <= pos < 10.0
    
    def test_fractional_positions(self, pointer_factory):
        """Posizioni altamente frazionarie."""
        pointer = pointer_factory({
            'start': 0.123456789,
            'speed_ratio': 1.0
        })
        
        pos = pointer.calculate(0.0)
        assert pos == pytest.approx(0.123456789, abs=1e-9)
    
    def test_negative_start_wraps(self, pointer_factory):
        """start negativo wrappa correttamente."""
        pointer = pointer_factory({
            'start': -2.0,
            'speed_ratio': 1.0
        }, sample_dur=10.0)
        
        # -2.0 % 10.0 = 8.0
        pos = pointer.calculate(0.0)
        assert pos == pytest.approx(8.0)
    
    def test_speed_exactly_zero_with_loop(self, pointer_factory):
        """Speed zero all'interno di un loop."""
        pointer = pointer_factory({
            'start': 3.0,
            'speed_ratio': 0.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        # Entra nel loop
        pointer.calculate(0.0)
        
        # Rimane fermo
        pos1 = pointer.calculate(100.0)
        pos2 = pointer.calculate(200.0)
        
        assert pos1 == pos2


# =============================================================================
# GRUPPO 8: STATE MANAGEMENT
# =============================================================================

class TestStateManagement:
    """Test reset e properties."""
    
    def test_reset_clears_state(self, pointer_factory):
        """reset() pulisce completamente lo stato."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        # Entra nel loop
        pointer.calculate(3.0)
        assert pointer.in_loop is True
        
        # Reset
        pointer.reset()
        
        # Stato pulito
        assert pointer.in_loop is False
        assert pointer._loop_absolute_pos is None
        assert pointer._last_linear_pos is None
    
    def test_sample_dur_sec_property(self, pointer_factory):
        """Property sample_dur_sec."""
        pointer = pointer_factory({}, sample_dur=7.5)
        assert pointer.sample_dur_sec == 7.5
    
    def test_in_loop_property(self, pointer_factory):
        """Property in_loop."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        assert pointer.in_loop is False
        pointer.calculate(3.0)
        assert pointer.in_loop is True
    
    def test_loop_phase_property(self, pointer_factory):
        """Property loop_phase calcola fase corretta."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0  # length = 3.0
        })
        
        # Prima del loop
        assert pointer.loop_phase == 0.0
        
        # Entra a 2.5 (0.5 nel loop)
        pointer.calculate(2.5)
        # phase = 0.5 / 3.0 = 0.166...
        assert 0.0 <= pointer.loop_phase <= 1.0
    
    def test_repr(self, pointer_factory):
        """__repr__ fornisce info utili."""
        pointer = pointer_factory({
            'start': 1.0,
            'speed_ratio': 2.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        })
        
        repr_str = repr(pointer)
        assert 'PointerController' in repr_str
        assert 'loop=' in repr_str


# =============================================================================
# GRUPPO 9: INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Test integrazione completa di scenari reali."""
    
    def test_realistic_forward_loop(self, pointer_factory):
        """Scenario realistico: loop forward con jitter."""
        pointer = pointer_factory({
            'start': 0.0,
            'speed_ratio': 1.5,
            'loop_start': 1.0,
            'loop_end': 4.0
        })
        
        # Simula generazione continua di grani
        positions = []
        for t in [i * 0.1 for i in range(50)]:
            pos = pointer.calculate(t)
            positions.append(pos)
        
        # Verifica: tutte le posizioni valide
        for pos in positions:
            assert 0.0 <= pos < 10.0
        
        # Verifica: dopo entrata nel loop, resta nel loop
        after_entry = [p for p in positions[15:] if p is not None]
        for pos in after_entry:
            assert 1.0 <= pos < 4.0
    
    def test_realistic_backward_loop(self, pointer_factory):
        """Scenario realistico: loop backward."""
        pointer = pointer_factory({
            'start': 5.0,
            'speed_ratio': -1.0,
            'loop_start': 1.0,
            'loop_end': 4.0
        })
        
        positions = []
        for t in [i * 0.1 for i in range(50)]:
            pos = pointer.calculate(t)
            positions.append(pos)
        
        # Verifica validità
        for pos in positions:
            assert 0.0 <= pos < 10.0
    
    def test_ping_pong_oscillation(self, pointer_factory):
        """Simulazione ping-pong: avanti/indietro ripetuto."""
        params = {
            'start': 3.0,
            'speed_ratio': 1.0,
            'loop_start': 2.0,
            'loop_end': 5.0
        }
        
        with patch('pointer_controller.ParameterOrchestrator') as MockOrch:
            mock_orch = MockOrch.return_value
            
            mock_params = {}
            
            mock_params['pointer_start'] = 3.0
            
            param = Mock()
            param.value = 1.0
            param.get_value = Mock(return_value=1.0)
            mock_params['pointer_speed_ratio'] = param
            
            param = Mock()
            param.value = 0.0
            param.get_value = Mock(return_value=0.0)
            mock_params['pointer_deviation'] = param
            
            param = Mock()
            param.value = 2.0
            param.get_value = Mock(return_value=2.0)
            mock_params['loop_start'] = param
            
            param = Mock()
            param.value = 5.0
            param.get_value = Mock(return_value=5.0)
            mock_params['loop_end'] = param

            
            # loop_dur opzionale (None per questi test)
            
            mock_params['loop_dur'] = None

            
            mock_orch.create_all_parameters.return_value = mock_params
            
            config = Mock(spec=StreamConfig)
            config.context = Mock(spec=StreamContext)
            config.context.stream_id = "test"
            config.context.sample_dur_sec = 10.0
            config.time_mode = 'absolute'
            
            pointer = PointerController(params, config)
            
            # Simula ping-pong
            linear_positions = [
                3.0, 3.5, 4.0, 4.5,  # Avanti
                4.0, 3.5, 3.0, 2.5,  # Indietro
                3.0, 3.5, 4.0,       # Avanti di nuovo
                3.5, 3.0, 2.5        # Indietro di nuovo
            ]
            
            positions = []
            for i, linear_pos in enumerate(linear_positions):
                pointer._calculate_linear_position = Mock(return_value=linear_pos)
                pos = pointer.calculate(float(i) * 0.1)
                positions.append(pos)
            
            # Tutte le posizioni devono essere valide
            for pos in positions:
                assert 2.0 <= pos < 5.0


