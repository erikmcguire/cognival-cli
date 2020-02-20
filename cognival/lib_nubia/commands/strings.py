EDITOR_TITLES = {"properties": "CogniVal properties",
                 "main": "General Configuration",
                 "cognitive": "Cognitive Source Configuration",
                 "embedding_exp": "Embedding Experiment Configuration",
                 "embedding_conf": "Embedding Parameter Configuration"}

EDITOR_DESCRIPTIONS = { "properties": {"cognival_path": "Path for storing user data (configurations, embeddings, cognitive sources and results)."},
                        "main": {"PATH": "Main working directory. Defaults to $HOME/.cognival",
                                "n_proc": "Number of (parent) processes to spawn for parallel fitting and evaluation. Defaults to (1 - number of available logical CPU cores). "
                                          "Note: A single process can allocate cycles on more than CPU core! Reduce this value if encountering issues (e.g. due to ulimit settings).",
                                "folds": "Number of folds evaluated in n-Fold cross-validation (CV)",
                                "outputDir": "Output directory as subdirectory of 'results' (automatically prefixed if missing)",
                                "seed": "Random seed for train-test sampling",
                                "run_id": "Configuration run_id. Normally set to 1 when creating a new configuration file"
                                },
                       "cognitive": {"dataset": "Name of the cognitive data set. See resources/cognitive_sources.json for a list of all available source",
                                     "modality": "Cognitive source modality (eeg, eye-tracking or fmri)",
                                     "features": "Comma-separated list of features to be evaluated. Must be set to ALL_DIM for all sources with only one feature, represented by all dimensions.",
                                     "type": "'single_output' for most multi-feature resources (typically eye-tracking) and 'multivariate_output' for most single-feature resources (typicall eeg, fmri)"
                                    },
                       "embedding_exp": {"activations": "Activation function(s) used in the neural regression model. Comma-separated list for multiple values.",
                                         "batch_size": "Batch size used during training. Comma-separated list for multiple values.",
                                         "cv_split": "Number of cross-validation (CV) splits",
                                         "epochs": "Number of training epochs. Comma-separated list for multiple values.",
                                         "layers": "List of lists of layer specifications. Each row corresponds to possible layer sizes for a layer (comma-separated). Layers are separated by newlines.",
                                         "validation_split": "Ratio training data used as validation data during training"
                                        },
                        "embedding_conf":{"chunk_number": "Number of embedding chunks. Ignored if chunked == 0.",
                                         "chunked": "Whether the embedding is chunked (1) or not (0).",
                                         "chunked_file": "Prefix/root of chunk files. Ignored if chunked == 0.",
                                         "ending": "File suffix of chunk files. Ignored if chunked == 0.",
                                         "path": "Path of embedding (chunks)",
                                         "truncate_first_line": "Whether to remove the first line upon loading"
                                         }
                        }

