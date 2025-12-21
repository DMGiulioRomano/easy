PWD_DIR := $(shell pwd)
INCDIR:=src
SSDIR:=refs
SFDIR:=output
GENDIR := $(INCDIR)/generated
YML_FILES := $(wildcard $(INCDIR)/*.yml)
SCO_FILES := $(patsubst $(INCDIR)/%.yml,$(GENDIR)/%.sco,$(YML_FILES))
AIF_FILES := $(patsubst $(GENDIR)/%.sco,$(SFDIR)/%.aif,$(SCO_FILES))

TEST?=false
.SECONDARY: $(SCO_FILES)


ifeq ($(TEST), true)
all: $(AIF_FILES)
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

clean:
	rm -f $(SFDIR)/*.aif $(GENDIR)/*.sco

.PHONY: open sync test clean
