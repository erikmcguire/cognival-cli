#!/usr/bin/env python3

# Derived from: TODO
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action="ignore", category=DeprecationWarning)

import collections
import copy
import csv
import itertools
import json
import gzip
import os
import sys
import re
import shutil
import subprocess
import zipfile

from pathlib import Path
from textwrap import fill
from tqdm import tqdm

import gdown
from joblib import Parallel, delayed
from natsort import natsorted
from nubia import command, argument, context
import numpy as np
import pandas as pd
import tabulate
import tableformatter as tform

from prompt_toolkit.shortcuts import input_dialog, button_dialog, yes_no_dialog, message_dialog, radiolist_dialog, ProgressBar
from pygments import highlight
from pygments.lexers import MarkdownLexer
from pygments.formatters import TerminalFormatter
from termcolor import cprint, colored

from cog_evaluate_parallel import run_parallel
from handlers.file_handler import write_options
from handlers.data_handler import chunk
from handlers.binary_to_text_conversion import bert_to_text, elmo_to_text

from utils import word2vec_bin_to_txt

#sys.path.insert(0, 'significance_testing/')
from significance_testing.statisticalTesting import extract_results as st_extract_results
from significance_testing.aggregated_eeg_results import extract_results as agg_eeg_extr_results
from significance_testing.aggregated_fmri_results import extract_results as agg_fmri_extr_results
from significance_testing.aggregated_gaze_results import extract_results_gaze as agg_et_extr_results
from significance_testing.aggregate_significance import aggregate_signi_eeg, aggregate_signi_fmri
from significance_testing.aggregate_significance import aggregate_signi_gaze as aggregate_signi_et
from significance_testing.testing_helpers import bonferroni_correction, test_significance

from lib_nubia.prompt_toolkit_table import *
from lib_nubia.commands import messages

# Silence TF 2.0 deprecation warnings
from tensorflow.python.util import deprecation
deprecation._PRINT_DEPRECATION_WARNINGS = False

# Local imports

from .form_editor import ConfigEditor, config_editor
from .process import (filter_config,
                      process_and_write_results,
                      resolve_cog_emb,
                      _edit_config,
                      update_emb_config,
                      generate_random_df,
                      populate)
                      
from .utils import (tupleit,
                   _open_config,
                   _open_cog_config,
                   _check_cog_installed,
                   _backup_config,
                   _save_cog_config,
                   _save_config,
                   DisplayablePath,
                   download_file,
                   AbortException,
                   NothingToDoException,
                   chunked_list_concat_str,
                   field_concat,
                   chunks,
                   page_list,
                   configure_tf_devices)

from .report import generate_report

from .templates import MAIN_CONFIG_TEMPLATE

from .strings import EXAMPLE_COMMANDS

# Pretty warnings
import warnings

def custom_formatwarning(msg, *args, **kwargs):
    # ignore everything except the message
    return colored('Warning: {}\n'.format(msg), 'yellow')

warnings.formatwarning = custom_formatwarning

NUM_BERT_WORKERS = 1
COGNIVAL_SOURCES_URL = 'https://drive.google.com/uc?id=1ouonaByYn2cnDAWihnQ3cGmMT6bJ4NaP'

def run(configuration,
        config_dict,
        resources_path,
        embedding_registry,
        embeddings,
        modalities,
        cognitive_sources,
        cognitive_features,
        processes,
        n_gpus,
        max_gpus,
        visible_gpu_ids,
        baselines):

    cog_sources_conf = _open_cog_config(resources_path)
    if not _check_cog_installed(resources_path):
        cprint('CogniVal sources not installed! Aborted ...', 'red')
        return

    # Set GPU IDs

    # max_gpus overrides n_gpus if smaller
    max_gpus = max_gpus if (max_gpus and (not n_gpus or (n_gpus and (max_gpus < n_gpus)))) else n_gpus if n_gpus else None

    _gpu_ids_all = configure_tf_devices(visible_gpu_ids)
    
    if _gpu_ids_all:
        if max_gpus:
            gpu_ids = _gpu_ids_all[:max_gpus]
        else:
            gpu_ids = _gpu_ids_all
    else:
        gpu_ids = None

    # Obtain parametrization, filter configuration if so specified
    parametrization = filter_config(embedding_registry,
                                    cog_sources_conf,
                                    configuration,
                                    config_dict,
                                    embeddings,
                                    modalities,
                                    cognitive_sources,
                                    cognitive_features,
                                    baselines)
    
    if not parametrization:
        return

    config_dict, embeddings_list, emb_to_random_dict, cog_sources_list, cog_source_to_feature = parametrization

    # Run parallelized evaluation and obtain results dictionary.
    results_dict = run_parallel(config_dict,
                                emb_to_random_dict,
                                embeddings_list,
                                cog_sources_list,
                                cog_source_to_feature,
                                n_jobs=processes,
                                gpu_ids=gpu_ids)

    if not results_dict:
        cprint('\nAborted run ...', 'red')
        return
    
    # Process and write results (required for significance testing) and option files (required for aggregation) per modality
    for modality, results in results_dict.items():
        run_stats = {}
        for id_, (result_proper, result_random, rand_emb, options) in enumerate(zip(results["proper"],
                                                                                results["random"],
                                                                                results["rand_embeddings"],
                                                                                results["options"])):
            process_and_write_results(result_proper, result_random, rand_emb, config_dict, options, id_, run_stats)
        write_options(config_dict, modality, run_stats)

    # Increment run_id
    config_dict['run_id'] += 1
    return config_dict


def list_configs(resources_path):
    general_param_dicts = []
    
    # Load all configuration files (except reference) and adjust for tabulation
    for entry in os.scandir(resources_path):
        if entry.name.endswith('config.json'):
            with open(entry) as f:
                config = entry.name.rsplit('_', maxsplit=1)[0]
                if not config == 'reference': 
                    config_dict = json.load(f)
                    general_params = {k:v for k, v in config_dict.items() if k not in ['cogDataConfig', 'wordEmbConfig', 'randEmbConfig', 'randEmbSetToParts']}
                    general_params['config'] = config
                    general_param_dicts.append(general_params)

    # Build formatted table
    fgrid = tform.FancyGrid()
    cols = ['config'] + [k for k in general_param_dicts[0].keys() if not k == 'config']
    rows = [[colored(x['config'], attrs=['bold'], color='yellow')] + [v for k, v in x.items() if not k == 'config'] for x in general_param_dicts]
    rows.sort(key=lambda x: x[0])
    formatted_table = tform.generate_table(rows=rows,
                                            columns=cols,
                                            grid_style=fgrid)
    header_msg = colored('List of available configurations. Note that the reference configuration is read-only and not listed.', 'green')
    
    # Return list intended for displaying in pagination
    formatted_list = [header_msg, '\n\n', formatted_table]
    return formatted_list


