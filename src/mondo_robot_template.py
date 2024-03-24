"""Medgen->Mondo robot template

Create a robot template to be used by Mondo to add MedGen xrefs curated by MedGen.

See also:
- PR: https://github.com/monarch-initiative/medgen/pull/9
- Used here: https://github.com/monarch-initiative/mondo/pull/6560
"""
from argparse import ArgumentParser
from pathlib import Path

import pandas as pd

from utils import add_prefixes_to_plain_id, get_mapping_set

SRC_DIR = Path(__file__).parent
PROJECT_DIR = SRC_DIR.parent
FTP_DIR = PROJECT_DIR / "ftp.ncbi.nlm.nih.gov" / "pub" / "medgen"
INPUT_FILE = str(FTP_DIR / "MedGenIDMappings.txt")
OUTPUT_FILE = str(PROJECT_DIR / "medgen-xrefs.robot.template.tsv")
ROBOT_ROW_MAP = {
    'mondo_id': 'ID',
    'xref_id': 'A oboInOwl:hasDbXref',
    'source_id': '>A oboInOwl:source',
    'source_medgen_id': '>A oboInOwl:source',
    'mapping_predicate': '>A oboInOwl:source',
}


# todo: refactor to use get_mapping_set(): (1) *maybe* use SSSOM as the intermediate standard (sssomify=True), and
#  update column renames below. and (2) use filter_sources (already used by MeSH).
def run(input_file: str = INPUT_FILE, output_file: str = OUTPUT_FILE, filter_out_medgencui=True):
    """Create robot template

    :param filter_out_medgencui: There should be no cases where Mondo or any other sources we care about will be
    MEDGENCUI (CN) instances, but we know we do not want them, so this default filtration step helps with that possible
    future edge case."""
    # Read input
    df = get_mapping_set(input_file, add_prefixes=True, sssomify=False, filter_out_medgencui=filter_out_medgencui)

    # Mondo->MEDGEN & Mondo->UMLS
    # 1. Get explicit Medgen (CUI, CN) -> Mondo mappings
    df_umls_mondo = df[df['source'] == 'MONDO'][['source_id', 'xref_id']].rename(
        columns={'source_id': 'mondo_id', 'xref_id': 'umls_cui'})

    # 2. Get Medgen (UID) -> Mondo mappings
    # - Done by proxy: UID <-> CUI <-> MONDO
    df_umls_medgenuid = df[df['source'] == 'MedGen'][['source_id', 'xref_id']].rename(
        columns={'source_id': 'medgen_uid', 'xref_id': 'umls_cui'})
    df_umls_medgenuid['medgen_uid'] = (
        df_umls_medgenuid['medgen_uid'].apply(add_prefixes_to_plain_id))  # should/will all be MEDGEN
    df_merged = pd.merge(df_umls_mondo, df_umls_medgenuid, on='umls_cui')
    # - Split into (Mondo <-> Medgen UID) & (Mondo <-> UMLS CUI)
    out_df_medgenuid = df_merged.rename(columns={'medgen_uid': 'xref_id', 'umls_cui': 'source_id'})[[
        'mondo_id', 'xref_id', 'source_id']]
    out_df_medgenuid['source_id'] = ''
    out_df_umlscui = df_merged.rename(columns={'umls_cui': 'xref_id', 'medgen_uid': 'source_id'})

    # Mondo->MESH
    df_umls_mesh = get_mapping_set(input_file, filter_sources=['MeSH'], add_prefixes=True, sssomify=False)
    df_umls_mesh['source_id'] = df_umls_mesh['source_id'].apply(lambda x: 'mesh:' + x)
    out_df_mesh = pd.merge(df_umls_mesh, df_umls_mondo, left_on='xref_id', right_on='umls_cui').rename(
        columns={'source_id': 'xref_id', 'xref_id': 'source_id'})[['mondo_id', 'xref_id', 'source_id']]

    # Combine mappings
    out_df = pd.concat([out_df_medgenuid, out_df_umlscui, out_df_mesh]).sort_values(['xref_id', 'mondo_id'])\
        .drop_duplicates().fillna('')

    # Add additional cols
    out_df['source_medgen_id'] = 'MONDO:MEDGEN'
    # todo: could optimize by doing apply just on the xref_id col
    def set_mapping_pred(row):
        """Set mapping predicate"""
        # M = Concept UI; D = Descriptor UI; C = SupplementalRecordUI; Q = Qualifier UI
        pred = 'MONDO:equivalentTo' if row['xref_id'].startswith('mesh:M') \
            else 'MONDO:relatedTo' if row['xref_id'].startswith('mesh:') \
            else 'MONDO:equivalentTo'
        return pred
    # Context on MeSH IDs:
    #  https://docs.google.com/document/d/1ryu6isBmNEno8lyni70jBaw-D_I6tdEXpnnAK86ZWfs/edit#heading=h.3cho5esard3q
    out_df['mapping_predicate'] = out_df.apply(set_mapping_pred, axis=1)

    # Save
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
