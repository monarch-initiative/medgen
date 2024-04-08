"""Create SSSOM outputs"""
from argparse import ArgumentParser
from pathlib import Path

import pandas as pd

from utils import get_mapping_set, write_sssom

SRC_DIR = Path(__file__).parent
PROJECT_DIR = SRC_DIR.parent
FTP_DIR = PROJECT_DIR / "ftp.ncbi.nlm.nih.gov" / "pub" / "medgen"
CONFIG_DIR = PROJECT_DIR / "config"
INPUT_MAPPINGS = str(FTP_DIR / "MedGenIDMappings.txt")
INPUT_CONFIG = str(CONFIG_DIR / "medgen.sssom-metadata.yml")
OUTPUT_FILE_HPO_UMLS = str(PROJECT_DIR / "umls-hpo.sssom.tsv")
OUTPUT_FILE_HPO_MESH = str(PROJECT_DIR / "hpo-mesh.sssom.tsv")


def _filter_and_format_cols(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """FIlter dataframe by source and format columns."""
    return df[df['source'] == source][['subject_id', 'subject_label', 'predicate_id', 'object_id']]


def run(input_mappings: str = INPUT_MAPPINGS, input_sssom_config: str = INPUT_CONFIG, hpo_match_only_with_umls=True):
    """Create SSSOM outputs

    :param hpo_match_only_with_umls: If True, only create SSSOM outputs for HPO mappings that have UMLS mappings, and
    will filter out other matches. This is purely edge case handling. As of 2024/04/06, 100% of the mappings were UMLS
    anyway."""
    # SSSOM 1: HPO<->UMLS
    df_hpo_umls = get_mapping_set(input_mappings, ['HPO'], add_prefixes=True)
    if hpo_match_only_with_umls:
        df_hpo_umls = df_hpo_umls[df_hpo_umls['subject_id'].str.startswith('UMLS:')]
    df_hpo_umls['mapping_justification'] = 'semapv:ManualMappingCuration'
    write_sssom(df_hpo_umls, input_sssom_config, OUTPUT_FILE_HPO_UMLS)

    # SSSOM 2: HPO<->MeSH
    # - filter
    df_hpo_mesh = get_mapping_set(input_mappings, ['MeSH'], add_prefixes=True)
    # - JOIN data: some cols temporary for temporary report for non-matches
    df_hpo_mesh = pd.merge(df_hpo_mesh, df_hpo_umls, on='subject_id', how='left').rename(columns={
        'subject_id': 'umls_id',
        'subject_label_x': 'umls_label',
        'predicate_id_x': 'predicate_id',
        'object_id_x': 'object_id',
        'object_id_y': 'subject_id',
    })
    # -- sort cols & sort rows & drop unneeded cols (subject_label_y, predicate_id_y)
    df_hpo_mesh = df_hpo_mesh[['subject_id', 'predicate_id', 'object_id', 'umls_id', 'umls_label']].sort_values(
        ['subject_id', 'object_id'], na_position='first')
    # -- add missing prefixes
    df_hpo_mesh['object_id'] = df_hpo_mesh['object_id'].apply(lambda x: 'MESH:' + x)
    # todo: temp; (1) remove later: saving dataset with no matches, for review (2) after remove, will need to
    #  move the col removals below (umls) to above
    # - add mapping_justification
    df_hpo_mesh['mapping_justification'] = 'semapv:ManualMappingCuration'
    write_sssom(df_hpo_mesh, input_sssom_config,
                OUTPUT_FILE_HPO_MESH.replace('.sssom.tsv', '-non-matches-included.sssom.tsv'))
    # -- filter non-matches & drop unneeded cols
    df_hpo_mesh = df_hpo_mesh[df_hpo_mesh['subject_id'].notna()][[
        x for x in df_hpo_mesh.columns if not x.startswith('umls')]]
    write_sssom(df_hpo_mesh, input_sssom_config, OUTPUT_FILE_HPO_MESH)


def cli():
    """Command line interface."""
    parser = ArgumentParser(
        prog='Create SSSOM outputs',
        description='Create SSSOM outputs from MedGen source')
    parser.add_argument(
        '-m', '--input-mappings', default=INPUT_MAPPINGS, help='Path to mapping file sourced from MedGen.')
    parser.add_argument(
        '-c', '--input-sssom-config', default=INPUT_CONFIG, help='Path to SSSOM config yml.')
    run(**vars(parser.parse_args()))


if __name__ == '__main__':
    cli()