EXAMPLE_COMMANDS = {'config':{'open':[{'example':'config open myconfig',
                                       'description':'Open existing or create configuration myconfig and open editor.'},
                                       {'example':'configuration=myconfig overwrite=True',
                                       'description':'Overwrite existing or create new configuration myconfig and open editor.'}],
                              'show':[{'example':'demo',
                                       'description':'Show overview information of configuration myconfig (general properties, associated cognitive sources and embeddings).'},
                                       {'example':' configuration=demo details=True',
                                       'description':'Likewise, but also show experiment details for each cognitive source (cog. source - embeddings combinations)'},
                                       {'example':' configuration=demo cognitive-source=eeg_zuco',
                                       'description':'Show experiment details for a particular cognitive source (cog. source - embeddings combinations)'}],
                              'experiment':[{'example':'configuration=demo cognitive-sources=[eye-tracking_zuco] embeddings=[glove.6B.50] rand-embeddings=True',
                                             'description':'Edit existing experiment specifics or populate from reference configuration for experiment eye-tracking_zuco-glove.6B.50. If populate, also add random embeddings.'},
                                            {'example':'configuration=demo cognitive-sources=[eeg_zuco, eeg_ucl] embeddings=[glove.6B.50, glove.6B.100] rand-embeddings=True single-edit=True',
                                             'description':'Likewise, but add all combinations of two cognitive sources and embeddings and open a separate editor for each embedding (if single-edit=False: Edit all experiment specifics at once, useful if there are no changes, e.g. only populating from reference config)'},
                                             {'example':'configuration=demo modalities=[eeg] embeddings=[glove.6B.50] rand-embeddings=True',
                                             'description':'Add all combinations of all cognitive-sources of the modality EEG and a particular embedding (as well as random embedding, if populating).'},
                                             {'example':'configuration=demo cognitive-sources=[all] embeddings=[glove.6B.50] rand-embeddings=True',
                                             'description':'Add all combinations of all installed cognitive-sources and a particular embedding (as well as random embeddings, if populating).'},
                                             {'example':'configuration=demo cognitive-sources=[eeg_zuco] embeddings=[all] rand-embeddings=True',
                                             'description':'Add all combinations of a particular cognitive-source and all installed embeddings (as well as random embeddings, if populating).'},
                                             {'example':'configuration=demo cognitive-sources=[eeg_zuco] edit-cog-source-params=True',
                                             'description':'Edit parameters of cognitive source. Mainly useful to add or remove features from multi-feature sources. Note: Embeddings are ignored if set to [all] or not explicitely given!'}
                              ],
                              'delete':[{'example':'configuration=demo cognitive-sources=[eeg_zuco] embeddings=[glove.6B.50]',
                                         'description':'Remove an embedding from a particular cognitive sources of a configuration (second variant prompts confirmation).'},
                                        {'example':'configuration=demo cognitive-sources=[all] embeddings=[glove.6B.50][nl]'
                                                   'configuration=demo embeddings=[glove.6B.50]',
                                         'description':'Remove an embedding from all cognitive sources of a configuration (second variant prompts confirmation).'},
                                         {'example':'configuration=foo cognitive-sources=[eeg_zuco]',
                                         'description':'Remove a cognitive source from a configuration.'},
                                         {'example':'configuration=demo',
                                         'description':'Delete a configuration (prompts confirmation).'}],},
                    'install':{'cognitive-sources':[{'example':'-',
                                                     'description':'Install CogniVal sources (required).'},
                                                    {'example':'source=mysource',
                                                     'description':'Install a custom cognitive source (requires manual file copying).'}],
                              'embeddings':[{'example':'glove.6B.50',
                                             'description':'Install a set of default embeddings (in this case, all GloVe embeddings are installed, as they are bundled in archive)'},
                                           {'example':'x=glove.6B.50 force=True',
                                             'description':'Reinstall a set of default embeddings.'},
                                           {'example':'/home/username/custom_embeddings.zip',
                                            'description':'Install a set of custom embeddings from a local path.'},
                                           {'example':'https://github.com/eyaler/word2vec-slim/raw/master/GoogleNews-vectors-negative300-SLIM.bin.gz',
                                            'description':'Install a set of custom embeddings from an URL (direct link or Google Drive).'}],
                              'random-embeddings':[{'example':'glove.6B.50',
                                                    'description':'Generate random embeddings and/or associate with glove.6B.50'},
                                                   {'example':'embeddings=glove.6B.50 no-embeddings=5 force=True',
                                                    'description':'Regenerate random embeddings with 5 (instead of 10) subsets of embeddings and/or associate with glove.6B.50'}]},
                    'run':[{'example':'demo',
                            'description':'Run all experiments specified in a configuration, including random embeddings (where applicable).'},
                            {'example':'configuration=demo embeddings=[glove.6B.50] cognitive-sources=[eeg_zuco, eye-tracking_ucl] cognitive-features=["ALL_DIM", "RTfirstfix;RTfirstpass"]',
                            'description':'Run a subset of experiments specified in a configuration, with a subset of features for an eye-tracking source with multiple features.'},
                            {'example':'configuration=demo processes=5 random-baseline=False',
                            'description':'Run all experiments specified in a configuration without random embeddings and override number of processes specified in configuration.'},
                            {'example':'configuration=demo n-gpus=2',
                            'description':'Run all experiments specified in a configuration and set number of GPUs to use to 2 (note that if the --max-gpus command-line parameter is set/not equal 0, this value must be equal or lower, otherwise it is ignored.)'},],
                    'significance':[{'example':'demo',
                                     'description':'Compute significance for experiments of all modalities for the most recent run_id of a configuration at an alpha of 0.01. Requires that experiments have been executed with random embeddings.'},
                                    {'example':'demo alpha=0.05',
                                     'description':'Likewise, but with a modified alpha.'},
                                    {'example':'configuration=demo run_id=1 modalities=[eye-tracking]',
                                     'description':'Compute significance for experiments of modality eye-tracking for run_id 1 of a configuration.'}],
                    'aggregate':[{'example':'configuration=demo',
                                'description':'Aggregate all modalities of the most recent experimental run of the configuration demo'},
                                {'example':'configuration=demo run_id=1',
                                'description':'Likewise, but for run_id 1 of the configuration.'},
                                {'example':'configuration=demo modality=[eye-tracking]',
                                'description':'Likewise, but for modality eye-tracking only.'}],
                   'report':[{'example':'report configuration=demo open-html=True',
                              'description':'Note: This command wraps significance and aggregate, thus sharing arguments of these commands.\n'
                                            'Compute significances, perform aggregation (all modalities, most recent run_id, default parameters), generates and opens HTML report (requires web browser and X11 forwarding when using SSH).'},
                             {'example':'report configuration=demo html=False pdf=True open-pdf=True',
                              'description':'Likewise, but generate and open a PDF export instead (latter requires a PDF viewer and X11 forwarding when using SSH).'}]
                }