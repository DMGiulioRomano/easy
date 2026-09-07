---
slug: errors
type: reference
status: stable
tags: [errors, exceptions, user-facing]
sources:
  - src/pge/shared/exceptions.py
  - src/pge/cli.py
  - src/pge/engine/generator.py
  - src/pge/rendering/csound_renderer.py
last_synced_commit: 386e6d2
entry_for: [error-handling]
---

# Error Handling — gerarchia `EngineError`

Documentazione del sistema di errori user-facing (issue #33 / #38). Obiettivo: separare il messaggio destinato all'utente finale (terminale pulito, italiano, contesto strutturato) dal traceback Python persistito nel log engine.

**Documenti collegati:** [[INDEX]] · [[architecture]] (`CsoundRenderError` /
`InvalidRendererError`) · [[yaml]] (campi YAML validati) · [[add-error-class]] ·
[[multi-voice]] (`StrategyNotFoundError`).

---

## Scope

Catalogo completo della gerarchia `EngineError`, regole `user_message()`, pattern di context enrichment. Per estendere con una nuova classe vedi [[add-error-class]].

## Sintassi

Forma del messaggio user-facing:

```
[ERRORE] <head>
  <dettaglio chiave: valore>
  <dettaglio chiave: valore>
  Stream:    <stream_id>     (se enrichito)
  Config:    <yaml_path>     (se enrichito)
```

Tutte le classi ereditano da `EngineError`. Sotto-gerarchie principali: `ConfigError` (YAML invalido) e `EngineRuntimeError` (errori a render-time).

## Bounds

Le classi specifiche e il loro contesto sono elencati in [Gerarchia](#1-gerarchia) e [Lista classi](#2-classi).

## Esempi

Vedi [Esempi](#3-esempi) per output reale di terminale.

## Versionato da

- `src/pge/shared/exceptions.py` — definizioni
- Siti di sollevamento sparsi nei moduli (parser, controller, renderer)
- Ultimo allineamento: vedi `last_synced_commit` in frontmatter

---

## 1. Gerarchia

Tutte le classi sono in [`src/pge/shared/exceptions.py`](../src/pge/shared/exceptions.py).

```
EngineError                                  (Exception)
├── SampleNotFoundError                      issue #33
│
├── ConfigError                              (anche ValueError, backward-compat)
│   ├── ConfigFileNotFoundError              #257 — lo YAML non esiste (anche FileNotFoundError)
│   ├── ConfigParseError                     #257 — lo YAML non si parsa (anche yaml.YAMLError)
│   ├── MissingFieldError                    PR1 — campo YAML mancante/null
│   ├── InvalidFieldValueError               PR1 — campo presente, valore invalido
│   ├── InvalidParameterError                PR2 — formato/tipo parametro non supportato
│   ├── ParameterBoundError                  PR2 — parametro fuori bounds (scalare/envelope)
│   ├── StrategyNotFoundError                PR3 — strategia non registrata
│   ├── InvalidStrategyConfigError           PR3 — config strategia invalida
│   ├── InvalidRendererError                 PR4 — renderer kind sconosciuto
│   ├── InvalidWindowError                   PR4 — window name/param invalido
│   └── FtableError                          PR4 — incoerenza FtableManager
│
└── EngineRuntimeError                       PR4 — errori runtime (non config)
    ├── _SubprocessRenderError               base dei render delegati a un binario
    │   ├── CsoundRenderError                (anche RuntimeError, backward-compat)
    │   └── SuperColliderRenderError         #228 — scsynth/sclang exit != 0
    └── _BinaryNotFoundError                 base dei binari esterni assenti
        ├── CsoundNotFoundError              #241 — csound non nel PATH
        └── SuperColliderNotFoundError       #228 — binario o sorgente assente
```

**Regole di design:**

- `ConfigError` eredita anche da `ValueError` → catch espliciti pre-esistenti
  continuano a funzionare.
- `CsoundRenderError` eredita anche da `RuntimeError` → idem.
  `SuperColliderRenderError` fa lo stesso, per simmetria: entrambe lo
  ereditano dalla base comune `_SubprocessRenderError`, che tiene
  `returncode`, `command`, `stderr`, `stdout` e il formato del messaggio in
  un posto solo. La riga `Output:` pesca dalla diagnostica del subprocess —
  la prima riga per csound, l'ultima per sclang/scsynth, che aprono sempre
  con il proprio preambolo — e considera **anche lo stdout**, che è dove
  entrambi i binari SuperCollider scrivono i loro errori.
- **Dentro `EngineError`, `FileNotFoundError` significa una cosa sola: il file
  di configurazione che hai nominato non esiste.** È una regola scritta in due
  tempi e da due lati opposti, e va letta insieme o non si capisce nessuna
  delle due metà.
  - `_BinaryNotFoundError` **NON** eredita da `FileNotFoundError`, e nemmeno
    le sue due sottoclassi (#228, #241). Lì il builtin era una bugia utile a
    nessuno: il file che mancava — `csound`, `scsynth`, un sorgente `.scd` —
    non era quello che il tipo lasciava intendere a chi lo catturava.
    `_run_csound` lasciava salire il `FileNotFoundError` del subprocess, e su
    una macchina senza csound l'utente si sentiva dire che il suo YAML non
    esisteva, letto e parsato pochi istanti prima.
  - `ConfigFileNotFoundError` **eredita** da `FileNotFoundError` (#257), per
    la ragione simmetrica: qui il file che manca è proprio quello, e
    `Generator.load_yaml` / `api.load_generator` dichiarano quel tipo fra i
    `Raises` da sempre — chi lo cattura continua a catturarlo, come per il
    `ValueError` di `ConfigError`. `ConfigParseError` fa lo stesso con
    `yaml.YAMLError`.

  Dove si eredita, si eredita per intero: `ConfigFileNotFoundError` valorizza
  `errno`, `strerror` e `filename` come li avrebbe riempiti `open()`, perché
  chi cattura quel tipo raramente si ferma alla cattura — e una promessa che
  regge per `isinstance` e cade per `e.filename` sarebbe muta, cioè la forma
  di guasto che questa issue chiude. Il prezzo si paga due volte, e va pagato
  tutto. `OSError.__str__`, visto `filename`, smetterebbe di stampare
  `args[0]`: `__str__` è sovrascritto, e `str(err)` — quello che finisce nel
  log engine — resta la prosa della classe. E `OSError.__reduce__` accoda
  `filename` agli `args`, perché un OSError si ricostruisce da `(errno,
  strerror, filename)`: qui gli `args` sono la sola prosa, quindi un round
  trip (`pickle`, `copy`) tornava indietro con il messaggio annidato dentro
  sé stesso e `path`/`filename` uguali al messaggio — senza sollevare
  niente, cioè la stessa promessa muta un piano più in là. Anche `__reduce__`
  è sovrascritto: tutto lo stato della classe è il suo path.

  Il guadagno non è la compatibilità (che è il prezzo di ammissione): è che
  il tipo torna a *isolare*. Un `FileNotFoundError` che risale dall'engine
  ora colloca sé stesso, e la garanzia non dipende più da dove sta scritto
  chi lo cattura. Il test che la tiene in piedi è derivato dalla gerarchia,
  non da un elenco trascritto:
  `tests/shared/test_engine_exceptions.py::test_solo_la_configurazione_e_un_FileNotFoundError`.
- **`cli.main()` non intercetta nessun tipo builtin lungo la pipeline** (#257).
  La #241 aveva stretto l'handler `FileNotFoundError` attorno a `Generator()`
  + `load_yaml()`, e funzionava; ma la garanzia che rivendicava era
  l'*estensione fisica del blocco*, non il tipo dell'eccezione. Una riga in
  più lì dentro — un `!include`, una prescansione dei sample, il passaggio ad
  `api.load_generator`, che impacchetta anche `create_elements` — rimetteva in
  circolo il messaggio falso, e niente sarebbe diventato rosso. Ora restano
  `except EngineError` e il ramo generico: quello che nessuno ha ancora
  tradotto esce con messaggio e traceback, non con un messaggio falso. Gli
  `except ValueError` che sopravvivono in `main()` stanno attorno a
  `int()`/`float()` su `sys.argv`, fuori dal `try` della pipeline. La guardia
  è `tests/test_cli_builtin_handlers.py`, che legge `cli.py` come AST.
- **La riga `Comando:` di `_SubprocessRenderError` invita a rieseguire, quindi
  deve restare rieseguibile.** Lo score che vi compare è temporaneo e il
  renderer lo cancella in un `finally` — anche quando il binario esce con un
  codice d'errore, che è il caso in cui quello score serve. Perciò la base ha
  un `hint` opzionale e il ramo csound lo valorizza con `--keep-sco` quando lo
  score era temporaneo: senza, la prima azione che il messaggio suggerisce è
  un no-op. Il flag però non ricrea *quel* file, quindi l'hint dice che la
  riga mostrata non si riesegue e rimanda a quella del messaggio successivo —
  altrimenti il rimedio-che-non-fa-nulla si sposta di un livello invece di
  sparire. Stessa forma dell'hint di `_BinaryNotFoundError`, e stessa regola —
  un rimedio si scrive solo quando c'è.
- `EngineRuntimeError` separa runtime engine da config; sotto-classi future
  (es. errori I/O di rendering) si appendono qui.
- Ogni sotto-classe override `user_message()` con formato strutturato.

---

## 2. Contratto `user_message()`

Ogni eccezione `EngineError` espone:

```python
def user_message(self) -> str
```

Formato:

```
[ERRORE] <head: cosa e' fallito>
  <Campo>:      <valore>
  ...
  Stream:       <stream_id>          # se arricchito
  Config:       <config_file>        # se arricchito
```

Esempio (`InvalidWindowError`):

```
[ERRORE] Window non trovata: 'totally_bogus'
  Disponibili:  bartlett, blackman, hamming, hanning, kaiser
  Stream:       drone_low
  Config:       configs/PGE_test.yml
```

Il chiamante (`main._handle_engine_error`) appende anche:

```
  Dettagli:     <path engine.log>
```

dove finisce il traceback Python completo per debug.

---

## 3. Pattern context enrichment layered

Le eccezioni vengono sollevate con contesto **minimo locale**, poi arricchite
mentre risalgono lo stack:

| Layer                                       | Arricchisce             |
|---------------------------------------------|-------------------------|
| Raise site (parser/strategy/registry)       | dato locale (param, value, available, ...) |
| Parser/Stream/Controller chiamante          | `err.stream_id`         |
| `Generator.create_elements`                 | `err.config_file`       |
| `main._handle_engine_error`                 | path engine log         |

**Esempio: `WindowController.parse_window_list`**

```python
try:
    win = NumpyWindowRegistry().get(name, n)        # raise InvalidWindowError
except InvalidWindowError as err:
    err.stream_id = stream_id                       # arricchisco e rilancio
    raise
```

**Esempio: `Generator.create_elements`**

```python
try:
    self._build_streams_from_yaml(yaml_data)
except ConfigError as err:
    if err.config_file is None:
        err.config_file = self.config_path
    raise
```

**Handler unico in `main.py:308`:**

```python
except EngineError as e:
    _handle_engine_error(e)
    sys.exit(1)
```

Polimorfismo: cattura tutta la gerarchia (config, runtime, sample). Nessun
ramo dedicato per sotto-classe.

---

## 4. Esempi YAML invalidi → output

### File di configurazione assente
CLI: `python src/main.py configs/inesistente.yml`
```
[ERRORE] File di configurazione non trovato
  Path cercato: /home/utente/PythonGranularEngine/configs/inesistente.yml
  Config:       configs/inesistente.yml
  Dettagli:     /tmp/engine.log
```

La riga `Path cercato:` compare solo quando aggiunge qualcosa, cioè quando il
path passato era relativo: dice in quale directory si è cercato, che è
l'informazione che manca proprio a chi ha sbagliato il path relativo. Con un
path già assoluto sarebbe `Config:` scritta due volte (stessa regola dei
bounds ignoti di `ParameterBoundError`).

### File di configurazione malformato
```
[ERRORE] YAML non valido
  Motivo:       mapping values are not allowed here
  Posizione:    riga 3, colonna 11
  Config:       configs/rotto.yml
  Dettagli:     /tmp/engine.log
```

Motivo e posizione vengono da `problem` e `problem_mark` di PyYAML (che conta
da 0, gli editor da 1): la posizione non si stima, si legge. Lo `YAMLError`
originale resta in catena via `raise ... from`, quindi lo sproloquio completo
del parser finisce nel log insieme al nostro traceback — è ciò che rende
accettabile un `user_message()` di tre righe al suo posto. Fino alla #257
nessuno lo traduceva e l'utente riceveva messaggio più traceback dal ramo
generico.

### Renderer sconosciuto
CLI: `--renderer foo`
```
[ERRORE] Renderer non supportato: 'foo'
  Disponibili:  csound, numpy, supercollider
  Dettagli:     /tmp/engine.log
```

L'elenco non è scritto a mano nel messaggio: viene da
`RendererFactory.available_types()`, così un backend nuovo compare qui senza
che nessuno aggiorni la stringa.

### Window name sconosciuto
```yaml
streams:
  s1:
    envelope: totally_bogus
```
```
[ERRORE] Window non trovata: 'totally_bogus'
  Disponibili:  bartlett, blackman, hamming, hanning, kaiser
  Stream:       s1
  Config:       configs/PGE_test.yml
```

### Parametro fuori bounds
```yaml
streams:
  s1:
    pitch: 999.0     # bounds [0.1, 100.0]
```
```
[ERRORE] Parametro 'pitch' fuori bounds
  value:        999.0
  Bounds:       [0.1, 100.0]
  Stream:       s1
  Config:       configs/PGE_test.yml
```

`ParameterBoundError` accetta anche un `hint` opzionale, per i casi in cui il
vincolo violato **non è un intervallo sul singolo valore**. È il caso
dell'overflow delle potenze nelle distribuzioni temporali del formato compatto
(`ratio ** n_reps`): nessuno dei due valori è fuori posto da solo, quindi non
c'è nessun `[min, max]` da stampare — e infatti la riga `Bounds` viene omessa
quando entrambi i bound sono ignoti, invece di scrivere `[None, None]`.

```yaml
streams:
  s1:
    density: [[[0, 5], [100, 50]], 10.0, 400, 'linear', {type: geometric, ratio: 10}]
```
```
[ERRORE] Parametro 'ratio' fuori bounds
  value:        10
  Hint:         la distribuzione 'geometric(ratio=10)' calcola ratio ** n_reps con n_reps=400, e il risultato non sta in un float. Ne' ratio=10 ne' n_reps=400 e' fuori posto da solo: e' la coppia a esplodere. Riduci n_reps, oppure avvicina ratio a 1.
  Stream:       s1
  Config:       configs/PGE_test.yml
```

### Strategia non trovata
```yaml
streams:
  s1:
    voices:
      pitch: { strategy: foo }
```
```
[ERRORE] Strategia pitch non trovata: 'foo'
  Disponibili:  fixed, harmonic, pyramid, scale
  Stream:       s1
  Config:       configs/PGE_test.yml
```

### Csound subprocess fallito
```
[ERRORE] Csound rendering fallito (exit code 2)
  Comando:      csound -o out.aif /tmp/tmpx3k9.sco
  Output:       error: undefined opcode
  Hint:         Lo score .sco era temporaneo ed e' stato rimosso, quindi il comando qui sopra non e' piu' rieseguibile: rilancia con `--keep-sco`, che lo score lo conserva su disco, e riesegui il `Comando:` del messaggio che ne esce.
  Stream:       drone_low
  Config:       configs/PGE_test.yml
  Dettagli:     /tmp/engine.log
```

La riga `Hint:` compare solo senza `--keep-sco`: con il flag lo score è già
sul disco e suggerirlo manderebbe l'utente a cercare un'opzione che ha già
passato. E manda a rieseguire il `Comando:` del messaggio *successivo*, non
quello mostrato qui: `--keep-sco` non riporta lo score al path temporaneo che
questa riga nomina — lo scrive in una directory stabile, e senza il flag
`mkstemp` pesca ogni volta un nome nuovo.

### SuperCollider subprocess fallito
Il campo `stage` distingue i due binari, perché hanno rimedi diversi:
`scsynth` è il rendering, `sclang` è la compilazione della SynthDef.
```
[ERRORE] scsynth fallito (exit code 1)
  Comando:      scsynth -o 2 -i 0 -z 1 -n 32768 -m 32768 -N /tmp/x.osc _ out.aif 48000 AIFF float
  Output:       ERROR: Buffer UGen: no buffer data
  Dettagli:     /tmp/engine.log
```

### SuperCollider non installato
```
[ERRORE] SuperCollider: binario 'scsynth' non trovato
  Hint:         Installa SuperCollider (Debian/Ubuntu: apt install supercollider; macOS: brew install --cask supercollider) oppure usa --renderer numpy.
  Dettagli:     /tmp/engine.log
```

### Csound non installato
```
[ERRORE] Csound: binario 'csound' non trovato
  Hint:         Installa csound (`make install-system-deps`; su Fedora/RHEL non e' nei repo e va compilato dai sorgenti, vedi README), oppure usa `--renderer numpy`, che non richiede binari esterni.
  Dettagli:     /tmp/engine.log
```

Fino alla issue #241 lo stesso guasto usciva come `Errore: file
'configs/x.yml' non trovato`, con exit 1 e nessuna menzione di csound.

---

## 5. Estensione — aggiungere nuova sotto-classe

1. Definire in `src/pge/shared/exceptions.py` ereditando dal nodo giusto:
   - errore di config YAML → `ConfigError`
   - errore runtime engine non-config → `EngineRuntimeError`
2. Override `user_message()` con formato `[ERRORE] head` + righe indentate +
   `self._context_lines()` finale (`stream_id` + `config_file`).
3. Se serve backward-compat con un tipo esterno (`KeyError`, `RuntimeError`,
   `FileNotFoundError`, `yaml.YAMLError`, ...) aggiungerlo come seconda base —
   vedere `CsoundRenderError`. La domanda da farsi non è «che cosa è successo»
   ma «a chi serve questo tipo»: se qualcuno lo catturava già e continuerebbe
   ad avere ragione a catturarlo, si eredita (`ConfigFileNotFoundError`, #257);
   se il tipo descriveva la causa ma sviava chi lo catturava, non si eredita
   (`_BinaryNotFoundError`, #228/#241). Le due decisioni sono opposte e
   coerenti: insieme fanno sì che il tipo isoli.
4. Sostituire i raise esistenti nel modulo target.
5. Arricchire `stream_id` al chiamante più prossimo (parser/controller).
6. Test:
   - unit in `tests/shared/test_engine_exceptions.py`: `isinstance` checks +
     `user_message()` substring.
   - integration nel modulo: raise propagato con campi corretti.
   - handler in `tests/test_main_engine_error.py`: cattura via `EngineError`.
   - e2e in `tests/e2e/test_engine_errors_e2e.py`: subprocess su YAML inline,
     exit code 1, head `[ERRORE]` su stdout.

---

## 6. Test patterns

| Layer       | File                                           | Cosa verifica                                  |
|-------------|------------------------------------------------|------------------------------------------------|
| unit        | `tests/shared/test_engine_exceptions.py`       | `isinstance(err, EngineError/ConfigError/...)`, `user_message()` substring |
| integration | `tests/<modulo>/test_<area>_errors.py`         | raise sollevato dal modulo, attributi popolati |
| handler     | `tests/test_main_engine_error.py`              | `_handle_engine_error` stampa `user_message`, log path appeso |
| e2e         | `tests/e2e/test_engine_errors_e2e.py`          | subprocess `python main.py <yaml>`, exit code 1, stdout contiene `[ERRORE]` |

E2E usa `tmp_path` con YAML inline + sample reale di repo. Mai scrivere YAML
di test in `configs/`.

---

## 7. Riferimenti

- Issue #33 — `SampleNotFoundError` + handler base
- Issue #38 — Estensione gerarchia ConfigError/EngineRuntimeError:
  - PR1 (Missing/InvalidFieldValue) — #40
  - PR2 (Parameter errors) — #41
  - PR3 (Strategy errors) — #42
  - PR4 (Rendering errors) — #43
  - PR5 (Documentation) — questo file
- Issue #228 / #241 — binario esterno assente: un tipo di dominio, **senza**
  `FileNotFoundError`
- Issue #257 — file di configurazione assente o malformato: un tipo di
  dominio, **con** il tipo esterno che sostituisce; e `cli.main()` che smette
  di intercettare builtin
