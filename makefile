# MedGen ingest
# Running `make all` will run the full pipeline. Note that if the FTP files have already been downloaded, it'll skip
# that part. In order to force re-download, run `make all -B`.
.DEFAULT_GOAL := all
.PHONY: all build stage stage-% analyze clean deploy-release

OBO=http://purl.obolibrary.org/obo
PRODUCTS=medgen-disease-extract.obo medgen-disease-extract.owl
TODAY ?=$(shell date +%Y-%m-%d)
VERSION=v$(TODAY)

all: build stage clean analyze
# analyze: runs more than just this file; that goal creates multiple files
analyze: output/medgen_terms_mapping_status.tsv
build: $(PRODUCTS) medgen.sssom.tsv
stage: $(patsubst %, stage-%, $(PRODUCTS))
	mv medgen.obo output/release/
	mv medgen.sssom.tsv output/release/
stage-%: % | output/release/
	mv $< output/release/
clean:
	rm medgen.obographs.json
	rm uid2cui.tsv
	rm *.obo

# ----------------------------------------
# Setup dirs
# ----------------------------------------
tmp/input/:
	mkdir -p $@
output/:
	mkdir -p $@
output/release/:
	mkdir -p $@

# ----------------------------------------
# ETL
# ----------------------------------------
ftp.ncbi.nlm.nih.gov:
	wget -r -np ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/ && touch $@

uid2cui.tsv:
	./src/make_uid2cui.pl > $@

# ----------------------------------------
# Main artefacts
# ----------------------------------------
# Hacky conversion to obo ----------------
# Relies on MGCONSO.RRF.gz etc being made by 'ftp.ncbi.nlm.nih.gov' step
medgen.obo: ftp.ncbi.nlm.nih.gov uid2cui.tsv
	./src/medgen2obo.pl > $@.tmp && mv $@.tmp $@

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

# SSSOM ----------------------------------
medgen.obographs.json:
	robot convert -i medgen-disease-extract.owl -o $@

medgen.sssom.tsv: medgen.obographs.json
	sssom parse medgen.obographs.json -I obographs-json -m config/medgen.sssom-metadata.yml -o $@

# ----------------------------------------
# Cycles	
# ----------------------------------------
# Requires: `blip-findall`. Also, some of the .obo files are in root and some are in release; might need changing.
%-cycles.tsv: %.obo
	blip-findall -i $< "subclass_cycle/2" -label -no_pred -use_tabs > $@

# ----------------------------------------
# Devops
# ----------------------------------------
deploy-release: | output/release/
	@test $(VERSION)
	gh release create $(VERSION) --notes "New release." --title "$(VERSION)" output/release/*

# ----------------------------------------
# Mapping analysis
# ----------------------------------------
tmp/input/mondo.sssom.tsv: | tmp/input/
	wget http://purl.obolibrary.org/obo/mondo/mappings/mondo.sssom.tsv -O $@

# creates more than just this file; that goal creates multiple files
output/medgen_terms_mapping_status.tsv output/obsoleted_medgen_terms_in_mondo.txt: | output/
	python src/mondo_mapping_status.py
