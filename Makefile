PWD_DIR := $(shell pwd)
INCDIR:=src
SSDIR:=refs
SFDIR:=output

all: python csound

python:
	python3.11 $(INCDIR)/test.py $(INCDIR)/file.yml $(INCDIR)/partitura.sco

csound:
	csound \
	--env:INCDIR+=$(PWD_DIR)/$(INCDIR) \
	--env:SSDIR+=$(PWD_DIR)/$(SSDIR) \
	--env:SFDIR=$(PWD_DIR)/$(SFDIR) \
	$(INCDIR)/main.orc $(INCDIR)/partitura.sco

open:
	open output/*.aif

sync:
	git add .
	git commit -m "."
	git pull --quiet
	git push

.PHONY=csound python open synch