def list_embeddings(debug, embedding_registry):
    if debug:
        emb_types = ['proper', 'random_static', 'random_multiseed']
    else:
        emb_types = ['proper', 'random_multiseed']

    relevant_keys = ('embeddings', 'dimensions', 'installed', 'truncate_first_line', 'chunked', 'random_embedding')
    titles = {'proper': 'Embeddings', 'random_multiseed': 'Baselines'}

    # Tabulate relevant information of embeddings and random baselines
    header_msg = colored('List of available and installed (custom) embeddings.', 'green')
    formatted_list = [header_msg, '\n\n']

    for emb_type in emb_types:
        title = colored(titles[emb_type], attrs=['bold'])
        param_dicts = []
        for key, value in copy.deepcopy(list(embedding_registry[emb_type].items())):
            value['embeddings'] = key
            param_dicts.append(value)
        
        fgrid = tform.FancyGrid()
        if param_dicts:
            cols = [x for x in relevant_keys if x in param_dicts[0]]
            rows = [[colored(x['embeddings'], attrs=['bold'], color='yellow')] + [x[k] for k in relevant_keys if k in x and not k == 'embeddings'] for x in param_dicts]
            rows.sort(key=lambda x: x[0])
            
            formatted_table = tform.generate_table(rows=rows,
                                                    columns=cols,
                                                    grid_style=fgrid)
            
            # Return list intended for displaying in pagination
            formatted_list.extend([title, '\n\n', formatted_table, '\n\n'])
    return formatted_list


def list_cognitive_sources(cog_config):
    # List cognitive sources along with features (where applicable)
    formatted_list = []

    for modality in cog_config['sources']:
        formatted_list.append(colored(modality.upper(), attrs=['bold']))
        formatted_list.append('\n')
        formatted_list.append(colored('Resource                           Features'))
        formatted_list.append('\n')
        for key, value in cog_config['sources'][modality].items():
            label = '{}_{}'.format(modality, key)
            formatted_list.append(colored(label, 'cyan')  + ' '*(35-len(label)))
            if isinstance(value["features"], str):
                formatted_list.append(colored(value["features"], 'green'))
                formatted_list.append('\n')
            else:
                formatted_list.append(colored(value["features"][0], 'green'))
                formatted_list.append('\n')
                for feature in value["features"][1:]:
                    formatted_list.append(colored(' '*35 + feature, 'green'))
                    formatted_list.append('\n')
            formatted_list.append('\n')
        formatted_list.append('\n')
    return formatted_list


def config_open(configuration, cognival_path, resources_path, edit, overwrite):    
    create = False

    # Determine if config needs to be created or overwritten
    if os.path.exists(resources_path / '{}_config.json'.format(configuration)):
        if overwrite:
            create = yes_no_dialog(title='Configuration {} already exists.'.format(configuration),
                        text='You have specified to overwrite the existing configuration. Are you sure?').run()
            if not create:
                cprint('Aborted ...', 'red')
                return
        else:
            create = False
    else:
        create = True

    # Open editor when creating (always) or opening (if edit=True)
    if create:
        config_dict = copy.deepcopy(MAIN_CONFIG_TEMPLATE)
        config_dict = _edit_config(resources_path, cognival_path, config_dict, configuration)
        if config_dict:
            _backup_config(configuration, resources_path)
            _save_config(config_dict, configuration, resources_path)
        else:
            return
    else:
        config_dict = _open_config(configuration, resources_path)
        if not config_dict:
            return
        if edit:
            config_dict = _edit_config(resources_path, cognival_path, config_dict, configuration)
            if config_dict:
                _backup_config(configuration, resources_path)
                _save_config(config_dict, configuration, resources_path)
    
    return configuration, config_dict


def config_show(configuration, config_dict, details, cognitive_source, hide_baselines):
    fgrid = tform.FancyGrid()
    table_strs = []
    
    # Tabulate general configuration properties
    if not cognitive_source:
        table_strs.append(colored("Note: Use 'config open {}' to edit the general properties of this configuration.".format(configuration), attrs=["bold"], color="green"))
        table_strs.append('\n')
        general = [(k, v) for k, v in config_dict.items() if not k in ['cogDataConfig', 'wordEmbConfig', 'randEmbConfig', 'randEmbSetToParts']]
        table_strs.append(colored('General properties', attrs=['bold', 'reverse'], color='green'))
        table_strs.append('\n')
        formatted_table = tform.generate_table(rows=[[x[1] for x in general]],
                                            columns=[x[0] for x in general],
                                            grid_style=fgrid,
                                            #row_tagger=row_stylist,
                                            transpose=False)
        table_strs.append(formatted_table)
        table_strs.append('\n')
        experiment_rows = [chunked_list_concat_str(list(config_dict['cogDataConfig']), 4)]
        experiment_rows += [chunked_list_concat_str(list(['{} ({})'.format(k, v['random_embedding'] if 'random_embedding' in v and v['random_embedding'] else 'None') \
                                                            for k, v in config_dict['wordEmbConfig'].items()]), 2)]
        experiment_rows = [experiment_rows]

        table_strs.append(colored('Experiment properties', attrs=['bold', 'reverse'], color='cyan'))
        table_strs.append('\n')
        formatted_table = tform.generate_table(rows=experiment_rows,
                                            columns=[colored('Cognitive sources', attrs=['bold']),
                                                    colored('Embeddings (Rand. emb.)', attrs=['bold'])],
                                            grid_style=fgrid,
                                            transpose=True)

        table_strs.append(formatted_table)
        table_strs.append('\n')
    
    # Show details of cognitive source(s) if single source specified or details==True (all sources)
    if cognitive_source:
        cognitive_sources = [cognitive_source]
    elif details:
        cognitive_sources = list(config_dict['cogDataConfig'].keys())
    else:
        cognitive_sources = []

    if cognitive_sources:
        table_strs.append(colored(fill("Note: Use 'config experiment cognitive-sources=[{}] single-edit=True' to edit the properties "
            "of the specified cognitive source(s) and associated embedding specifics.".format(', '.join(cognitive_sources)), 160)))
        table_strs.append('\n')

    for cognitive_source in cognitive_sources:
        table_strs.append(colored('{}\n'.format(cognitive_source), attrs=['bold', 'reverse'], color='yellow'))
        table_strs.append('\n')
        try:
            cog_source_config_dict = config_dict['cogDataConfig'][cognitive_source]
        except KeyError:
            cprint('Cognitive source {} not registered in configuration {}, aborted ...'.format(cognitive_source, configuration), 'red')
            return

        cog_source_properties = [(k, field_concat(v)) for k, v in cog_source_config_dict.items() if k != 'wordEmbSpecifics']
        table_strs.append(colored('Cognitive source properties ({})'.format(cognitive_source), attrs=['bold', 'reverse'], color='green'))
        table_strs.append('\n')
        formatted_table = tform.generate_table(rows=[[', '.join(x[1]) if isinstance(x[1], list) else x[1] for x in cog_source_properties]],
                                            columns=[x[0] for x in cog_source_properties],
                                            grid_style=fgrid,
                                            transpose=False)
        table_strs.append(formatted_table)
        table_strs.append('\n')
        table_strs.append(colored('Word embedding specifics', attrs=['bold', 'reverse'], color='cyan'))
        table_strs.append('\n')
        word_emb_specifics = cog_source_config_dict['wordEmbSpecifics']
        if hide_baselines:
            word_emb_specifics = {k:v for k, v in word_emb_specifics.items() if not k.startswith('random')}

        df = pd.DataFrame.from_dict(word_emb_specifics).transpose()
        df.reset_index(inplace=True)
        df = df.rename(columns={"index": "word_embedding",
                                "activations":"activations (l.)",
                                "batch_size": "batch_size (l.)",
                                "epochs": "epochs (l.)",
                                "layers": "layers (nested l.)",
                                "validation_split": "validation_split (l.)"})
        df = df.applymap(field_concat)
        formatted_table = tform.generate_table(df,
                                            grid_style=fgrid,
                                            transpose=False) 
        table_strs.append(formatted_table)
        table_strs.append('\n')
    return table_strs


