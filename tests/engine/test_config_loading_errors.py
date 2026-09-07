# =============================================================================
# tests/engine/test_config_loading_errors.py
# =============================================================================
"""
Il caricamento dello YAML solleva errori di dominio, non builtin (issue #257).

Fino alla #257 `Generator.load_yaml` lasciava salire il `FileNotFoundError`
della `open()` e lo `yaml.YAMLError` del parser. Il primo era annunciato
dalla CLI con un messaggio giusto per una ragione fragile — l'handler stava
attaccato a quelle due righe, e la garanzia era la loro estensione fisica,
non il tipo dell'eccezione. Il secondo non lo traduceva nessuno e finiva nel
ramo generico: messaggio piu' traceback.

Qui si verifica il capo dell'pge.engine: i due guasti hanno un tipo, il tipo
porta il messaggio, e la conversione e' stretta sul punto che puo' produrli
davvero — non sul blocco che li contiene.
"""
import errno
import os

import pytest
import yaml

from pge.engine.generator import Generator
from pge.shared.exceptions import ConfigFileNotFoundError, ConfigParseError


YAML_VALIDO = """\
composition:
  title: "test"
streams: []
"""

YAML_ROTTO = """\
composition:
  title: uno
   cattiva: due
"""


def test_load_yaml_file_assente_solleva_errore_di_dominio(tmp_path):
    mancante = tmp_path / "non_esiste.yml"
    gen = Generator(str(mancante))

    with pytest.raises(ConfigFileNotFoundError) as excinfo:
        gen.load_yaml()

    err = excinfo.value
    assert err.config_file == str(mancante)
    msg = err.user_message()
    assert "[ERRORE]" in msg
    assert str(mancante) in msg


def test_load_yaml_file_assente_resta_un_FileNotFoundError(tmp_path):
    """La promessa di libreria non si rompe: la docstring di `load_yaml`
    dichiara FileNotFoundError, e chi lo cattura continua a catturarlo."""
    gen = Generator(str(tmp_path / "non_esiste.yml"))
    with pytest.raises(FileNotFoundError):
        gen.load_yaml()


def test_load_yaml_malformato_solleva_config_parse_error(tmp_path):
    rotto = tmp_path / "rotto.yml"
    rotto.write_text(YAML_ROTTO)

    with pytest.raises(ConfigParseError) as excinfo:
        Generator(str(rotto)).load_yaml()

    err = excinfo.value
    assert err.config_file == str(rotto)
    msg = err.user_message()
    assert "[ERRORE]" in msg
    assert "YAML non valido" in msg
    # La posizione arriva dal mark di PyYAML, non da una stima.
    assert "Posizione:" in msg


def test_load_yaml_malformato_resta_uno_yaml_error(tmp_path):
    rotto = tmp_path / "rotto.yml"
    rotto.write_text(YAML_ROTTO)
    with pytest.raises(yaml.YAMLError):
        Generator(str(rotto)).load_yaml()


def test_load_yaml_malformato_incatena_l_errore_originale(tmp_path):
    """Il traceback del parser non si perde: finisce nel log engine via la
    catena `__cause__` che `traceback.format_exc()` stampa."""
    rotto = tmp_path / "rotto.yml"
    rotto.write_text(YAML_ROTTO)
    with pytest.raises(ConfigParseError) as excinfo:
        Generator(str(rotto)).load_yaml()
    assert isinstance(excinfo.value.__cause__, yaml.YAMLError)
    assert not isinstance(excinfo.value.__cause__, ConfigParseError)


