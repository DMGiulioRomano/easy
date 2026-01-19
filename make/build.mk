# make/csound.mk
# Pipeline di generazione: YAML → SCO → AIF

# Variabili derivate per la pipeline
PYTHON_SOURCES := $(wildcard $(INCDIR)/*.py)
YML_FILES := $(wildcard $(YMLDIR)/*.yml)
SCO_FILES := $(patsubst $(YMLDIR)/%.yml,$(GENDIR)/%.sco,$(YML_FILES))
AIF_FILES := $(patsubst $(GENDIR)/%.sco,$(SFDIR)/%.aif,$(SCO_FILES))

# Non eliminare file intermedi .sco
.SECONDARY: $(SCO_FILES)

# --- Logica condizionale per flags ---

ifeq ($(AUTOVISUAL), true)
PYFLAG = --visualize
else
PYFLAG =
endif

ifeq ($(AUTOKILL),true)
ALL_PRE = rx-stop
else
ALL_PRE =
endif

# --- Target principale ---

.PHONY: all
ifeq ($(TEST), true)
all: $(ALL_PRE) $(AIF_FILES)
else
all: $(ALL_PRE) $(SFDIR)/$(FILE).aif
endif

# --- Regole di build ---

# YAML → SCO (Python)
$(GENDIR)/%.sco: $(YMLDIR)/%.yml $(PYTHON_SOURCES) | $(GENDIR)
	python3.11 $(INCDIR)/main.py $< $@ $(PYFLAG)

# SCO → AIF (Csound)
$(SFDIR)/%.aif: $(GENDIR)/%.sco $(YMLDIR)/%.yml | $(SFDIR) $(LOGDIR)
	csound \
		--env:INCDIR+=$(PWD_DIR)/$(INCDIR) \
		--env:SSDIR+=$(PWD_DIR)/$(SSDIR) \
		--env:SFDIR=$(PWD_DIR)/$(SFDIR) \
		$(CSDIR)/main.orc $< \
		--logfile=$(LOGDIR)/$*.log \
		-o $@
	@if [ "$(AUTOPEN)" = "true" ] && [ "$$(uname)" = "Darwin" ]; then \
		open "$@"; \
	fi