def config_experiment(configuration,
                      main_conf_dict,
                      cog_config_dict,
                      embedding_registry,
                      resources_path,
                      baselines,
                      modalities,
                      cognitive_sources,
                      embeddings,
                      single_edit,
                      edit_cog_source_params,
                      scope):
    populate_conf = True
    backed_up = False

    if not main_conf_dict:
        return

    # Never add random baselines if not yet present
    if main_conf_dict['wordEmbConfig'] and baselines and not main_conf_dict['randEmbConfig']:
        cprint('Cannot add random baselines to existing configuration without random baselines! Aborting ...', 'red')
        return

    # Always add random baselines if already present
    if main_conf_dict['randEmbConfig']:
        baselines = True
    
    config_dicts = []
    cog_emb_pairs = []

    edit_all_embeddings = embeddings[0] == 'all' if embeddings else False

    # When configuration is empty, 'all' pertains to all embeddings and cognitive-source. If sources
    # and embeddings have already been added, 'all' means all contained in config.
    
    if scope is None:
        if main_conf_dict['wordEmbConfig']:
            scope = 'config'
        else:
            scope = 'all'
    else:
        if scope not in ('all', 'config'):
            cprint("Error: Invalid value for parameter 'scope'.", 'red')
            raise AbortException
    
    # Resolve passed cognitive sources and embeddings, considering specified scope
    try:
        cognitive_sources, embeddings = resolve_cog_emb(modalities,
                                                        cognitive_sources,
                                                        embeddings,
                                                        main_conf_dict,
                                                        cog_config_dict,
                                                        embedding_registry,
                                                        scope=scope)
    except AbortException:
        return

    # Only edit cognitive sources or combinations of cognitive sources and embeddings
    if not cognitive_sources:
        return

    cog_data_config_dict = main_conf_dict['cogDataConfig']
    
    for csource in cognitive_sources:
        if csource not in cog_data_config_dict:
            if populate_conf:
                cprint('Source {} not yet registered, creating ...'.format(csource), 'yellow')
                try:
                    populate(resources_path,
                             embedding_registry,
                             cog_config_dict,
                             configuration,
                             main_conf_dict,
                             rand_embeddings=False,
                             cognitive_sources=[csource],
                             embeddings=[],
                             quiet=True)
                except AbortException:
                    return
            else:
                continue

        # If populate is False, edit only existing configurations vs. populating missing ones
        if edit_all_embeddings and not populate_conf:
            embeddings = list(cog_data_config_dict[csource]["wordEmbSpecifics"].keys())

        if edit_cog_source_params or not embeddings:
            # Run config editor for cognitive source if parameter edit_cog_source_params is set
            config_patch = config_editor("cognitive",
                                            cog_data_config_dict[csource],
                                            [],
                                            [csource],
                                            singleton_params=['dataset', 'parent', 'type', 'modality'],
                                            skip_params=['wordEmbSpecifics'])

            # If patch dictionary is set, apply, backup existing and save new configuration
            if config_patch:
                cog_data_config_dict[csource].update(config_patch)
                if not backed_up:
                    _backup_config(configuration, resources_path)
                    backed_up = True
                _save_config(main_conf_dict, configuration, resources_path)
            else:
                return

        # Populate embeddings only if neither editing_cog_source_params nor editing embedding specifics of all embeddings
        if not edit_cog_source_params or not edit_all_embeddings:
            for emb in embeddings:
                do_populate = False
                if not emb in cog_data_config_dict[csource]["wordEmbSpecifics"]:
                    cprint('Experiment {} / {} not yet registered, populating from reference config if possible ...'.format(csource, emb), 'yellow')
                    do_populate = True
                if baselines and (emb not in main_conf_dict["wordEmbConfig"] or not main_conf_dict["wordEmbConfig"][emb]['random_embedding']):
                    cprint('Random baselines not yet associated with {}, adding ...'.format(emb), 'yellow')

                if do_populate:
                    try:
                        populate(resources_path,
                                 embedding_registry,
                                 cog_config_dict,
                                 configuration,
                                 main_conf_dict,
                                 rand_embeddings=baselines,
                                 cognitive_sources=[csource],
                                 embeddings=[emb],
                                 quiet=True)
                    except AbortException:
                        return

                emb_config = cog_data_config_dict[csource]["wordEmbSpecifics"][emb]
                config_dicts.append(emb_config)
                cog_emb_pairs.append((csource, emb))

    if config_dicts:
        emb_to_label = {}
        for emb in embeddings:
            if main_conf_dict['wordEmbConfig'][emb]['random_embedding']:
                emb_to_label[emb] = '{} (+ rand.)'.format(emb)
            else:
                emb_to_label[emb] = emb

        # Editing specifics of each embedding individually
        if single_edit:
            for idx, ((csource, emb), cdict) in enumerate(zip(cog_emb_pairs, config_dicts)):
                config_template = copy.deepcopy(config_dicts[idx])
                # Run editor for cognitive source/embedding experiments
                config_patch = config_editor("embedding_exp",
                                            config_template,
                                            [emb_to_label[emb]],
                                            cognitive_sources,
                                            singleton_params=['cv_split', 'validation_split'])
                if config_patch is None:
                    return
                else:
                    try:
                        update_emb_config(emb, csource, cdict, config_patch, baselines, main_conf_dict, embedding_registry)
                    except AbortException:
                        return
                    if not backed_up:
                        _backup_config(configuration, resources_path)
                        backed_up = True
                    _save_config(main_conf_dict, configuration, resources_path)
        # Editing embedding specifics of multiple embeddings at once
        else:
            config_template = copy.deepcopy(config_dicts[0])
            # Generate template for multi-editing
            if len(config_dicts) > 1:
                config_aggregated = collections.defaultdict(set)
                for key in config_template:
                    for cdict in config_dicts:
                        config_aggregated[key].add(tupleit(cdict[key]))
                
                for key, values in config_aggregated.items():
                    if len(values) > 1:
                        config_template[key] = '<multiple values>'
                    else:
                        config_template[key] = values.pop()
            
            # Run editor for cognitive source/embedding experiments
            config_patch = config_editor("embedding_exp",
                                        config_template,
                                        list(emb_to_label.values()),
                                        cognitive_sources,
                                        singleton_params=['cv_split', 'validation_split'])
            if config_patch is None:
                return
            else:
                for (csource, emb), cdict in zip(cog_emb_pairs, config_dicts):
                    try:
                        update_emb_config(emb, csource, cdict, config_patch, baselines, main_conf_dict, embedding_registry)
                    except AbortException:
                        return

            if not backed_up:
                _backup_config(configuration, resources_path)
                backed_up = True
            _save_config(main_conf_dict, configuration, resources_path)


