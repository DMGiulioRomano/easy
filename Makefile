# Makefile Principale
# --- Rilevazione OS ---
OS := $(shell uname -s)

ifeq ($(OS), Darwin)
    OPEN_CMD     := open
    PYTHON_CMD   := python3.12
    HAS_RX11     := $(shell [ -d "/Applications/iZotope RX 11 Audio Editor.app" ] && echo "true" || echo "false")
    KILL_RX_CMD  := osascript -e 'tell application "iZotope RX 11 Audio Editor" to quit'
else ifeq ($(OS), Linux)
    OPEN_CMD     := xdg-open
    PYTHON_CMD   := python3.12
    HAS_RX11     := false
    KILL_RX_CMD  := true
else
    # Fallback / Windows con WSL o altri sistemi
    OPEN_CMD     := echo "Apertura automatica non supportata su questo OS:"
    PYTHON_CMD   := python3
    HAS_RX11     := false
    KILL_RX_CMD  := true
endif

# --- Configurazione directory ---
PWD_DIR := $(shell pwd)
GENDIR := generated
INCDIR := src
LOGDIR := logs
CSDIR  := csound
SFDIR  := output
SSDIR  := refs
YMLDIR := configs

# --- Flags configurabili ---
AUTOKILL ?= true
AUTOPEN ?= true
AUTOVISUAL ?= true
SHOWSTATIC ?= true
FILE ?= test-lez
TEST ?= false
PRECLEAN ?=true
STEMS ?= false

# Include moduli
include make/test.mk
include make/utils.mk
include make/audioFile.mk
include make/build.mk
include make/clean.mk

# --- Infrastruttura: creazione directory ---
$(GENDIR):
	mkdir -p $@

$(SFDIR):
	mkdir -p $@

$(LOGDIR):
	mkdir -p $@

# --- Setup iniziale ---
.PHONY: setup
setup: $(GENDIR) $(SFDIR) $(LOGDIR) venv-setup
	@echo "✅ [SETUP] Project ready."

# --- Help ---
.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo " Granular Synthesis - Comandi disponibili:"
	@echo ""
	@echo "  Setup:"
	@echo "  make setup           - Setup completo progetto"
	@echo "  make venv-setup      - Setup virtual environment"
	@echo ""
	@echo " Build:"
	@echo "  make all             - Build pipeline (YAML→SCO→AIF)"
	@echo "  make FILE=nome       - Build singolo file"
	@echo ""
	@echo " Testing:"
	@echo "  make tests  - Esegui test"
	@echo ""
	@echo " Utility:"
	@echo "  make open            - Apri file audio generati"
	@echo "  make pdf             - Apri PDF generati"
	@echo "  make sync            - Git add/commit/pull/push"
	@echo "  make rx-stop         - Chiudi iZotope RX 11"
	@echo ""
	@echo " Pulizia:"
	@echo "  make clean           - Pulisci file generati"
	@echo "  make clean-all       - Pulizia completa (+ venv)"
	@echo ""
	@echo "  Flags:"
	@echo "  AUTOKILL=true/false  - Auto-chiudi RX prima di build"
	@echo "  AUTOPEN=true/false   - Auto-apri file generati"
	@echo "  AUTOVISUAL=true/false- Genera visualizzazioni PDF"
	@echo "  TEST=true/false      - Build tutti i file o solo FILE"