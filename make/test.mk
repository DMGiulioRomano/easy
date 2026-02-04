# Makefile.test
# Gestisce esclusivamente Virtual Environment e Unit Testing
# CONFIGURATO PER PYTHON 3.12

# --- CONFIGURAZIONE VENV ---
VENV_DIR := .venv
PYTHON_VERSION := 3.12


# Trova il comando Python corretto per la versione specificata
ifeq ($(shell which python$(PYTHON_VERSION) 2>/dev/null),)
    ifeq ($(shell which python3.12 2>/dev/null),)
        # Se python3.12 non esiste, prova a usare python3 e controlla la versione
        PYTHON_CHECK := $(shell python3 -c "import sys; print('OK' if sys.version_info[:2] >= (3, 12) else 'FAIL')")
        ifeq ($(PYTHON_CHECK),OK)
            PYTHON_CMD := python3
        else
            $(error Python $(PYTHON_VERSION) non trovato. Installalo con: brew install python@3.12 o apt install python3.12)
        endif
    else
        PYTHON_CMD := python3.12
    endif
else
    PYTHON_CMD := python$(PYTHON_VERSION)
endif

# Definiamo gli eseguibili relativi al venv
PYTHON_VENV := $(VENV_DIR)/bin/python
PIP_VENV := $(VENV_DIR)/bin/pip
PYTEST_VENV := $(VENV_DIR)/bin/pytest
REQUIREMENTS := requirements.txt
TEST_FILE ?= tests/

# File marker per evitare di reinstallare se non cambia nulla
VENV_MARKER := $(VENV_DIR)/.installed

# --- TARGETS ---

.PHONY: venv-setup venv-clean tests check-python


# Target per verificare la versione Python
check-python:
	@echo "🔍 [PYTHON] Verifica versione..."
	@$(PYTHON_CMD) -c "import sys; print(f'✅ Python {sys.version}'); sys.exit(0) if sys.version_info[:2] >= (3, 12) else (print('❌ Richiesta Python >= 3.12'), sys.exit(1))"


# Target principale per assicurarsi che l'ambiente sia pronto
venv-setup: $(VENV_MARKER)

# Regola: se manca il marker o cambia requirements.txt, rifà il setup
$(VENV_MARKER): $(REQUIREMENTS) check-python
	@echo "🔧 [VENV] Creazione/aggiornamento Virtual Environment con Python $(PYTHON_VERSION)..."
	@echo "📦 Python command: $(PYTHON_CMD)"
	@$(PYTHON_CMD) -m venv $(VENV_DIR)
	@$(PIP_VENV) install --upgrade pip
	@$(PIP_VENV) install -r $(REQUIREMENTS)
	@touch $(VENV_MARKER)
	@echo "✅ [VENV] Ambiente Python $(PYTHON_VERSION) pronto."

# Test con coverage report
tests-cov: venv-setup
	@echo "📊 [TEST] Running pytest con coverage..."
	$(PYTEST_VENV) $(TEST_FILE) --cov=src --cov-report=html --cov-report=term-missing


# Lancia i test usando pytest dentro il venv
tests: venv-setup
	@echo "🧪 [TEST] Running pytest..."
	$(PYTEST_VENV) $(TEST_FILE)

# Pulisce l'ambiente virtuale
venv-clean:
	@echo "🧹 [CLEAN] Rimozione Virtual Environment..."
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +

# Mostra info sull'ambiente
venv-info: venv-setup
	@echo "📋 [INFO] Informazioni ambiente:"
	@echo "Python: $$($(PYTHON_VENV) --version)"
	@echo "Pip: $$($(PIP_VENV) --version)"
	@echo "Pytest: $$($(PYTEST_VENV) --version)"
	@echo "Virtualenv: $(VENV_DIR)"

# Reinstalla completamente le dipendenze
venv-reinstall: venv-clean venv-setup
	@echo "🔄 [VENV] Reinstallazione completata."

# Aggiorna pip e tutte le dipendenze
venv-upgrade: venv-setup
	@echo "⬆️  [UPGRADE] Aggiornamento pip e pacchetti..."
	@$(PIP_VENV) install --upgrade pip
	@$(PIP_VENV) list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 $(PIP_VENV) install -U
	@echo "✅ Aggiornamento completato."