def config_delete(configuration,
                  main_conf_dict,
                  cog_config_dict,
                  embedding_registry,
                  modalities,
                  cognitive_sources,
                  embeddings,
                  force=False):
    # Delete entire configuration
    if not cognitive_sources and not modalities and not embeddings:
        if force:
            delete_config = True
        else:
            delete_config = button_dialog(title='Deletion',
                                text='You have not specified cognitive sources and embeddings for removal. Do you wish to delete configuration "{}"?'.format(configuration),
                                buttons=[
                                        ('No', False),
                                        ('Yes', True),
                                        ]).run()
        if delete_config:
            os.remove(resources_path / '{}_config.json'.format(configuration))
            cprint('Deleting configuration "{}" ...'.format(configuration), 'yellow')
            return
        else:
            return
    
    # Delete embeddings from all sources
    elif not cognitive_sources and not modalities:
        if force:
            all_sources = True
        else:
            all_sources = button_dialog(title='Deletion',
                                text='You have not specified cognitive sources or modalities. Do you wish to remove the specified embeddings for all sources?',
                                buttons=[
                                        ('No', False),
                                        ('Yes', True),
                                        ]).run()
        if all_sources:
            cognitive_sources = ['all']
        else:
            return

    elif not embeddings:
        embeddings = []
    
    if not main_conf_dict:
        return
    
    try:
        cognitive_sources, embeddings = resolve_cog_emb(modalities,
                                                        cognitive_sources,
                                                        embeddings,
                                                        main_conf_dict,                                                            
                                                        cog_config_dict,
                                                        embedding_registry,
                                                        scope="config")
    except AbortException:
        return

    main_conf_dict['cogDataConfig']
    
    # Remove experiments
    if embeddings:
        cprint("Removing experiments ...", "magenta")
        for csource in cognitive_sources:            
            for emb in embeddings:
                if emb in main_conf_dict['cogDataConfig'][csource]["wordEmbSpecifics"]:
                    rand_emb = main_conf_dict["wordEmbConfig"][emb]["random_embedding"]

                    del main_conf_dict['cogDataConfig'][csource]["wordEmbSpecifics"][emb]

                    # Remove associated random embeddings if present
                    if rand_emb:
                        cprint ("Deleting {}/{} and associated random baselines set {}/{}...".format(csource, emb, csource, rand_emb), 'green')
                    else:
                        cprint ("Deleting {}/{} ...".format(csource, emb), 'green')

                    if rand_emb:
                        for rand_emb_part in main_conf_dict["randEmbSetToParts"][rand_emb]:
                            del main_conf_dict['cogDataConfig'][csource]["wordEmbSpecifics"][rand_emb_part]

                    # Delete embedding config and associated random embedding configs if not longer used by any cognitive source
                    remove_dangling_emb_random(emb, main_conf_dict)
                else:
                    cprint ("Combination {}/{} not found in configuration {}, skipping ...".format(csource, emb, configuration), 'yellow')
        
            # Remove cognitive source if empty
            if not main_conf_dict['cogDataConfig'][csource]["wordEmbSpecifics"]:
                cprint("Deleting now empty source {} ...".format(csource), 'yellow')
                del main_conf_dict['cogDataConfig'][csource]

    # Remove complete cognitive source along with embeddings
    else:
        cprint("Removing cognitive sources ...", "magenta")
        for csource in cognitive_sources:            
            if csource in main_conf_dict['cogDataConfig']:
                cprint ("Deleting {} ...".format(csource), 'green')
                del main_conf_dict['cogDataConfig'][csource]
                for emb in list(main_conf_dict["wordEmbConfig"]):
                    remove_dangling_emb_random(emb, main_conf_dict)
            else:
                cprint ("Cognitive source {} not found in configuration {}, skipping ...".format(csource, configuration), 'yellow')

    return main_conf_dict


def remove_dangling_emb_random(emb, main_conf_dict):
    # Delete embedding config and associated random embedding configs if not longer used by any cognitive source
    if not any(emb in cd_dict["wordEmbSpecifics"] for cd_dict in main_conf_dict['cogDataConfig'].values()):
        cprint("Embedding {} no longer used by any cognitive source, removing (and associated random baselines if applicable and unused)".format(emb), 'yellow')
        assoc_rand_emb = main_conf_dict["wordEmbConfig"][emb]["random_embedding"]
        if assoc_rand_emb:
            for rand_emb_part in main_conf_dict["randEmbSetToParts"][assoc_rand_emb]:
                if not any(rand_emb_part in cd_dict["wordEmbSpecifics"] for cd_dict in main_conf_dict['cogDataConfig'].values()):
                    del main_conf_dict["randEmbConfig"][rand_emb_part]
            del main_conf_dict["randEmbSetToParts"][assoc_rand_emb]
        del main_conf_dict["wordEmbConfig"][emb]
    return main_conf_dict


def significance(configuration,
                 config_dict,
                 run_id,
                 modalities,
                 alpha,
                 test,
                 quiet):
    out_dir = Path(config_dict["PATH"]) / config_dict["outputDir"]

    # Get mapping of previous run_id (current not yet executed)
    if not run_id:
        run_id = config_dict['run_id'] - 1
    elif run_id >= config_dict['run_id']:
        if not quiet:
            cprint('Run ID {} exceeds last run ID for which results were generated ({}), aborting ...'.format(run_id, config_dict['run_id'] - 1), 'red')
        return
    if not run_id:
        if not quiet:
            cprint('No experimental runs performed yet for configuration {}, aborting ...'.format(configuration), 'red')
        return

    if not os.path.exists(out_dir):
        if not quiet:
            cprint('Output path {} associated with configuration "{}" does not exist. Have you already performed experimental runs?'.format(out_dir, configuration), "red")
        return

    try:
        with open(out_dir / 'mapping_{}.json'.format(run_id)) as f:
            mapping_dict = json.load(f)
    except FileNotFoundError:
        if not quiet:
            cprint('No results for run_id {}, aborting ...'.format(run_id), 'red')
        return
    
    for modality in modalities:
        if not quiet:
            cprint('\n[{}]\n'.format(modality.upper()), attrs=['bold'], color='green')
        experiments_dir = out_dir / 'experiments'
        sig_test_res_dir = out_dir / 'sig_test_results' / modality / str(run_id)
        report_dir = out_dir / 'reports' / modality / str(run_id)
        
        # Erase previously generated report files and significance test files
        if os.path.exists(report_dir / '{}.json'.format(test)):
            os.remove(report_dir / '{}.json'.format(test))
        if os.path.exists(sig_test_res_dir):
            shutil.rmtree(sig_test_res_dir)
        
        os.makedirs(sig_test_res_dir, exist_ok=True)
        os.makedirs(report_dir, exist_ok=True)

        datasets = [k for (k, v) in config_dict["cogDataConfig"].items() if 'modality' in v and v['modality'] == modality]
        
        embeddings = list(config_dict["wordEmbConfig"])

        
        hypothesis_counter = collections.Counter()
        # Extract results for significance testing
        for ds in datasets:
            for feat in config_dict["cogDataConfig"][ds]["features"]:
                for embed in embeddings:
                    experiment = '{}_{}#-#{}'.format(ds, feat, embed)
                    try:
                        st_extract_results(run_id, modality, experiment, mapping_dict, experiments_dir, sig_test_res_dir)
                        hypothesis_counter[embed] += 1
                    except KeyError:
                        pass

        # Skip modality if no hypotheses found
        if not hypothesis_counter:
            if not quiet:
                cprint('No hypotheses, skipping ...', 'yellow')
            continue
        else:
            # Compute bonferroni-corrected alpha (per embedding)
            embedding_to_bonferroni = {}
            for embed, num_hyp in hypothesis_counter.items():
                embedding_to_bonferroni[embed] = bonferroni_correction(alpha, num_hyp)

        if not quiet:
            cprint('\n[Significance tests]:', attrs=['bold'])

        report = report_dir / '{}.json'.format(test)
        results = collections.defaultdict(dict)
        # For each hypothesis (i.e. non-baseline)
        for filename in sorted(os.listdir(sig_test_res_dir)):
            if not 'baseline' in filename:
                # Obtain feature and average MSE
                experiment = re.sub(r'embeddings_scores_(.*?).txt', r'\1', filename)
                embedding = mapping_dict[experiment]['embedding']
                
                with open(experiments_dir / mapping_dict[experiment]['proper'] / '{}.json'.format(embedding)) as f:
                    result_json = json.load(f)
                avg_mse = result_json['AVERAGE_MSE']
                feature = mapping_dict[experiment]['feature']
                bf_corr_alpha = embedding_to_bonferroni[embedding]

                # Perform significance testing
                model_file = sig_test_res_dir / filename
                baseline_file = sig_test_res_dir / 'baseline_{}'.format(filename.partition('_')[2])
                significant, pval, name = test_significance(baseline_file, model_file, bf_corr_alpha, test)
                
                # Store and display results
                results['hypotheses'][name] = {'p_value': pval,
                                                'alpha': alpha,
                                                'bonferroni_alpha': bf_corr_alpha,
                                                'significant': significant,
                                                'wordEmbedding': embedding,
                                                'feature': feature,
                                                'AVERAGE_MSE': avg_mse}

                results['hypotheses'][name]['feature'] = feature

                if significant:
                    out_str, color = ': significant (p = {:1.3e})'.format(pval), 'green'
                else:
                    out_str, color = ': not significant (p = {:1.3e})'.format(pval), 'red'
                
                out_str += ' / hypotheses: {} / α (initial/after bonferroni correction): {} / {}'.format(hypothesis_counter[embedding], alpha, bf_corr_alpha)

                if not quiet:
                    cprint('    - {}'.format(name), attrs=['bold'], color=color, end='')
                    cprint(out_str, color)

            json_str = json.dumps(dict(results), indent=4)
            yield json_str
            
            with open(report, 'w', encoding='utf-8') as fp:
                fp.write(json_str)
                

