# make/utils.mk
# Utility per aprire file, git sync, etc.

COMMIT?="." 

.PHONY: open pdf sync rx-stop

open:
	open $(SFDIR)/*.aif

pdf:
	open $(GENDIR)/*.pdf

sync:
	git add .
	git commit -m "$(COMMIT)"
	git pull --quiet
	git push

rx-stop:
	@if [ "$$(uname)" = "Darwin" ] && \
	   [ -d "/Applications/iZotope RX 11 Audio Editor.app" ] && \
	   pgrep -f "iZotope RX 11" >/dev/null; then \
		echo "RX 11 attivo: AUTOKILL=true, chiusura in corso"; \
		osascript -e 'tell application "iZotope RX 11 Audio Editor" to quit' || true; \
		sleep 1; \
	else \
		echo "make: Nothing to be done for 'all'..."; \
	fi