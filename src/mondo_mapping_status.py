"""Mapping status between Medgen and Mondo"""
from pathlib import Path
from typing import List, Set, Tuple

import pandas as pd

SRC_DIR = Path(__file__).parent
PROJECT_DIR = SRC_DIR.parent
OUTDIR = PROJECT_DIR / 'output'
RELEASE_OUTDIR = OUTDIR / 'release'
INPUT_DIR = PROJECT_DIR / 'tmp' / 'input'
MONDO_SSSOM_TSV = INPUT_DIR / 'mondo.sssom.tsv'
MEDGEN_SSSOM_TSV = RELEASE_OUTDIR / 'medgen.sssom.tsv'
# MEDGEN_PREFIXES: Some of these are old, some are new, some may not be used.
MEDGEN_PREFIXES = ['Medgen', 'MedGen', 'MEDGEN', 'Medgen_UID', 'MedGen_UID', 'UMLS', 'UMLS_CUI']
CURIE = str


def ids_prefixless(ids: Set[str]) -> Set[str]:
    """Remove prefix"""
    return set([x.split(':')[1] for x in ids])


def ids_drop_uids(ids: Set[CURIE]) -> Set[CURIE]:
    """From a set of Medgen IDs, drop those that are UIDs"""
    return set([x for x in ids if x.split(':')[1].startswith('C')])

def read_mapping_sources(
    mondo_predicate_filter: List[str] = None,
    drop_uids=True
) -> Tuple[Set[CURIE], Set[CURIE], Set[CURIE]]:
    """Read data sources
    :param drop_uids: drop UIDs from Medgen IDs. These are ones that don't start with CN or C, and are IDs that are used
    only internally in Medgen and are not stable."""
    medgen_df = pd.read_csv(MEDGEN_SSSOM_TSV, sep='\t', comment='#').fillna('')
    # todo: move commented line to .ipynb
    # preds = list(medgen_df['predicate_id'].unique())  # oboInOwl:hasDbXref, owl:equivalentClass
    medgen_in_medgen: Set[CURIE] = set(list(medgen_df['subject_id']))

    mondo_df = pd.read_csv(MONDO_SSSOM_TSV, sep='\t', comment='#').fillna('')  # n=72,902
    mondo_df['prefix'] = mondo_df['object_id'].apply(lambda x: x.split(':')[0])
    mondo_df = mondo_df[mondo_df['prefix'].isin(MEDGEN_PREFIXES)]  # n=16,627
    del mondo_df['prefix']
    # todo: move commented line to .ipynb
    # preds = list(mondo_df['predicate_id'].unique())  # only skos:exactMatch
    if mondo_predicate_filter:  # leaving for now; but has no effect because only skos:exactMatch exists
        mondo_df = mondo_df[mondo_df['predicate_id'].isin(mondo_predicate_filter)]
    medgen_in_mondo: Set[CURIE] = set(mondo_df['object_id'].tolist())

    medgen_all_ids = medgen_in_medgen.union(medgen_in_mondo)

    if drop_uids:
        medgen_all_ids = ids_drop_uids(medgen_all_ids)
        medgen_in_medgen = ids_drop_uids(medgen_in_medgen)
        medgen_in_mondo = ids_drop_uids(medgen_in_mondo)

    return medgen_all_ids, medgen_in_medgen, medgen_in_mondo

def report_obs_medgen_in_mondo(medgen_in_mondo: Set[str], medgen_in_medgen: Set[str]):
    """Obsoleted Medgen terms in Mondo"""
    # obsoleted_medgen_terms_in_mondo.txt: get a list of obsolete Medgen terms that are still in Mondo
    in_mondo_not_in_medgen = medgen_in_mondo.difference(medgen_in_medgen)
    obs_medgen_in_mondo_df = pd.DataFrame()
    obs_medgen_in_mondo_df['id'] = sorted([x for x in in_mondo_not_in_medgen])
    obs_medgen_in_mondo_df = obs_medgen_in_mondo_df.sort_values(by='id')
    obs_medgen_in_mondo_df.to_csv(OUTDIR / 'obsoleted_medgen_terms_in_mondo.txt', index=False, header=False)

def report_existing_overlap(medgen_all_ids: Set[str], medgen_in_medgen: Set[str], medgen_in_mondo: Set[str], file_suffix: str):
    """Get explicit, existing mapping status overlaps between Medgen and Mondo
    These are mappings at the time before we began the Medgen ingest, and we this was useful for analytical information
    at the time, but we maybe should drop this because not using for curation. We're not keeping the previous
    Mondo::Medgen mappings from Mondo."""
    existing_overlap_df = pd.DataFrame()
    existing_overlap_df['subject_id'] = list(medgen_all_ids)
    existing_overlap_df['in_medgen'] = existing_overlap_df['subject_id'].isin(medgen_in_medgen)
    existing_overlap_df['in_mondo'] = existing_overlap_df['subject_id'].isin(medgen_in_mondo)
    existing_overlap_df['status'] = existing_overlap_df['subject_id'].apply(
        lambda x:
        'medgen' if x in medgen_in_medgen and x not in medgen_in_mondo else
        'mondo' if x in medgen_in_mondo and x not in medgen_in_medgen else
        'both')
    existing_overlap_df = existing_overlap_df.sort_values(['status', 'subject_id', 'in_medgen', 'in_mondo'])
    # todo: move to .ipynb
    # tot_medgen = len(existing_overlap_df[existing_overlap_df['status'] == 'medgen'])  # n=66,224
    # tot_mondo = len(existing_overlap_df[existing_overlap_df['status'] == 'mondo'])  # n=2,362
    # tot_both = len(existing_overlap_df[existing_overlap_df['status'] == 'both'])  # n=14,263
    existing_overlap_df.to_csv(OUTDIR / f'medgen_terms_mapping_status{file_suffix}.tsv', index=False, sep='\t')

def medgen_mondo_mapping_status(mondo_predicate_filter: List[str] = None):
    """Mapping status between Medgen and Mondo"""
    # Vars
    file_suffix = '' if not mondo_predicate_filter \
        else '-mondo-exacts-only' if mondo_predicate_filter == ['skos:exactMatch'] \
        else '-custom'
    # Read sources
    medgen_all_ids, medgen_in_medgen, medgen_in_mondo = \
        read_mapping_sources(mondo_predicate_filter=mondo_predicate_filter)
    # Special operations
    # - Inconsistent prefixes between what Mondo used before and will going forward. In this case, stripping prefixes
    # should be OK, at least for now.
    medgen_all_ids = ids_prefixless(medgen_all_ids)
    medgen_in_medgen = ids_prefixless(medgen_in_medgen)
    medgen_in_mondo = ids_prefixless(medgen_in_mondo)
    # Report
    report_obs_medgen_in_mondo(medgen_in_mondo, medgen_in_medgen)
    report_existing_overlap(medgen_all_ids, medgen_in_medgen, medgen_in_mondo, file_suffix)

def run():
    """Run reports"""
    # # filters: could be set up if needed, but current Medgen & previous Mondo only have exactMatch
    # filters = [None, ['skos:exactMatch']]
    # for f in filters:
    #     medgen_mondo_mapping_status(f)
    medgen_mondo_mapping_status()


if __name__ == '__main__':
    run()
