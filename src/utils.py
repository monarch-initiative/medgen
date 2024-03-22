"""Utils"""
import os
from pathlib import Path
from typing import List, Set, Union

import pandas as pd
import yaml


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


def find_prefixes_in_mapping_set(source_df: pd.DataFrame) -> Set[str]:
    """Find prefixes in mapping set"""
    df = source_df.copy()
    cols_with_prefixes = ['subject_id', 'object_id', 'predicate_id']
    prefixes = set()
    for col in cols_with_prefixes:
        col2 = col.replace('id', 'prefix')
        df[col2] = df[col].apply(lambda x: x.split(':')[0]
            if isinstance(x, str) else x)  # handles nan
        prefixes.update(set(df[col2].to_list()))
    return prefixes


def write_sssom(df: pd.DataFrame, config_path: Union[Path, str], outpath: Union[Path, str]):
    """Writes a SSSOM file with commented metadata at the top of the file.

    Filters only prefxes in curie_map that exist in the mapping set."""
    temp_filtered_config_path = str(config_path) + '.tmp'
    # Load config
    config = yaml.safe_load(open(config_path, 'r'))
    # Filter curie_map
    prefixes: Set[str] = find_prefixes_in_mapping_set(df)
    config['curie_map'] = {k: v for k, v in config['curie_map'].items() if k in prefixes}
    # Write
    with open(temp_filtered_config_path, 'w') as f:
        yaml.dump(config, f)
    write_tsv_with_comments(df, temp_filtered_config_path, outpath)
    os.remove(temp_filtered_config_path)


def write_tsv_with_comments(df: pd.DataFrame, comments_file: Union[Path, str], outpath: Union[Path, str]):
    """Write a TSV with comments at the top"""
    # write metadata
    f = open(comments_file, "r")
    lines = f.readlines()
    f.close()
    output_lines = []
    for line in lines:
        output_lines.append("# " + line)
    metadata_str = ''.join(output_lines)
    if os.path.exists(outpath):
        os.remove(outpath)
    f = open(outpath, 'a')
    f.write(metadata_str)
    f.close()
    # write data
    df.to_csv(outpath, index=False, sep='\t', mode='a')


# todo: for the SSSOM use case, it is weird to rename #CUI as xref_id. so maybe _get_mapping_set() should either not
#  common code for this and robot template, or add a param to not rename that col
def get_mapping_set(
    inpath: Union[str, Path], filter_sources: List[str] = None, add_prefixes=False, sssomify=True,
) -> pd.DataFrame:
    """Load up MedGen mapping set (MedGenIDMappings.txt), with some modifications."""
    # Read
    df = pd.read_csv(inpath, sep='|').rename(columns={'#CUI': 'xref_id'})
    # Remove empty columns
    empty_cols = [col for col in df.columns if df[col].isnull().all()]  # caused by trailing | at end of each row
    if empty_cols:
        df = df.drop(columns=empty_cols)
    # Add prefixes
    if add_prefixes:
        df['xref_id'] = df['xref_id'].apply(add_prefixes_to_plain_id)
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
