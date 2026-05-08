.PHONY: all clean

MAIN = main

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib
	pdflatex $(MAIN)
	bibtex $(MAIN)
	pdflatex $(MAIN)
	pdflatex $(MAIN)

clean:
	rm -f $(MAIN).{aux,bbl,blg,log,out,pdf,toc,fls,fdb_latexmk,synctex.gz}
