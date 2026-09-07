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
