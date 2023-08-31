"""Medgen->Mondo robot template

Create a robot template to be used by Mondo to add MedGen xrefs curated by MedGen.

See also:
- PR: https://github.com/monarch-initiative/medgen/pull/9
- Used here: https://github.com/monarch-initiative/mondo/pull/6560
"""
from argparse import ArgumentParser
from copy import copy
from pathlib import Path
from typing import Dict, List

import pandas as pd

SRC_DIR = Path(__file__).parent
PROJECT_DIR = SRC_DIR.parent
FTP_DIR = PROJECT_DIR / "ftp.ncbi.nlm.nih.gov" / "pub" / "medgen"
INPUT_FILE = str(FTP_DIR / "MedGenIDMappings.txt")
OUTPUT_FILE = str(PROJECT_DIR / "medgen-xrefs.robot.template.tsv")


def _prefixed_id_rows_from_common_df(source_df: pd.DataFrame, mondo_col='mondo_id', xref_col='xref_id') -> List[Dict]:
    """From worksheets having same common format, get prefixed xrefs for the namespaces we're looking to cover

    Note: This same exact function is used in:
    - mondo repo: medgen_conflicts_add_xrefs.py
    - medgen repo: mondo_robot_template.py"""
    df = copy(source_df)
    df[xref_col] = df[xref_col].apply(
        lambda x: f'MEDGENCUI:{x}' if x.startswith('CN')  # "CUI Novel"
        else f'UMLS:{x}' if x.startswith('C')  # CUI: will be created twice: one for MEDGENCUI, one for UMLS
        else f'MEDGEN:{x}')  # UID
    rows = df.to_dict('records')
    rows2 = [{mondo_col: x[mondo_col], xref_col: x[xref_col].replace('UMLS', 'MEDGENCUI')} for x in rows if
             x[xref_col].startswith('UMLS')]
    return rows + rows2


def run(input_file: str = INPUT_FILE, output_file: str = OUTPUT_FILE):
    """Create robot template"""
    # Read input
    df = pd.read_csv(input_file, sep='|').rename(columns={'#CUI': 'xref_id'})

    # Get explicit Medgen (CUI, CN) -> Mondo mappings
    df_medgen_mondo = df[df['source'] == 'MONDO'][['source_id', 'xref_id']].rename(columns={'source_id': 'mondo_id'})
    out_df_cui_cn = pd.DataFrame(_prefixed_id_rows_from_common_df(df_medgen_mondo))

    # Get Medgen (UID) -> Mondo mappings
    # - Done by proxy: UID <-> CUI <-> MONDO
    df_medgen_medgenuid = df[df['source'] == 'MedGen'][['source_id', 'xref_id']].rename(
        columns={'source_id': 'medgen_uid'})
    out_df_uid = pd.merge(df_medgen_mondo, df_medgen_medgenuid, on='xref_id')[['mondo_id', 'medgen_uid']]\
        .rename(columns={'medgen_uid': 'xref_id'})
    out_df_uid['xref_id'] = out_df_uid['xref_id'].apply(lambda x: f'MEDGEN:{x}')

    # Save
    out_df = pd.concat([out_df_cui_cn, out_df_uid]).sort_values(['xref_id', 'mondo_id']).drop_duplicates()
    out_df = pd.concat([pd.DataFrame([{'mondo_id': 'ID', 'xref_id': 'A oboInOwl:hasDbXref'}]), out_df])
    out_df.to_csv(output_file, index=False, sep='\t')

def cli():
    """Command line interface."""
    parser = ArgumentParser(
        prog='"Medgen->Mondo robot template',
        description='Create a robot template to be used by Mondo to add MedGen xrefs curated by MedGen.')
    parser.add_argument(
        '-i', '--input-file', default=INPUT_FILE, help='Mapping file sourced from MedGen')
    parser.add_argument(
        '-o', '--output-file', default=OUTPUT_FILE, help='ROBOT template to be used to add xrefs')
    run(**vars(parser.parse_args()))


if __name__ == '__main__':
    cli()
