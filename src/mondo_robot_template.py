"""Medgen->Mondo robot template

Create a robot template to be used by Mondo to add MedGen xrefs curated by MedGen.

See also:
- PR: https://github.com/monarch-initiative/medgen/pull/9
- Used here: https://github.com/monarch-initiative/mondo/pull/6560
"""
from argparse import ArgumentParser
from pathlib import Path

import pandas as pd

from utils import get_mapping_set, add_prefixes_to_plain_id

SRC_DIR = Path(__file__).parent
PROJECT_DIR = SRC_DIR.parent
FTP_DIR = PROJECT_DIR / "ftp.ncbi.nlm.nih.gov" / "pub" / "medgen"
INPUT_FILE = str(FTP_DIR / "MedGenIDMappings.txt")
OUTPUT_FILE = str(PROJECT_DIR / "medgen-xrefs.robot.template.tsv")
ROBOT_ROW_MAP = {
    'mondo_id': 'ID',
    'xref_id': 'A oboInOwl:hasDbXref',
    'source_id': '>A oboInOwl:source'
}


def run(input_file: str = INPUT_FILE, output_file: str = OUTPUT_FILE):
    """Create robot template"""
    # Read input
    df: pd.DataFrame = get_mapping_set(input_file)
    # Get explicit Medgen (CUI, CN) -> Mondo mappings
    df_medgen_mondo = df[df['source'] == 'MONDO'][['source_id', 'xref_id']].rename(columns={'source_id': 'mondo_id'})
    out_df_cui_cn = df_medgen_mondo.copy()
    out_df_cui_cn['xref_id'] = out_df_cui_cn['xref_id'].apply(add_prefixes_to_plain_id)

    # Get Medgen (UID) -> Mondo mappings
    # - Done by proxy: UID <-> CUI <-> MONDO
    df_medgen_medgenuid = df[df['source'] == 'MedGen'][['source_id', 'xref_id']].rename(
        columns={'source_id': 'medgen_uid'})
    # todo: should some of these steps be in _reformat_mapping_set()? to be utilized by SSSOM files?
    out_df_uid = pd.merge(df_medgen_mondo, df_medgen_medgenuid, on='xref_id').rename(
        columns={'xref_id': 'source_id', 'medgen_uid': 'xref_id'})[['mondo_id', 'xref_id', 'source_id']]
    out_df_uid['xref_id'] = out_df_uid['xref_id'].apply(lambda x: f'MEDGEN:{x}')
    out_df_uid['source_id'] = out_df_uid['source_id'].apply(lambda x: f'UMLS:{x}')

    # Save
    out_df = pd.concat([out_df_cui_cn, out_df_uid]).sort_values(['xref_id', 'mondo_id']).drop_duplicates().fillna('')
    out_df = pd.concat([pd.DataFrame([ROBOT_ROW_MAP]), out_df])
    out_df.to_csv(output_file, index=False, sep='\t')


def cli():
    """Command line interface."""
    parser = ArgumentParser(
        prog='Medgen->Mondo robot template',
        description='Create a robot template to be used by Mondo to add MedGen xrefs curated by MedGen.')
    parser.add_argument(
        '-i', '--input-file', default=INPUT_FILE, help='Path to mapping file sourced from MedGen')
    parser.add_argument(
        '-o', '--output-file', default=OUTPUT_FILE, help='Path to ROBOT template to be used to add xrefs')
    run(**vars(parser.parse_args()))


if __name__ == '__main__':
    cli()
