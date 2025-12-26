PWD_DIR:=$(shell pwd)
INCDIR:=src
SSDIR?=refs
LOGDIR:=logs
SFDIR:=output
GENDIR:=$(INCDIR)/generated
YMLDIR:=$(INCDIR)/configs
PYTHON_SOURCES := $(wildcard $(INCDIR)/*.py)
YML_FILES := $(wildcard $(YMLDIR)/*.yml)
SCO_FILES := $(patsubst $(YMLDIR)/%.yml,$(GENDIR)/%.sco,$(YML_FILES))
AIF_FILES := $(patsubst $(GENDIR)/%.sco,$(SFDIR)/%.aif,$(SCO_FILES))

SKIP?=0.0
SKIP_:=$(subst .,_,$(SKIP))
DURATA?=30.0
DURATA_:=$(subst .,_,$(DURATA))
INPUT?=001

FILE?=file1
TEST?=true
.SECONDARY: $(SCO_FILES)


ifeq ($(TEST), true)
all: $(AIF_FILES)
else
all: $(SFDIR)/$(FILE).aif
endif

$(GENDIR)/%.sco: $(YMLDIR)/%.yml $(PYTHON_SOURCES)| $(GENDIR)
	python3.11 $(INCDIR)/main.py $< $@

$(GENDIR):
	mkdir -p $@

$(SFDIR)/%.aif: $(GENDIR)/%.sco $(YMLDIR)/%.yml | $(SFDIR) $(LOGDIR)
	csound \
	--env:INCDIR+=$(PWD_DIR)/$(INCDIR) \
	--env:SSDIR+=$(PWD_DIR)/$(SSDIR) \
	--env:SFDIR=$(PWD_DIR)/$(SFDIR) \
	$(INCDIR)/main.orc $< \
	--logfile=$(LOGDIR)/$*.log \
	-o $@

$(SFDIR):
	mkdir -p $@

$(LOGDIR):
	mkdir -p $@

open:
	open $(SFDIR)/*.aif

sync:
	git add .
	git commit -m "."
	git pull --quiet
	git push

$(INPUT)-$(SKIP_)-$(DURATA_).wav: refs/$(INPUT).wav
	sox $(SSDIR)/$(INPUT).wav $@ trim $(SKIP) $(DURATA)
	mv $@ $(SSDIR)/$@ && open $(SSDIR)/$@

clean:
	rm -f $(SFDIR)/*.aif $(GENDIR)/*.sco *.wav logs/*.log

.PHONY: open sync test clean
