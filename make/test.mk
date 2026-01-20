# Makefile.test
# Gestisce esclusivamente Virtual Environment e Unit Testing

# --- CONFIGURAZIONE VENV ---
VENV_DIR := .venv
# Definiamo gli eseguibili relativi al venv
PYTHON_VENV := $(VENV_DIR)/bin/python3
PIP_VENV := $(VENV_DIR)/bin/pip
PYTEST_VENV := $(VENV_DIR)/bin/pytest
REQUIREMENTS := requirements.txt

# File marker per evitare di reinstallare se non cambia nulla
VENV_MARKER := $(VENV_DIR)/.installed

# --- TARGETS ---

.PHONY: venv-setup venv-clean tests

# Target principale per assicurarsi che l'ambiente sia pronto
venv-setup: $(VENV_MARKER)

# Regola: se manca il marker o cambia requirements.txt, rifà il setup
$(VENV_MARKER): $(REQUIREMENTS)
	@echo "🔧 [VENV] Creating/Updating Virtual Environment..."
	python3 -m venv $(VENV_DIR)
	$(PIP_VENV) install --upgrade pip
	$(PIP_VENV) install -r $(REQUIREMENTS)
	touch $(VENV_MARKER)
	@echo "✅ [VENV] Environment ready."

# Lancia i test usando pytest dentro il venv
tests: venv-setup
	@echo "🧪 [TEST] Running pytest..."
	$(PYTEST_VENV) tests/

# Pulisce l'ambiente virtuale
venv-clean:
	@echo "🧹 [CLEAN] Removing Virtual Environment..."
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +