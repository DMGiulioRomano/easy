# =============================================================================
# tests/test_cli_builtin_handlers.py
# =============================================================================
"""
Guardia strutturale sugli `except` di `pge.cli` (issue #257).

La #241 aveva spostato l'handler `FileNotFoundError` dal fondo del `try` di
`main()` alle due righe che caricano lo YAML. La correzione funzionava, ma la
garanzia che rivendicava — «qui puo' fallire solo il file di configurazione» —
era vera per *estensione fisica del blocco*, non per il tipo dell'eccezione:
una riga in piu' dentro quel `try` (un `!include`, una prescansione dei
sample, il passaggio ad `api.load_generator`, che impacchetta anche
`create_elements`) rimetteva in circolo il messaggio falso senza che niente
diventasse rosso.

La #257 ha tolto la premessa invece di puntellarla: i guasti del caricamento
hanno un tipo di dominio (`ConfigFileNotFoundError`, `ConfigParseError`) e la
CLI non intercetta piu' nessun builtin lungo la pipeline. Questo file e' la
forma eseguibile di quella regola, letta dal sorgente come AST invece che
riasserita a parole.

Due guardie, di raggio diverso:

1. **Nessun handler di `cli.py` cattura un errore della famiglia `OSError`.**
   E' la famiglia che risale da qualunque profondita' di I/O — csound assente
   (#241), un sample illeggibile, un disco pieno — e per questo l'unica che il
   tipo, da solo, non basta a collocare. Una `except FileNotFoundError` che
   tornasse in questo file avrebbe di nuovo bisogno di stare *nel punto
   giusto* per non mentire.
2. **Il `try` che avvolge la pipeline non contiene nessun handler su un
   builtin**, a nessuna profondita', e i suoi due rami sono `EngineError` e
   il generico. Gli `except ValueError` sopravvissuti in `main()` stanno
   attorno a `int()`/`float()` su `sys.argv` e non toccano la pipeline: la
   guardia li lascia stare di proposito, ed e' il motivo per cui e' scritta
   sul blocco e non sull'intera funzione.
"""

import ast
import builtins
import os

import pytest


CLI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'src', 'pge', 'cli.py')


@pytest.fixture(scope='module')
def albero():
    with open(CLI_PATH, encoding='utf-8') as f:
        return ast.parse(f.read(), filename=CLI_PATH)


def _nomi_catturati(handler: ast.ExceptHandler) -> list[str]:
    """I nomi (dotted o semplici) che un `except` intercetta."""
    if handler.type is None:
        return []
    tipi = (handler.type.elts
            if isinstance(handler.type, ast.Tuple) else [handler.type])
    nomi = []
    for t in tipi:
        if isinstance(t, ast.Name):
            nomi.append(t.id)
        elif isinstance(t, ast.Attribute):
            nomi.append(t.attr)
    return nomi


def _builtin_exception(nome: str):
    """La classe builtin omonima, se e' un'eccezione; altrimenti None.

    Derivata da `builtins`, non da un elenco trascritto: un elenco andrebbe
    aggiornato da chi aggiunge l'handler, cioe' proprio da chi non ci pensa.
    """
    cls = getattr(builtins, nome, None)
    if isinstance(cls, type) and issubclass(cls, BaseException):
        return cls
    return None


def _funzione(albero, nome):
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nome:
            return nodo
    raise AssertionError(f"funzione {nome!r} non trovata in {CLI_PATH}")


def _try_della_pipeline(main_node):
    """Il `try` che avvolge caricamento, generazione e render.

    Individuato dal suo contenuto (`generator.load_yaml()`), non dalla sua
    posizione nel file: e' la stessa differenza che questa issue ha corretto
    nel codice.
    """
    candidati = [
        nodo for nodo in ast.walk(main_node)
        if isinstance(nodo, ast.Try)
        and any(isinstance(c, ast.Call)
                and isinstance(c.func, ast.Attribute)
                and c.func.attr == 'load_yaml'
                for c in ast.walk(nodo))
    ]
    assert candidati, "nessun try contiene la chiamata a load_yaml()"
    # Il piu' esterno: quello i cui handler chiudono la pipeline.
    return max(candidati, key=lambda n: len(list(ast.walk(n))))


def test_cli_non_cattura_nessun_errore_della_famiglia_oserror(albero):
    colpevoli = []
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.ExceptHandler):
            continue
        for nome in _nomi_catturati(nodo):
            cls = _builtin_exception(nome)
            if cls is not None and issubclass(cls, OSError):
                colpevoli.append((nome, nodo.lineno))
    assert not colpevoli, (
        "pge/cli.py cattura di nuovo un errore della famiglia OSError: "
        f"{colpevoli}. Un guasto di I/O risale da qualunque profondita', "
        "quindi il tipo non basta a collocarlo e il messaggio torna a "
        "dipendere da dove sta l'handler (issue #241/#257). Dagli un tipo "
        "di dominio nel punto che lo produce, come "
        "ConfigFileNotFoundError."
    )


def test_la_pipeline_non_contiene_handler_su_builtin(albero):
    blocco = _try_della_pipeline(_funzione(albero, 'main'))
    colpevoli = []
    for corpo in blocco.body:
        for nodo in ast.walk(corpo):
            if not isinstance(nodo, ast.ExceptHandler):
                continue
            for nome in _nomi_catturati(nodo):
                if _builtin_exception(nome) is not None:
                    colpevoli.append((nome, nodo.lineno))
    assert not colpevoli, (
        "un handler su un tipo builtin e' tornato dentro il try della "
        f"pipeline: {colpevoli}. Il messaggio che ne esce vale finche' "
        "il blocco non cresce, e cresce senza che nessun test lo dica "
        "(issue #257)."
    )


def test_la_pipeline_ha_i_due_rami_dichiarati(albero):
    """`EngineError` prima, il generico dopo: l'ordine e' il contratto.

    Se un domani `ConfigFileNotFoundError` — che eredita `FileNotFoundError`
    — passasse da un ramo builtin messo davanti, il tipo di dominio
    smetterebbe di servire a chi lo cattura, che e' l'unica cosa a cui serve.
    """
    blocco = _try_della_pipeline(_funzione(albero, 'main'))
    catturati = [_nomi_catturati(h) for h in blocco.handlers]
    assert catturati == [['EngineError'], ['Exception']], catturati