def aggregate(configuration,
              config_dict,
              run_id,
              modalities,
              test,
              quiet):
    # Get mapping of previous run_id (current not yet executed)
    if not run_id:
        run_id = config_dict['run_id'] - 1
    elif run_id >= config_dict['run_id']:
        if not quiet:
            cprint('Run ID {} exceeds last run ID for which results were generated ({}), aborting ...'.format(run_id, config_dict['run_id'] - 1), 'red')
        return
    if not run_id:
        if not quiet:
            cprint('No experimental runs performed yet for configuration {}, aborting ...'.format(configuration), 'red')
        return

    out_dir = Path(config_dict['PATH']) / config_dict['outputDir']

    if not os.path.exists(out_dir):
        if not quiet:
            cprint('Output path {} associated with configuration "{}" does not exist. Have you already performed experimental runs?'.format(out_dir, configuration), "red")
        return

    with open(out_dir / 'mapping_{}.json'.format(run_id)) as f:
        mapping_dict = json.load(f)

    report_dir = out_dir / 'reports'
    
    if not os.path.exists(out_dir):
        if not quiet:
            cprint('Output path {} associated with configuration "{}" does not exist. Have you already performed experimental runs?'.format(out_dir, configuration), "red")
        return

    extract_results = {'eeg': agg_eeg_extr_results,
                       'fmri': agg_fmri_extr_results,
                       'eye-tracking': agg_et_extr_results}

    aggregate_significance = {'eeg': aggregate_signi_eeg,
                              'fmri': aggregate_signi_fmri,
                              'eye-tracking': aggregate_signi_et}
    
    modality_to_experiments = collections.defaultdict(list)
    
    options_dicts = []
    
    # Retrieve options dict per modality
    for modality in modalities:
        try:
            with open(Path(out_dir) / 'experiments' / modality / 'options_{}.json'.format(run_id)) as f:
                options_dict = json.load(f)
                options_dicts.append(options_dict)
        except FileNotFoundError:
            if not quiet:
                cprint("No results for modality {}, skipping ...".format(modality), "yellow")
            options_dicts.append(None)

        for experiment, properties in mapping_dict.items():
            if properties['modality'] == modality:
                modality_to_experiments[modality].append(properties['embedding'])

    
    # Collect embedding - baseline (random embedding) pairs
    emb_bl_pairs = []

    for k, v in config_dict["wordEmbConfig"].items():
        if v['random_embedding']:
            emb_bl_pairs.append((k, v['random_embedding']))
        else:
            cprint('Embedding {} has no associated random baselines, no significance test possible, skipping ...'.format(k), 'yellow')

    try:
        embeddings, baselines = zip(*emb_bl_pairs)
    except ValueError:
        cprint('No embedding-baseline pairs, aborting ...', 'red')
        return
    
    # Extract results for aggregation and aggregate significance scores
    for modality, options_dict in zip(modalities, options_dicts):
        if not quiet:
            cprint('\n[{}]\n'.format(modality.upper()), attrs=['bold'], color='green')
    
        if not options_dict:
            continue

        results = extract_results[modality](options_dict)

        significance = aggregate_significance[modality](report_dir,
                                                        run_id,
                                                        test,
                                                        modality_to_experiments[modality])
        
        df_rows = []
        df_rows_cli = []

        # Tabulate aggregated scores for CLI display and JSON export
        for emb, base in zip(embeddings, baselines):
            try:
                avg_base = results[base]
                avg_emb = results[emb]
                df_rows_cli.append({'Word embedding': emb,
                                    'Ø MSE Baseline': avg_base,
                                    'Ø MSE Proper': avg_emb,
                                    'Significance': colored(significance[emb], 'yellow')})

                df_rows.append({'Word embedding':emb,
                                'Ø MSE Baseline':avg_base,
                                'Ø MSE Proper':avg_emb,
                                'Significance': significance[emb]})

            except KeyError:
                pass

        df_cli = pd.DataFrame(df_rows_cli)
        df_cli.columns = [colored(col, attrs=['bold']) for col in df_cli.columns]
        df = pd.DataFrame(df_rows)
        df.set_index('Word embedding', drop=True, inplace=True)
        df_json = df.to_json()

        yield df_json
        
        with open(report_dir / modality / str(run_id) / 'aggregated_scores.json', 'w') as f:
            f.write(df_json)
        
        if not quiet:
            print(tabulate.tabulate(df_cli, headers="keys", tablefmt="fancy_grid", showindex=False))