def test_un_file_diverso_che_manca_non_diventa_la_configurazione(tmp_path,
                                                                 monkeypatch):
    """Il sabotaggio della premessa, al capo dell'pge.engine.

    La conversione e' stretta sulla `open()` del solo YAML. Un
    FileNotFoundError sollevato *dentro* il blocco di caricamento ma per un
    altro file — un `!include`, una prescansione dei sample, qualunque cosa
    il parsing arrivi a fare domani — non deve travestirsi da configurazione
    mancante: e' esattamente il difetto che la #241 ha chiuso per posizione e
    che la #257 chiude per tipo. Con un `try` largo su tutto il caricamento,
    questo test sarebbe rosso.
    """
    buono = tmp_path / "buono.yml"
    buono.write_text(YAML_VALIDO)

    def _safe_load_che_apre_altro(stream):
        raise FileNotFoundError(2, 'No such file or directory', 'altro.wav')

    monkeypatch.setattr(yaml, 'safe_load', _safe_load_che_apre_altro)

    gen = Generator(str(buono))
    with pytest.raises(FileNotFoundError) as excinfo:
        gen.load_yaml()

    assert not isinstance(excinfo.value, ConfigFileNotFoundError)
    assert 'buono.yml' not in str(excinfo.value)


def test_load_yaml_valido_non_cambia_comportamento(tmp_path):
    """La conversione non tocca il percorso felice."""
    buono = tmp_path / "buono.yml"
    buono.write_text(YAML_VALIDO)
    dati = Generator(str(buono)).load_yaml()
    assert dati['composition']['title'] == 'test'


def test_api_load_generator_eredita_lo_stesso_tipo(tmp_path):
    """L'API pubblica verso cui il repo converge (#243) porta lo stesso
    errore: il giorno in cui la CLI la chiamera' al posto di
    Generator+load_yaml, il messaggio non cambia."""
    from pge import api
    mancante = tmp_path / "non_esiste.yml"
    with pytest.raises(ConfigFileNotFoundError):
        api.load_generator(str(mancante))


def test_directory_al_posto_del_file_non_e_un_file_mancante(tmp_path):
    """Il perimetro dichiarato: la #257 traduce «non c'e'» e «non si parsa».

    Un path che esiste ma non e' un file di configurazione (una directory,
    un file senza permessi) resta un OSError grezzo e finisce nel ramo
    generico della CLI. Il test lo fissa perche' sia una scelta e non una
    scoperta: il giorno in cui qualcuno vorra' coprirlo, questa e' la riga
    che dice dove si era deciso di fermarsi.
    """
    gen = Generator(str(tmp_path))
    with pytest.raises(OSError) as excinfo:
        gen.load_yaml()
    assert not isinstance(excinfo.value, ConfigFileNotFoundError)
    assert not isinstance(excinfo.value, FileNotFoundError)
    # `errno.EISDIR`, non il 21 trascritto: il numero e' della
    # piattaforma, e in questo repo nessuna costante di casa d'altri si
    # copia a mano.
    assert excinfo.value.errno == errno.EISDIR
    assert os.path.isdir(str(tmp_path))


# =============================================================================
# Il file c'e', ma i suoi byte non sono quelli che il locale si aspetta
# =============================================================================

# Accentata di proposito: e' la forma normale dei titoli in questo repo
# (`configs/PGE_12min.yml` e altri nove hanno byte non-ASCII), quindi non e'
# un caso di laboratorio.
CONFIG_ACCENTATA = 'composition:\n  title: "città perduta"\nstreams: []\n'


def test_config_non_utf8_e_uno_yaml_che_non_si_parsa(tmp_path):
    """«Il file c'e' ma non si lascia leggere» e' la definizione di
    ConfigParseError, e un byte non decodificabile ci sta dentro.

    Chi decodifica decide anche chi solleva. Con `open(path, 'r')` la
    decodifica avviene nel layer di testo, prima che PyYAML veda alcunche':
    ne esce un `UnicodeDecodeError` grezzo, che non e' uno `yaml.YAMLError` e
    non e' un `OSError` -- cioe' non e' nel perimetro che la #257 dichiara ne'
    in quello che dichiara di lasciare fuori. Finiva nel ramo generico della
    CLI: messaggio piu' traceback, l'esito che il criterio della issue vieta.
    Leggendo i byte e lasciando la decodifica a PyYAML, lo stesso guasto
    diventa un `ReaderError` -- uno `yaml.YAMLError` -- e passa dalla porta
    che esiste gia'.
    """
    rotto = tmp_path / "non_utf8.yml"
    rotto.write_bytes(CONFIG_ACCENTATA.encode('latin-1'))

    with pytest.raises(ConfigParseError) as excinfo:
        Generator(str(rotto)).load_yaml()

    msg = excinfo.value.user_message()
    assert "[ERRORE]" in msg
    assert "YAML non valido" in msg
    assert str(rotto) in msg


