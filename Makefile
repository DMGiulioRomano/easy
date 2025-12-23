PWD_DIR := $(shell pwd)
INCDIR:=src
SSDIR?=refs
SFDIR:=output
GENDIR := $(INCDIR)/generated
YML_FILES := $(wildcard $(INCDIR)/*.yml)
SCO_FILES := $(patsubst $(INCDIR)/%.yml,$(GENDIR)/%.sco,$(YML_FILES))
AIF_FILES := $(patsubst $(GENDIR)/%.sco,$(SFDIR)/%.aif,$(SCO_FILES))

SKIP?=0.0
SKIP_:=$(subst .,_,$(SKIP))
DURATA?=30.0
DURATA_:=$(subst .,_,$(DURATA))
INPUT?=001

FILE?=file1
TEST?=false
.SECONDARY: $(SCO_FILES)


ifeq ($(TEST), true)
all: $(AIF_FILES)
else
all: $(SFDIR)/$(FILE).aif
endif

$(GENDIR)/%.sco: $(INCDIR)/%.yml | $(GENDIR)
	python3.11 $(INCDIR)/test.py $< $@

$(GENDIR):
	mkdir -p $@

$(SFDIR)/%.aif: $(GENDIR)/%.sco | $(SFDIR)
	csound \
	--env:INCDIR+=$(PWD_DIR)/$(INCDIR) \
	--env:SSDIR+=$(PWD_DIR)/$(SSDIR) \
	--env:SFDIR=$(PWD_DIR)/$(SFDIR) \
	$(INCDIR)/main.orc $< \
	-o $@

$(SFDIR):
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
	rm -f $(SFDIR)/*.aif $(GENDIR)/*.sco *.wav

.PHONY: open sync test clean
