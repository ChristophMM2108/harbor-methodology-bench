# Harbor Methodology Bench whitepaper
#
#   make            regenerate everything, then compile both documents
#   make paper      compile main.tex only   (full, 48 pp)
#   make brief      compile brief.tex only  (short report, 19 pp)
#   make figures    regenerate figures/*.pdf and *.png
#   make diagrams   render diagrams/*.mmd to PDF and PNG
#   make tables     regenerate tables/*.tex
#   make citations  regenerate data/citation-map.md from the .bib and the two .tex files
#   make data       recompute verified_numbers.json and best_of_n.json
#   make clean      remove build artefacts (keeps generated figures and tables)

PY      := $(CURDIR)/../.venv/bin/python
TECTONIC := $(shell command -v tectonic 2>/dev/null || echo $(HOME)/.local/bin/tectonic)

.PHONY: all paper brief figures diagrams tables data citations clean distclean

all: data figures diagrams tables paper brief citations

paper:
	$(TECTONIC) -X compile main.tex
	$(TECTONIC) -X compile main.tex        # second pass for the TOC and cross-references

brief:
	$(TECTONIC) -X compile brief.tex
	$(TECTONIC) -X compile brief.tex

data:
	$(PY) scripts/verify_numbers.py
	$(PY) scripts/best_of_n.py

figures:
	cd scripts && $(PY) make_figures_perrun.py
	cd scripts && $(PY) make_figures_cross.py

diagrams:
	./scripts/render_diagrams.sh

tables:
	cd scripts && $(PY) make_tables.py
	cd scripts && $(PY) make_tables_brief.py

citations:
	$(PY) scripts/make_citation_map.py

clean:
	rm -f main.log main.aux main.out main.toc main.xdv main.bbl main.blg \
	      brief.log brief.aux brief.out brief.xdv brief.bbl brief.blg \
	      diagrams/puppeteer.json

distclean: clean
	rm -f main.pdf brief.pdf figures/*.pdf figures/*.png diagrams/*.pdf diagrams/*.png tables/*.tex
