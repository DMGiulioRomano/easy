# make/clean.mk
# Pulizia directory generate

.PHONY: clean clean-all clean-generated clean-output clean-logs

clean:
	@echo "🧹 [CLEAN] Removing generated files..."
	rm -rf $(GENDIR)/* $(SFDIR)/* $(LOGDIR)/*

clean-all: clean venv-clean
	@echo "🧹 [CLEAN] Full cleanup done."

clean-generated:
	rm -rf $(GENDIR)/*

clean-output:
	rm -rf $(SFDIR)/*

clean-logs:
	rm -rf $(LOGDIR)/*