"""Utils"""
from pathlib import Path
from typing import Dict, List, Union

import curies
import pandas as pd
import yaml
from sssom import MappingSetDataFrame
from sssom.writers import write_table


def add_prefixes_to_plain_id(x: str) -> str:
    """From plain IDs from originanl source, add prefixes.

    Terms:
        CN: stands for "CUI Novel". These are created for any MedGen records without UMLS CUI.
        C: stands for "CUI". These are sourced from UMLS.
        CUI: stands for "Concept Unique Identifier"
        UID (Unique IDentifier): These are cases where the id is all digits; does not start with a leading alpha char.
    """
    return f'MEDGENCUI:{x}' if x.startswith('CN') \
        else f'UMLS:{x}' if x.startswith('C') \
        else f'MEDGEN:{x}'


# todo: Add to sssom-py. Shared between, at the least, ICD11 and MedGen repos
def write_sssom(df: pd.DataFrame, config_path: Union[Path, str], outpath: Union[Path, str]):
    """Writes a SSSOM file"""
    with open(config_path, 'r') as yaml_file:
        metadata: Dict = yaml.load(yaml_file, Loader=yaml.FullLoader)
    converter = curies.Converter.from_prefix_map(metadata['curie_map'])
    msdf: MappingSetDataFrame = MappingSetDataFrame(converter=converter, df=df, metadata=metadata)
    with open(outpath, 'w') as f:
        write_table(msdf, f)


# todo: for the SSSOM use case, it is weird to rename #CUI as xref_id. so maybe _get_mapping_set() should either not
#  common code for this and robot template, or add a param to not rename that col
def get_mapping_set(
    inpath: Union[str, Path], filter_sources: List[str] = None, add_prefixes=False, sssomify=True,
    filter_out_medgencui=True
) -> pd.DataFrame:
    """Load up MedGen mapping set (MedGenIDMappings.txt), with some modifications."""
    # Read
    df = pd.read_csv(inpath, sep='|').rename(columns={
        '#CUI_or_CN_id': 'xref_id',
    })
    # Remove empty columns
    empty_cols = [col for col in df.columns if df[col].isnull().all()]  # caused by trailing | at end of each row
    if empty_cols:
        df = df.drop(columns=empty_cols)
    # Filter MEDGENCUI & add prefixes
    df['xref_id'] = df['xref_id'].apply(add_prefixes_to_plain_id)
    # - Filter MEDGENCUI
    if filter_out_medgencui:
        df = df[~df['xref_id'].str.startswith('MEDGENCUI')]
    # - Add prefixes
    if not add_prefixes:
        del df['xref_id']
    # Sort
    df = df.sort_values(['xref_id', 'source_id'])
    if filter_sources:
        df = df[df['source'].isin(filter_sources)]
        del df['source']
    # Standardize to SSSOM
    if sssomify:
        df = df.rename(columns={
            'xref_id': 'subject_id',
            'pref_name': 'subject_label',
            'source_id': 'object_id',
        })
        df['predicate_id'] = 'skos:exactMatch'
        df = df[['subject_id', 'subject_label', 'predicate_id', 'object_id']]
    return df