def update_vocabulary(cog_sources_path,
                      old_vocab):
    old_vocab = set(old_vocab)
    old_len = len(old_vocab)

    new_vocab = set()
    source_paths = [(Path(path) / source) for path, _, sources in os.walk(cog_sources_path) for source in sources \
                        if source.endswith('txt') and not source.startswith('.')]
    cprint("Updating CogniVal vocabulary from cognitive sources ...", "yellow")
    
    # Iterate over sources
    for source_path in tqdm(source_paths):
        df = pd.read_csv(source_path,
                            sep=" ",
                            quotechar=None,
                            quoting=csv.QUOTE_NONE,
                            doublequote=False,
                            keep_default_na=False)
        
        # Determine if any NaNs in word column, warn accordingly
        is_nan_series = df['word'].isnull()
        if is_nan_series.values.any():
            nan_indices = is_nan_series.index[is_nan_series == True] + 1
            nan_indices = nan_indices.tolist()
            cprint('Warning - NaNs in (rows: {}): {}'.format(', '.join(map(str, list(nan_indices))), source_path), 'yellow')
            
        # Fill NaNs and perform inplace set union with new vocabulary set
        df.fillna('', inplace=True)
        new_vocab |= set(df['word'])

    new_vocab_list = sorted([x for x in new_vocab if x])
    new_len = len(new_vocab_list)

    # Report changes in vocabulary size
    if new_len == old_len:
        cprint('Vocabulary size unchanged ({})'.format(old_len), 'magenta')
    else:
        if new_len > old_len:
            cprint('Vocabulary size increased (previous/new): {}/{}'.format(old_len, new_len), 'green')
        elif new_len < old_len:
            cprint('Vocabulary size decreased (previous/new): {}/{} (Caution: Vocabulary size has decreased!)'.format(old_len, new_len), 'yellow')

    # Display a diff (union the sets minus intersection)
    diff_list = ', '.join(sorted(list((old_vocab | new_vocab) - (old_vocab & new_vocab))))
    if diff_list:
        cprint('Diff: {}'.format(diff_list))
        
    return new_vocab_list


def import_cognitive_sources(cognival_path,
                             resources_path,
                             cog_config,
                             source):
    basepath = cognival_path / 'cognitive_sources'

    if source == 'cognival': 
        url = COGNIVAL_SOURCES_URL
    else:
        url = None

    if source == 'cognival':
        if not cog_config['cognival_installed']:
            fullpath = basepath / 'cognival_vectors.zip'
            cprint("Retrieving CogniVal cognitive sources ...", "yellow")
            gdown.cached_download(url, path=str(fullpath), quiet=False, postprocess=gdown.extractall)
            cognival_dir = basepath / 'cognival-vectors'
            subdirs = os.listdir(cognival_dir)
            for subdir in subdirs:
                shutil.move(str(cognival_dir / subdir), basepath)
            os.remove(basepath / 'cognival_vectors.zip')
            for path in ['__MACOSX', '.DS_Store', 'cognival-vectors']:
                try:
                    shutil.rmtree(basepath / path)
                except NotADirectoryError:
                    os.remove(basepath / path)
            cog_config['cognival_installed'] = True
            cognival_sources = set(cog_config['cognival_sources'])
            for modality in cog_config['sources'].values():
                for csource, source_props in modality.items():
                    if csource in cognival_sources:
                        source_props['installed'] = True
        else:
            cprint("CogniVal sources already present!", "green")
            return 
    else:
        if not cog_config['cognival_installed']:
            cprint('Please import CogniVal source before importing custom cognitive sources (run this command without argument).', 'yellow')
            return

        # Specify path
        message_dialog(title='Cognitive source registration',
                        text='Custom cognitive sources MUST conform to the CogniVal format (space-separated, columns word, feature\n'
                            'or dimension columns (named e[i])) and be put manually in the corresponding directory \n'
                            'after running this assistant:\n\n'
                            '{}/cognitive_sources/<modality>/\n\n'
                            'The specified name ({}) must match the corresponding text file! \n'
                            'Multi-hypothesis (multi-file) sources must currently be added manually to: \n\n'
                            '{}/cognitive_sources/resources/cognitive_sources.json'.format(str(cognival_path), source, str(cognival_path))).run()


        modality = radiolist_dialog(title='Cognitive source registration',
                                    text='Specify cognitive source modality:',
                                    values=[('eeg', 'EEG (Electroencephalography)'),
                                            ('eye-tracking', 'Eye-Tracking'),
                                            ('fmri', 'fMRI (Functional magnetic resonance imaging)'),
                                            ]).run()

        if modality is None:
            return

        dimensionality = input_dialog(title='Cognitive source registration',
                                text='Specify the dimensionality of the cognitive source. Leave empty if each dimension constitutes a separate \n'
                                        'feature. Multi-dimensional multi-feature sources are not supported.').run()
        
        if dimensionality is None:
            return
        
        if not dimensionality:
            dimensionality = 1

        dimensionality = int(dimensionality)

        if dimensionality == 1:
            features = input_dialog(title='Cognitive source registration',
                                    text='If the source has multiple features, specify below, separated by comma. Leave empty otherwise.').run()
        else:
            features = ''
        
        if features is None:
            return
        
        if not features:
            features = 'single'
        else:
            features = [x.strip() for x in features.split(',')]

        # Add config dictionary
        cog_config['sources'][modality][source] = {'file': '{}.txt'.format(source),
                                                    'features': features,
                                                    'dimensionality': dimensionality,
                                                    'hypothesis_per_participant': False,
                                                    'installed': True}
        # Add to index
        index = cog_config['index']
        index.append('{}_{}'.format(modality, source))
        cog_config['index'] = natsorted(list(set(index)))
    
        message_dialog(title='Cognitive source registration',
                        text='Please ensure that the file has the following path and name after import:\n\n'
                                '{}/cognitive_sources/{}/{}.txt\n\n'
                                'Afterwards, run the command "update-vocabulary" to update the evaluation vocabulary.'.format(str(cognival_path), modality, source)).run()
    
    cprint("Completed importing cognitive sources ({})".format(source), "green")

    # Display a tree of the cognitive-sources directory for reference
    paths = DisplayablePath.make_tree(basepath, max_len=10, max_depth=3)

    for path in paths:
        cprint(path.displayable(), 'cyan')
    return cog_config


