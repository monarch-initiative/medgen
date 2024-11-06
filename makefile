# MedGen ingest
# Running `make all` will run the full pipeline. Note that if the FTP files have already been downloaded, it'll skip
# that part. In order to force re-download, run `make all -B`.
# todo: remove parts of old make/perl pipeline no longer used
.DEFAULT_GOAL := all
.PHONY: all build stage stage-% analyze clean deploy-release build-lite minimal sssom sssom-validate

OBO=http://purl.obolibrary.org/obo
# todo: medgen-disease-extract.owl.gz?
PRODUCTS=medgen-disease-extract.obo medgen-disease-extract.owl medgen.owl.gz
TODAY ?=$(shell date +%Y-%m-%d)
VERSION=$(TODAY)

minimal: build-lite stage-lite clean
# stage-lite: These commented out files are produced by `all` but not by `minimal`. Just left here for reference. See: https://github.com/monarch-initiative/medgen/issues/11
stage-lite: | output/release/
#	mv medgen-disease-extract.owl output/release/
	mv *.obo output/release/
	mv medgen.ttl.gz output/release/
	mv *.robot.template.tsv output/release/
	mv *.sssom.tsv output/release/
build-lite: medgen.ttl.gz medgen-disease-extract.obo medgen-xrefs.robot.template.tsv umls-hpo.sssom.tsv sssom-validate

all: build stage clean analyze
# analyze: runs more than just this file; that goal creates multiple files
analyze: output/medgen_terms_mapping_status.tsv
build: $(PRODUCTS)
stage: $(patsubst %, stage-%, $(PRODUCTS))
stage-%: % | output/release/
	mv $< output/release/
clean:
	rm -f medgen.obographs.json
	rm -f uid2cui.tsv
	rm -f *.obo

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
ftp.ncbi.nlm.nih.gov/:
	wget -r -np ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/ && touch $@

uid2cui.tsv: ftp.ncbi.nlm.nih.gov/
	./src/make_uid2cui.pl > $@

# todo: an issue can happen where the file exists but it triest to run the goal again:
#  ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt already exists -- do you wish to overwrite (y or n)?
#  This happens because the prerequisite `ftp.ncbi.nlm.nih.gov/` is newer than the goal
#  `ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt`. When this happened, it was 5 hours newer. However, I don't
#  know how this can possibly be the case, since the goal is unzipped within that folder after the folder is created.
ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt: ftp.ncbi.nlm.nih.gov/
	@if [ -f "ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt.gz" ]; then \
		gzip -dk ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt.gz; \
	fi

# ----------------------------------------
# Main artefacts
# ----------------------------------------
# Hacky conversion to obo ----------------
# Relies on MGCONSO.RRF.gz etc being made by 'ftp.ncbi.nlm.nih.gov/' step
medgen.obo: ftp.ncbi.nlm.nih.gov/ uid2cui.tsv
	./src/medgen2obo.pl > $@.tmp && mv $@.tmp $@

medgen.ttl: medgen.obo
	robot convert --input $< --output $@ --format ttl

medgen.ttl.gz: medgen.ttl
	gzip -c $< > $@

# We only care about diseases for now
# - NOTE: some cancers seem to appear under Neoplastic-Process
x-%.obo: medgen.obo
	owltools $< --extract-subset $* --set-ontology-id $(OBO)/mondo/$@ -o -f obo $@

medgen-disease-extract.obo: x-Disease-or-Syndrome.obo x-Neoplastic-Process.obo
	owltools $^ --merge-support-ontologies -o -f obo $@

# todo: change this to robot convert w/ format ttl, lower memory usage?
output/medgen-disease-extract.owl: medgen-disease-extract.obo | output/
	owltools $< -o $@

# SSSOM ----------------------------------
sssom: umls-hpo.sssom.tsv sssom-validate

sssom-validate: umls-hpo.sssom.tsv
	sssom validate umls-hpo.sssom.tsv
	sssom validate hpo-mesh.sssom.tsv

# todo: Address GH action build heap space err:
#  https://github.com/monarch-initiative/medgen/actions/runs/9150396559/job/25155114016
#  Don't need to fix until the case where we need to use `make all` or otherwise need this file.
#medgen-disease-extract.json: medgen-disease-extract.obo
#	owltools $< -o -f json $@
output/medgen.obographs.json: output/medgen-disease-extract.owl | output/
	robot convert -i $< -o $@

output/medgen.sssom.tsv: output/medgen.obographs.json | output/
	sssom parse $< -I obographs-json -m config/medgen.sssom-metadata.yml -o $@

umls-hpo.sssom.tsv hpo-mesh.sssom.tsv output/hpo-mesh_non-matches-included.sssom.tsv: ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt | output/
	python src/create_sssom.py --input-mappings $< --input-sssom-config config/medgen.sssom-metadata.yml

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
output/medgen_terms_mapping_status.tsv output/obsoleted_medgen_terms_in_mondo.txt: tmp/input/mondo.sssom.tsv output/medgen.sssom.tsv | output/
	python src/mondo_mapping_status.py

# ----------------------------------------
# Robot templates
# ----------------------------------------
# todo: Ideally I wanted this done at the end of the ingest, permuting from medgen.sssom.tsv, but there were some
#  problems with that file. Eventually changing to that feels like it makes more sense. Will have already been
#  pre-curated by disease. And some of the logic in this Python script is duplicative.
medgen-xrefs.robot.template.tsv medgen-xrefs-mesh.robot.template.tsv: ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt
	python src/mondo_robot_template.py -i $< \
	--outpath-general medgen-xrefs.robot.template.tsv \
	--outpath-mesh medgen-xrefs-mesh.robot.template.tsv
