#---------- $(INPUT)-$(SKIP_)-$(DURATA_).wav ---
SKIP?=0.0
SKIP_:=$(subst .,_,$(SKIP))
DURATA?=30.0
DURATA_:=$(subst .,_,$(DURATA))
INPUT?=001

$(INPUT)-$(SKIP_)-$(DURATA_).wav: refs/$(INPUT).wav
	sox $(SSDIR)/$(INPUT).wav $@ trim $(SKIP) $(DURATA)
	mv $@ $(SSDIR)/$@
	@if [ "$(AUTOPEN)" = "true" ]; then open $(SSDIR)/$@; fi

