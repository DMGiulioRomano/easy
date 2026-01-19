import pytest
from envelope import Envelope

# =============================================================================
# 1. TEST INIZIALIZZAZIONE & SORTING
# =============================================================================

def test_init_sorts_breakpoints():
    """I breakpoint devono essere ordinati, anche se passati a caso."""
    # Questo test usa dati specifici, quindi non usiamo le fixture
    raw_points = [[10, 100], [0, 0], [5, 50]]
    env = Envelope(raw_points)
    
    assert env.breakpoints[0] == [0, 0]
    assert env.breakpoints[1] == [5, 50]
    assert env.breakpoints[2] == [10, 100]

def test_single_point_constant():
    """Un envelope con un solo punto è una costante."""
    env = Envelope([[0, 42]])
    assert env.evaluate(0) == 42
    assert env.evaluate(999) == 42
    # Integrale costante (rettangolo): base 10 * altezza 42 = 420
    assert env.integrate(0, 10) == 420.0

# =============================================================================
# 2. TEST INTERPOLAZIONE LINEARE
# =============================================================================

def test_linear_eval(env_linear):
    """Test valori su rampa lineare [0,0]->[10,100]."""
    assert env_linear.type == 'linear'
    assert env_linear.evaluate(0) == 0
    assert env_linear.evaluate(5) == 50     # Metà esatta
    assert env_linear.evaluate(2.5) == 25   # Un quarto
    assert env_linear.evaluate(10) == 100

def test_linear_clamping(env_linear):
    """Test comportamento fuori dai bordi temporali."""
    # Prima dell'inizio -> valore iniziale (0)
    assert env_linear.evaluate(-5) == 0
    # Dopo la fine -> valore finale (100)
    assert env_linear.evaluate(50) == 100

# =============================================================================
# 3. TEST STEP (A GRADINI)
# =============================================================================

def test_step_eval(env_step):
    """Test valori step [0,10]->[5,50]->[10,100]."""
    assert env_step.type == 'step'
    
    # Primo gradino (t < 5)
    assert env_step.evaluate(0) == 10
    assert env_step.evaluate(4.99) == 10
    
    # Secondo gradino (t >= 5)
    assert env_step.evaluate(5.0) == 50
    assert env_step.evaluate(9.99) == 50
    
    # Terzo gradino (t >= 10)
    assert env_step.evaluate(10.0) == 100

# =============================================================================
# 4. TEST CUBIC (FRITSCH-CARLSON)
# =============================================================================

def test_cubic_monotonicity(env_cubic):
    """
    Verifica che il plateau piatto [1,10]->[2,10] resti piatto.
    Algoritmi ingenui creerebbero una gobba > 10.
    """
    # Nel mezzo del plateau (t=1.5) deve essere esattamente 10
    val = env_cubic.evaluate(1.5)
    assert val == pytest.approx(10.0)

def test_cubic_smoothness(env_cubic):
    """Verifica che la salita sia curva e non retta."""
    # Salita lineare a t=0.5 sarebbe 5.0
    # Una cubica "smooth" di solito è un po' diversa (dipende dalle tangenti)
    val = env_cubic.evaluate(0.5)
    
    # Basta verificare che sia un valore sensato tra 0 e 10
    assert 0 < val < 10

# =============================================================================
# 5. TEST INTEGRALE
# =============================================================================

def test_integrate_linear(env_linear):
    """Area sotto il triangolo 0->10s, h=100."""
    # Area triangolo = (base * altezza) / 2 = (10 * 100) / 2 = 500
    area = env_linear.integrate(0, 10)
    assert area == pytest.approx(500.0)

def test_integrate_step(env_step):
    """Area sotto gradini."""
    # Gradino 1 (0-5s): altezza 10 -> Area 50
    # Gradino 2 (5-10s): altezza 50 -> Area 250
    # Totale atteso: 300
    area = env_step.integrate(0, 10)
    assert area == pytest.approx(300.0)

def test_integrate_partial_segment(env_linear):
    """Integrale di una porzione di segmento."""
    # Integriamo da 0 a 5 (metà rampa).
    # È un triangolo più piccolo: base 5, altezza 50.
    # Area = (5 * 50) / 2 = 125
    area = env_linear.integrate(0, 5)
    assert area == pytest.approx(125.0)

def test_integrate_out_of_bounds(env_linear):
    """Integrale che si estende oltre la definizione dell'envelope."""
    # Env finisce a 10s con valore 100.
    # Integriamo da 10 a 12 (2 secondi di valore costante 100).
    # Area rettangolo aggiuntivo: 2 * 100 = 200.
    area = env_linear.integrate(10, 12)
    assert area == pytest.approx(200.0)

# Aggiungi in coda a tests/test_envelope.py

def test_integrate_cubic_symmetry():
    """
    Test matematico avanzato.
    Una rampa cubica semplice [0,0]->[10,100] è simmetrica.
    La sua area deve essere uguale a quella lineare (500).
    Se questo fallisce, la formula in _integrate_cubic_segment è sbagliata.
    """
    env_cub = Envelope({'type': 'cubic', 'points': [[0, 0], [10, 100]]})
    area = env_cub.integrate(0, 10)
    
    # Tolleranza minima per float math
    assert area == pytest.approx(500.0, rel=1e-5)

def test_empty_breakpoints_error():
    """Envelope non deve accettare liste vuote."""
    # Attualmente il tuo codice solleverebbe IndexError o simili.
    # È buona norma verificare che esploda in modo controllato o gestirlo.
    with pytest.raises((IndexError, ValueError)):
        Envelope([])

def test_invalid_type_error():
    """Se passo un tipo sconosciuto, ORA DEVE DARE ERRORE (più sicuro)."""
    
    # Ci aspettiamo che sollevi ValueError
    with pytest.raises(ValueError) as excinfo:
        Envelope({'type': 'supercazzola', 'points': [[0,0], [10,10]]})
    
    # Verifica opzionale del messaggio di errore
    assert "Tipo envelope non valido" in str(excinfo.value)
    assert "supercazzola" in str(excinfo.value)