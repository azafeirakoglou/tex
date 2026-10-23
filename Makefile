# Ένα περιεχόμενο, δύο εκδόσεις· ανεξάρτητα aux και αυτόματες επαναλήψεις latexmk.
PYTHON ?= python3
BOOK_TARGETS = print2 screen
SAMPLE_TARGETS = sample-screen sample-print2 figures-screen figures-print2 \
 assessment-screen assessment-print2 tables-screen tables-print2 \
 opening-goals-screen opening-goals-print2 history-statements-screen history-statements-print2 \
 callouts-screen callouts-print2 palette-screen palette-print2

.PHONY: all book samples setup check-colors check-palette colors-regenerate clean \
 $(BOOK_TARGETS) $(SAMPLE_TARGETS)
all: book samples
book: $(BOOK_TARGETS)
samples: $(SAMPLE_TARGETS)
setup:
	$(PYTHON) scripts/setup_environment.py
check-colors:
	$(PYTHON) scripts/check_color_consistency.py
check-palette: check-colors
colors-regenerate:
	$(PYTHON) scripts/generate_colors.py
	$(PYTHON) scripts/check_color_consistency.py
$(BOOK_TARGETS) $(SAMPLE_TARGETS): check-colors
	$(PYTHON) scripts/build.py $@
# Διαγράφει μόνο τα παραγόμενα PDF/aux/log, ποτέ περιεχόμενο ή εγκατεστημένες γραμματοσειρές.
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"

.PHONY: preflight test
# Ελέγχει τα πραγματικά PDF και τις πλάκες, χωρίς μετατροπή των παραδοτέων.
preflight: book
	$(PYTHON) scripts/validate_pdf.py --print build/print/Physics_A_Print_Technical.pdf \
	 --screen build/screen/Physics_A_Screen.pdf --map config/color-map.json \
	 --report build/validation/report.json

test:
	$(PYTHON) -m unittest discover -s tests -v

.PHONY: export
export: preflight
	$(PYTHON) scripts/export_review.py

.PHONY: preflight-all
preflight-all: all
	$(PYTHON) scripts/validate_suite.py
