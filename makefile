# MedGen ingest
# Running `make all` will run the full pipeline. Note that if the FTP files have already been downloaded, it'll skip
# that part. In order to force re-download, run `make all -B`.
.DEFAULT_GOAL := all
.PHONY: all build stage stage-%

OBO=http://purl.obolibrary.org/obo
PRODUCTS=medgen-disease-extract.obo medgen-disease-extract.owl
TODAY ?=$(shell date +%Y-%m-%d)
VERSION=v$(TODAY)

all: build stage
build: $(PRODUCTS)
stage: $(patsubst %, stage-%, $(PRODUCTS))
	mv medgen.obo release/
stage-%: % | release/
	mv $< release/

# ----------------------------------------
# ETL
# ----------------------------------------
release/:
	mkdir -p $@

ftp.ncbi.nlm.nih.gov:
	wget -r -np ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/ && touch $@

uid2cui.tsv:
	./bin/make_uid2cui.pl > $@

# ----------------------------------------
# Hacky conversion to obo
# ----------------------------------------
# Relies on MGCONSO.RRF.gz etc being made by 'ftp.ncbi.nlm.nih.gov' step
medgen.obo: ftp.ncbi.nlm.nih.gov uid2cui.tsv
	./bin/medgen2obo.pl > $@.tmp && mv $@.tmp $@

# We only care about diseases for now
# - NOTE: some cancers seem to appear under Neoplastic-Process
x-%.obo: medgen.obo
	owltools $< --extract-subset $* --set-ontology-id $(OBO)/mondo/$@ -o -f obo $@

medgen-disease-extract.obo: x-Disease-or-Syndrome.obo x-Neoplastic-Process.obo
	owltools $^ --merge-support-ontologies -o -f obo $@

medgen-disease-extract.json: medgen-disease-extract.obo
	owltools $< -o -f json $@

medgen-disease-extract.owl: medgen-disease-extract.obo
	owltools $< -o $@

# ----------------------------------------
# Cycles	
# ----------------------------------------
# Requires: `blip-findall`. Also, some of the .obo files are in root and some are in release; might need changing.
%-cycles.tsv: %.obo
	blip-findall -i $< "subclass_cycle/2" -label -no_pred -use_tabs > $@

# ----------------------------------------
# Devops
# ----------------------------------------
deploy-release: | release/
	@test $(VERSION)
	gh release create $(VERSION) --notes "New release." --title "$(VERSION)" release/*