def test_config_non_utf8_resta_uno_yaml_error(tmp_path):
    """Stessa promessa di libreria della sorella malformata: il tipo esterno
    che `load_yaml` dichiara nei `Raises` resta fra le basi."""
    rotto = tmp_path / "non_utf8.yml"
    rotto.write_bytes(CONFIG_ACCENTATA.encode('latin-1'))
    with pytest.raises(yaml.YAMLError):
        Generator(str(rotto)).load_yaml()


def test_config_non_utf8_incatena_l_errore_originale(tmp_path):
    """Il motivo vero non si perde: `raise ... from` lo tiene in catena e
    `traceback.format_exc()` lo scrive nel log engine."""
    rotto = tmp_path / "non_utf8.yml"
    rotto.write_bytes(CONFIG_ACCENTATA.encode('latin-1'))
    with pytest.raises(ConfigParseError) as excinfo:
        Generator(str(rotto)).load_yaml()
    assert isinstance(excinfo.value.__cause__, yaml.YAMLError)


def test_la_codifica_del_config_non_dipende_dal_locale(tmp_path):
    """L'altra meta', e la piu' spiacevole: un config UTF-8 valido non deve
    smettere di caricarsi perche' la macchina ha un locale ASCII.

    `open(path, 'r')` decodifica con `locale.getpreferredencoding()`. Sotto
    `LC_ALL=C` -- un container, un cron, una GitHub Action senza locale --
    quello e' ASCII, e i dieci config accentati che questo repo distribuisce
    (`configs/PGE_12min.yml` fra loro) morivano con un `UnicodeDecodeError`
    grezzo prima ancora che PyYAML fosse chiamato. YAML 1.1 prescrive UTF-8 o
    UTF-16: la codifica del file e' un fatto del file, non dell'ambiente, e
    lasciarla a PyYAML e' il modo di dirlo una volta sola.

    Il locale si degrada solo in un processo figlio, quindi la prova e' un
    subprocess -- e se il degrado non riesce (piattaforme che coercono
    comunque a UTF-8) il test si dichiara muto invece di passare per caso.
    """
    import os
    import subprocess
    import sys

    buono = tmp_path / "accentato.yml"
    buono.write_bytes(CONFIG_ACCENTATA.encode('utf-8'))

    radice = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    env = dict(
        os.environ,
        LC_ALL='C', LANG='C', LANGUAGE='C',
        PYTHONUTF8='0', PYTHONCOERCECLOCALE='0',
        PYTHONPATH=os.pathsep.join([radice, os.path.join(radice, 'src')]),
    )
    codice = (
        "import locale, sys\n"
        "from pge.engine.generator import Generator\n"
        "print(locale.getpreferredencoding(False))\n"
        "titolo = Generator(sys.argv[1]).load_yaml()['composition']['title']\n"
        # Solo ASCII sullo stdout del figlio: sotto LC_ALL=C stampare
        # l'accento sarebbe un UnicodeEncodeError, cioe' un rosso che parla
        # del print e non del caricamento.
        "print(titolo.encode('utf-8').hex())\n"
    )
    res = subprocess.run(
        [sys.executable, '-c', codice, str(buono)],
        env=env, capture_output=True, text=True, timeout=60,
    )

    righe = res.stdout.splitlines()
    assert righe, f"il figlio non ha stampato niente: {res.stderr}"
    codifica = righe[0].lower().replace('-', '').replace('_', '')
    if 'utf8' in codifica:
        pytest.skip(f"locale non degradabile qui ({righe[0]}): la prova non "
                    "distinguerebbe le due letture")

    assert res.returncode == 0, res.stderr
    assert righe[1] == 'città perduta'.encode('utf-8').hex()
