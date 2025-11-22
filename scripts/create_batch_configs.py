DESC='''
Code to split a "master" config file into a series of smaller config files, with either
different numbers of simulations or different alpha_S/alpha_LD values, to be fed into
the simulation pipeline one by one (in parallel)

Intended to be called by generate_pipelines.py and generate_pipelines_model.py
'''

import sys
import json
import random
from copy import deepcopy

CONFIG_PATH = "../work/configs" # where config files are outputted, by default

def generateConfigs(config, sims=None, alpha_S=None, alpha_LD=None, intervention=None):
    '''
    Given Dict representing config json file, returns a list of config Dicts, one per batch.
    
    Takes in either a number of simulations (for stability analysis)
    or values for alpha_s/alpha_LD (for pathway analysis).
    Parameters can be specified either through function arguments or fields in the config json
    '''
    num_batches = config['batches']
    out_configs = []
    
    # generate random seed
    try:
        random.seed(config['random_seed'])
    except KeyError:
        print('No seed for random number generator given.')
    try:
        prefix = config['prefix'] # in case it is an empty string
    except KeyError:
        prefix = ""
    
    # sims will never be a list. Either it is an individual value provided by 
    # generate_pipelines, or config['simulations'] is already a single value
    if sims is None:
        s = config['simulations'] # should NOT be a list in this case
    else:
        s = sims
    aS = config['parameters']['model_parameters']['alpha_S'] if alpha_S is None else alpha_S
    aLD = config['parameters']['model_parameters']['alpha_LD'] if alpha_LD is None else alpha_LD
    # none of these should be a list, either
    
    # change prefix based on what analysis is being conducted
    if sims is None and alpha_S is not None:
        prefix += ("as"+str(alpha_S) + "_" + "ald" + str(alpha_LD))
    else:
        prefix += ("S"+str(s))
        # by default, uses number of simulations
    
    for i in range(num_batches):
        # prefix_index = "_"+str(i) if num_batches > 1 else ""
        prefix_index = "_"+str(i)
        batch_config = {
            "network_specific_input" : deepcopy(config['input']),
            "random_seed": random.randrange(2**31),
            "model_parameters" : deepcopy(config['parameters']['model_parameters']),
            "simulation_parameters" : deepcopy(config['parameters']['simulation_parameters']),
            "simulation_output_prefix": prefix+prefix_index
        }
        # deepcopy is required to modify certain fields without changing original config
        batch_config['simulation_parameters']['number_of_simulations'] = s
        batch_config['model_parameters']['alpha_S'] = aS # overwrites if needed
        batch_config['model_parameters']['alpha_LD'] = aLD

        if intervention is not None:
            batch_config['network_specific_input']['interventions'] = intervention # interventions with an s

        out_configs.append(batch_config)    
    return out_configs


if __name__=="__main__":
    # Optional input arguments if this file is directly (filepaths)
    with open(sys.argv[1], "r") as file:
        print(sys.argv[1])
        master_config = json.load(file)
    
    simulations = master_config['simulations']
    if type(simulations) == list:
        batch_configs = []
        for s in simulations:
            l = generateConfigs(master_config, sims=s)
            batch_configs.extend(l)
    else:
        batch_configs = generateConfigs(master_config)
    if len(sys.argv)>2:
        CONFIG_PATH = sys.argv[2] # second element for path
    for c in batch_configs:
        path = f"{CONFIG_PATH}/{c['simulation_output_prefix']}.json"
        with open(path, 'w') as file:
            json.dump(c, file)
        print(path)