def import_embeddings(x,
                      embedding_registry,
                      path2embeddings,
                      resources_path,
                      embeddings_path,                      
                      force=False,
                      log_only_success=False,
                      are_set=False,
                      associate_rand_emb=False,
                      debug=False):
    if not are_set:
        associate_rand_emb = yes_no_dialog(title='Random baseline generation',
                                            text='Do you wish to compare the embeddings with random baselines of identical dimensionality? \n').run()
    local = False                                   
    
    # Download all embeddings
    if x == 'all':
        for emb in embedding_registry['proper']:
            import_embeddings(emb,
                              embedding_registry,
                              path2embeddings,
                              resources_path,
                              embeddings_path,
                              are_set=True,
                              associate_rand_emb=associate_rand_emb)

        # Download random baselines
        if debug:
            for rand_emb in embedding_registry['random_static']:
                import_embeddings(rand_emb,
                                  embedding_registry,
                                  path2embeddings,
                                  resources_path,
                                  embeddings_path,
                                  rand_emb,
                                  log_only_success=True)
        return

    # Download all static random baselines (debug, not intended for productive use)
    elif x == 'all_random':
        if debug:
            for rand_emb in embedding_registry['random_static']:
                import_embeddings(rand_emb,
                                  embedding_registry,
                                  path2embeddings,
                                  resources_path,
                                  embeddings_path,
                                  rand_emb,
                                  log_only_success=True)
            folder = embedding_registry['random_static'][rand_emb]['path']
        else:
            cprint('Error: random baselines must be generated using "import random-baselines"', 'red')
            return

    # Download a set of static random baselines (debug, not intended for productive use)
    elif x.startswith('random'):
        if debug:
            emb_name = x
            url = embedding_registry['random_static'][x]['url']
            path = 'random_static'
            folder = embedding_registry['random_static'][emb_name]['path']
        else:
            cprint('Error: random baselines must be generated using "import random-baselines"', 'red')
            return

    # Download a set of default embeddings (pre-registered in the embeddings registry)
    elif x in embedding_registry['proper']:
        if x.startswith('bert'):
            cprint('Warning:', attrs=['bold', 'reverse'], color='red', end='')
            print(' ', end='')
            cprint('BERT conversion is extremely memory-intensive. 16GB of RAM or more (depending on the embedding size) highly recommended. Press Ctrl-C to abort.', attrs=['reverse'], color='yellow')
        emb_name = x
        url = embedding_registry['proper'][x]['url']
        # Always assume subdirectories to be part of the archive!
        path = embedding_registry['proper'][x]['path'].split('/')[0]
        folder = embedding_registry['proper'][emb_name]['path']
        emb_dim = embedding_registry['proper'][emb_name]['dimensions']

    # Download custom embedding via URL
    else:
        if os.path.exists(x):
            local = True
        elif not x.startswith('http') and x is not None:
            cprint("Specified value is neither a default embedding, valid URL or path of an existing file, aborting ...", "red")
            list_embeddings(debug, embedding_registry)
            return

        url = x
        
        emb_name = input_dialog(title='Embedding registration',
                            text='You have provided a custom embedding URL/file path ({}). Please make sure that\n'
                                    'all of the following criteria are met:\n\n'
                                    '- The passed value is either a local path or an URL representing a direct HTTP(S) link to the file or a Google Drive link. \n'
                                    '- The file is either a ZIP archive, gzipped file or usable as-is (uncompressed).\n\n'
                                    'Other modes of hosting and archival are currently NOT supported and will cause the import to fail.\n'
                                    'In those instances, please manually download and extract the files in the {} '
                                    'directory and \nregister them in {}/embedding_registry.json\n\n'
                                    'Please enter a short name for the embeddings:'.format(url, str(embeddings_path), str(resources_path)),
                            ).run()
        if emb_name is None:
            cprint("Aborting ...", "red")
            return
        
        elif not emb_name:
            emb_name = 'my_custom_embeddings'
            cprint('No name specified, using "my_custom_embeddings" ...', 'yellow')

        main_emb_file = input_dialog(title='Embedding registration',
                    text='Specify the main embedding file (file name only, without path). This information is usually available from the supplier.\n'
                            'If not available, you can leave this information empty and manually edit {}/embeddings2url.json\n'
                            'after the import.'.format(str(resources_path))).run()

        if main_emb_file is None:
            cprint("Aborting ...", "red")
            return
        
        if not main_emb_file:
            main_emb_file = url.rsplit('/', maxsplit=1)[-1].rsplit('.', maxsplit=1)[0]
            cprint('No main embedding file specified, inferring "{}" (only works for .gz compressed single files!)'.format(main_emb_file), 'yellow')

        path = input_dialog(title='Embedding registration',
                            text='Optionally specify the directory name for the embeddings. The path may specify more details. \n'
                                    'If no string is specified, the name of the main embedding file (without extension) is used instead.'.format(url)).run()


        if path == '':
            folder = path = main_emb_file.rsplit('.', maxsplit=1)[0]
        elif not path:
            cprint('Aborted.', 'red')
            return

        emb_dim = input_dialog(title='Embedding registration',
                    text='Please specify embedding dimensionality:').run()
        
        if not emb_dim:
            cprint('Aborted.', 'red')
            return
        
        try:
            emb_dim = int(emb_dim)
        except ValueError:
            cprint('Error: {} is not a valid embedding dimensionality, aborting ...'.format(emb_dim), 'red')
            return

        emb_binary = yes_no_dialog(title='Embedding registration',
                                    text='Is the embedding file binary? If "No" is chosen, the file \n'
                                    'will be treated as text (only-space separated formats supported).').run()

        emb_binary_format = None
        truncate_first_line = False
        if emb_binary:
            emb_binary_format = radiolist_dialog(title='Embedding registration',
                                            text='Choose the binary format (switch to buttons using <Tab>). Note that unlisted formats (e.g. ELMo) cannot be processed automatically.',
                                            values=[('word2vec', 'word2vec-compliant (e.g. fasttext. Requires gensim)')]).run()

            if not emb_binary_format:
                cprint('Aborted.', 'red')
                return
        else:
            truncate_first_line = yes_no_dialog(title='Embedding registration',
                                                text='Is the embedding prefixed by a header row or row specifying dimensionality?').run()

        chunk_embeddings = button_dialog(title='Embedding registration',
                                        text='Large embeddings can be memory-intensive. Do you wish to segment the embeddings into chunks?\n'
                                                'The original file will be retained.',
                                        buttons=[
                                                ('No', False),
                                                ('Yes', True),
                                                ]).run()

        chunk_number = 0
        if chunk_embeddings:
            chunk_number = input_dialog(title='Embedding registration',
                                            text='Please specify the number of chunks. If left empty, the value is set to 4.').run()
            try:
                if chunk_number:
                    chunk_number = int(chunk_number)
            except ValueError:
                cprint('Invalid value, aborting ...', 'red')
                return
            
            if not chunk_number:
                chunk_number = 4

        embedding_registry['proper'][emb_name] = {'url': url,
                                                'dimensions': emb_dim,
                                                'path': path,
                                                'embedding_file': main_emb_file if not emb_binary else '{}.txt'.format(main_emb_file.rsplit('.', maxsplit=1)[0]),
                                                'installed': False,
                                                'binary': emb_binary,
                                                'binary_format': emb_binary_format,
                                                'binary_file': main_emb_file if emb_binary else None,
                                                'truncate_first_line': True if emb_binary_format == 'word2vec' else truncate_first_line,
                                                'chunked': chunk_embeddings,
                                                'chunk_number': chunk_number,
                                                'chunked_file': main_emb_file.rsplit('.', maxsplit=1)[0] if chunk_embeddings else None,
                                                'chunk_ending': '.txt',
                                                'random_embedding': None}
        
        # Make mapping for current session (loaded from config upon next start)
        path2embeddings[folder] = [emb_name]

    # Check if embeddings already installed
    if x in embedding_registry['proper'] and embedding_registry['proper'][x]['installed'] and not force:
        if not log_only_success:
            cprint('Embedding {} already imported. Use "force" to override'.format(emb_name), 'yellow')
        return

    if url:
        # Get file name and paths
        fname = url.split('/')[-1]
        fpath = embeddings_path / fname
        fpath_extracted = embeddings_path / path

        try:
            shutil.rmtree(fpath_extracted)
        except FileNotFoundError:
            pass

        if local:
            cprint('Copying and importing:', 'yellow', end =' ') 
        else:
            cprint('Downloading and importing:', 'yellow', end =' ') 
        cprint('{}'.format(emb_name), 'yellow', attrs=['bold'])
        
        # Google Drive downloads
        if 'drive.google.com' in url:
            gdown.download(url, str(embeddings_path / 'gdrive_embeddings.dat'), quiet=False)
            try:
                with zipfile.ZipFile(embeddings_path / 'gdrive_embeddings.dat', 'r') as zip_ref:
                    zip_ref.extractall(fpath_extracted) 
            except zipfile.BadZipFile:
                # Assume gzipped txt (requires manually creating path and setting filename)
                os.mkdir(fpath_extracted)
                with gzip.open(embeddings_path / 'gdrive_embeddings.dat', 'rb') as f_in:
                    with open(fpath_extracted / '{}.txt'.format(path), 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            os.remove(embeddings_path / 'gdrive_embeddings.dat')
        
        # Normal HTTP downloads and local file moves
        else:
            os.makedirs(fpath_extracted)
            # TODO: Test this
            if local:
                shutil.copy(url, fpath)
            else:
                download_file(url, fpath)
            if fname.endswith('zip'):
                with zipfile.ZipFile(fpath, 'r') as zip_ref:
                    zip_ref.extractall(fpath_extracted)
                os.remove(fpath)
            elif fname.endswith('gz'):
                # Assume gzipped bin (requires manually setting filename)
                with gzip.open(fpath, 'rb') as f_in:
                    with open(fpath_extracted / '{}.bin'.format(path), 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(fpath)
            else:
                # Local file move
                shutil.move(fpath, fpath_extracted / fname)
    
    # Do nothing in case download and provision is handled by external library (e.g. allennlp/elmo)
    else:
        cprint('No URL specified, delegating embedding provision to external package ...', 'yellow')

    # Iterate over all embedding files (e.g. GloVe has multiple files requiring processing)
    for emb_name in path2embeddings[folder]:
        base_path = embeddings_path / embedding_registry['proper'][emb_name]['path']
        try:
            bin_file = Path(embedding_registry['proper'][emb_name]['binary_file'])
        except TypeError:
            bin_file = None
        emb_file = Path(embedding_registry['proper'][emb_name]['embedding_file'])
        try:
            bin_path = base_path / bin_file
        except TypeError:
            bin_path = None
        emb_path = base_path / emb_file
        emb_dim = embedding_registry['proper'][emb_name]['dimensions']
        
        # Convert from binary to text
        try:
            if embedding_registry['proper'][emb_name]['binary']:
                if embedding_registry['proper'][emb_name]['binary_format'] == 'word2vec':
                    cprint('Converting binary to txt format ...', 'yellow')
                    word2vec_bin_to_txt(base_path, bin_file, emb_file)
                    os.remove(bin_path)

                elif embedding_registry['proper'][emb_name]['binary_format'] == 'elmo':
                    elmo_to_text(resources_path / 'standard_vocab.txt',
                                emb_path,
                                layer='nocontext')

                elif embedding_registry['proper'][emb_name]['binary_format'] == 'bert':
                    bert_to_text(resources_path / 'standard_vocab.txt',
                                base_path,
                                emb_path,
                                NUM_BERT_WORKERS)
                else:
                    cprint("Unknown binary format, aborting ...", "red")
                    return
        except FileNotFoundError as e:
            cprint("Error: {}".format(str(e)), "red")
            return

        # Chunk embeddings if necessary
        if embedding_registry['proper'][emb_name]['chunked']:
            cprint('Chunking {} ...'.format(emb_name), 'yellow')
            chunk(base_path,
                    base_path,
                    emb_file,
                    embedding_registry['proper'][emb_name]['chunked_file'],
                    number_of_chunks=embedding_registry['proper'][emb_name]['chunk_number'],
                    truncate_first_line=embedding_registry['proper'][emb_name]["truncate_first_line"])
            embedding_registry['proper'][emb_name]["truncate_first_line"] = False

        cprint('Finished importing embedding "{}"'.format(emb_name), 'green')

        # Associate random baselines with embeddings if set by user
        if associate_rand_emb:                                                
            import_random_baselines(embedding_registry, resources_path, embeddings_path, emb_name)
    
    if emb_name.startswith('random'):
        embedding_registry['random_static'][emb_name]['installed'] = True
    else:
        for emb_name in path2embeddings[folder]:
            embedding_registry['proper'][emb_name]['installed'] = True
    return embedding_registry


def import_random_baselines(embedding_registry,
                            resources_path,
                            embeddings_path,
                            embeddings,
                            num_baselines=10,
                            seed_func='exp_e_floored',
                            force=False):
    if embeddings.startswith('random'):
        cprint('✗ Reference embedding must be non-random! Aborting ...'. format(embeddings), 'red')
        return
    
    emb_properties = embedding_registry['proper'].get(embeddings, None)
    if not emb_properties:
        cprint('✗ No specifications set for embeddings {}! Import custom embeddings or register them manually. Aborting ...'. format(embeddings), 'red')
        return

    emb_dim = emb_properties['dimensions']

    # Get dimensions of existing random baselines
    available_dims = set()
    for _, parameters in embedding_registry['random_multiseed'].items():
        if parameters['installed']:
            available_dims.add(parameters['dimensions'])

    # Obtain seed values from non-linear function
    if seed_func == 'exp_e_floored':
        seeds = [int(np.floor((k+1)**np.e)) for k in range(num_baselines)]
    else:
        raise NotImplementedError('Only floor(x**e) (exp_e_floored) currently implemented')
    
    rand_emb_name = 'random-{}-{}'.format(emb_dim, len(seeds))
    
    # Generate random baselines if not already present
    if emb_dim not in available_dims or force:
        if emb_dim in available_dims:
            cprint('Replacing existing random baselines of dimensionality {}, generating ...'.format(emb_dim), 'yellow')
        else:
            cprint('No pre-existing random baselines of dimensionality {}, generating ...'.format(emb_dim), 'yellow')

        with open(resources_path / 'standard_vocab.txt') as f:
            vocabulary = f.read().split('\n')
        cprint('Generating {}-dim. random baselines using standard CogniVal vocabulary ({} tokens)...'.format(emb_dim, len(vocabulary)), 'yellow')

        # Generate random baselines
        rand_emb_keys = ['{}_{}_{}'.format(rand_emb_name, idx+1, seed) for idx, seed in enumerate(seeds)]
        rand_emb_path = Path('random_multiseed') / '{}_dim'.format(emb_dim) / '{}_seeds'.format(len(seeds))
        fullpath = embeddings_path / rand_emb_path
        try:
            os.makedirs(fullpath)
        except FileExistsError:
            pass

        dfs = Parallel((os.cpu_count() - 1))(delayed(generate_random_df)(seed, vocabulary, emb_dim) for seed in tqdm(seeds))
        for df, emb_file in zip(dfs, rand_emb_keys):
            df.to_csv(fullpath / '{}.txt'.format(emb_file), sep=" ", encoding="utf-8", header=False, index=False)
                
        # Register random baselines
        embedding_registry['random_multiseed'][rand_emb_name] = {'url': 'locally generated',
                                                                    'dimensions': emb_dim,
                                                                    'path':str(rand_emb_path),
                                                                    'embedding_parts':{},
                                                                    'installed': True,
                                                                    'chunked': False,
                                                                    'associated_with':[embeddings]}
        for rand_emb_key in rand_emb_keys:
            embedding_registry['random_multiseed'][rand_emb_name]['embedding_parts'][rand_emb_key] = '{}.txt'.format(rand_emb_key)
        
        cprint('✓ Generated random baselines (Naming scheme: random-<dimensionality>-<no. seeds>-<#seed>-<seed_value>)', 'green')
    # Associate existing baseline otherwise, unless already associated
    else:
        try:
            if not embeddings in embedding_registry['random_multiseed'][rand_emb_name]['associated_with']:
                cprint('Random baselines of dimensionality {} already present, associating ...'.format(emb_dim), 'green')
                embedding_registry['random_multiseed'][rand_emb_name]['associated_with'].append(embeddings)
            else:
                cprint('Random baselines of dimensionality {} already present and associated.'.format(emb_dim), 'green')
                return
        except KeyError:
            cprint('Random baselines of dimensionality {} present, but different fold count (no_emb). Use force to regenerate.'.format(emb_dim), 'yellow')
            return
    
    emb_properties['random_embedding'] = rand_emb_name
    return embedding_registry
