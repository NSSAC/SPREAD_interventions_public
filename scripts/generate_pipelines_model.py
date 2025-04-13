DESC='''Code to generate simulation pipeline instances given a "master"
config file with model parameters and their values.

Unlike generate_pipelines.py, this supports input values for alpha_S, alpha_LD, budget, and intervention delay.
Uniquely-named config files will be placed in placed in the configs folder, depending
on input values and number of batches, and a script file (./run.sh by default)
will be filled with the commands necessary to run the pipelines in SLURM.
'''

import json
import argparse
import itertools, math
from create_batch_configs import generateConfigs 
# config file generator; make sure create_batch_configs.py is in the same folder

HOMEPATH="../scripts"
WORKPATH="../work"
# Where files are saved, relative to WORKPATH:
CONFIG_PATH = "configs"
# These are used for SLURM, not for generating:
DAG_PATH = "dags"
SUMMARY_PATH = "summaries"
INTERVENTION_PATH = "interventions"
SIM_SUMMARY_PATH="sim_summaries"
# May be changed if necessary

MEM_VALUES = {
    'BD': math.log(52000),
    'ID': math.log(3400),
    'PH': math.log(1200),
    'TH': math.log(1800),
    'VN': math.log(27000)
} # a set of constants used to estimate the number of threads to allow interventions to use

def generate_pipeline_instances_model(master_config, slurmFile, configs_only=False, simulator_only=False, shell=False, jobArray=True):
    '''Main function, handling pipeline instances. Can choose to only generate configs, or omit interventions'''

    batch_configs = []
    for alpha_S,alpha_LD in itertools.product(master_config['parameters']['model_parameters']['alpha_S'],master_config['parameters']['model_parameters']['alpha_LD']):
        l = generateConfigs(master_config, alpha_S=alpha_S, alpha_LD=alpha_LD)
        batch_configs.extend(l)
    
    budgets, ints = parse_budget_int(master_config)
    for c in batch_configs:
        # create a new .json
        jsonpath = f"{WORKPATH}/{CONFIG_PATH}/{c['simulation_output_prefix']}.json"
        with open(jsonpath, 'w') as file:
            json.dump(c, file)
        print(jsonpath)
    
    # done with creating jsons. write to slurm if needed
    if configs_only:
        return True
    
    if jobArray and master_config['batches']>1:
        job_array_write_model(master_config, slurmFile, simulator_only)
    else: 
        job_single_write_model(master_config, slurmFile, simulator_only)

def job_array_write_model(master_config, slurmFile, simulator_only=False):
    '''
    Function to utilize SLURM's job array functionality to submit jobs.
    This function is run if multiple batches are to be run per input combination
    '''
    batches = master_config['batches']
    alpha_S = master_config['parameters']['model_parameters']['alpha_S']
    alpha_LD = master_config['parameters']['model_parameters']['alpha_LD']
    net_ind = (master_config['input']['network']).rindex('/')+1
    network_name = (master_config['input']['network'])[net_ind:]
    s = master_config['simulations']
    for alpha_S,alpha_LD in itertools.product(alpha_S,alpha_LD):
        prefix=f"{master_config['prefix']}as{alpha_S}_ald{alpha_LD}" # no need to add _%a here
        slurmFile.write(f'''\
mkdir -p {WORKPATH}/logs/{prefix}_{{0..{batches-1}}}
jid=$(sbatch \
-o {WORKPATH}/logs/{prefix}_%a/as{alpha_S}_ald{alpha_LD}_%a_log.txt \
--array=0-{batches-1} \
--export=ALL,prefix={prefix} \
./pipe_sim.sbatch | awk '{{print $NF}}' )
echo "Submitted batch job $jid"; ./qreg_batch \n''') # default memory usage
        # interventions part
        if simulator_only:
            continue
        for b,i in itertools.product(master_config['budget'], master_config['intervention_time']):
            #c = 1.5 if int(b) <= 3 else 1
            cpu_limit = math.ceil(MEM_VALUES[network_name] * int(s) * int(i) / 815) # rough estimate
            #cpu_limit = math.ceil(mem_limit/8)
            cpu_limit = min(max(cpu_limit,1),20)
            print(network_name,alpha_S,alpha_LD,i,b,cpu_limit)
            #print(mem_limit)
            slurmFile.write(f'''\
sbatch -o {WORKPATH}/logs/{prefix}_%a/I{i}B{b}_log.txt \
--array=0-{batches-1} \
--dependency=aftercorr:$jid \
--ntasks={cpu_limit} --mem={cpu_limit*8}G \
--export=ALL,prefix={prefix},\
hierarchy={master_config['input']['hierarchy']},budget={b},\
int_time={i} \
./pipe_int.sbatch; \
./qreg_batch \n''')           

def job_single_write_model(master_config, slurmFile, simulator_only=False):
    '''Function to be run if only one batch is needed per alpha_S/alpha_LD combination.
    In this case, each combination is submitted one job at a time.'''
    alpha_S = master_config['parameters']['model_parameters']['alpha_S']
    alpha_LD = master_config['parameters']['model_parameters']['alpha_LD']
    net_ind = (master_config['input']['network']).rindex('/')+1
    network_name = (master_config['input']['network'])[net_ind:]
    s = master_config['simulations']
    for alpha_S,alpha_LD in itertools.product(alpha_S,alpha_LD):
        prefix=f"{master_config['prefix']}as{alpha_S}_ald{alpha_LD}"
        logpath=f"{WORKPATH}/logs/{prefix}"
        # if not os.path.isdir(f"{WORKPATH}/logs/{prefix}/"):
        #     os.mkdir(f"{WORKPATH}/logs/{prefix}/")
        slurmFile.write(f'''\
mkdir -p {logpath}
jid=$(sbatch \
-o {logpath}/as{alpha_S}_ald{alpha_LD}_log.txt \
--export=ALL,prefix={prefix},single=1 \
./pipe_sim.sbatch | awk '{{print $NF}}' )
echo "Submitted batch job $jid"; ./qreg_single \n''')
        # interventions part
        if simulator_only:
            continue
        for b,i in itertools.product(master_config['budget'], master_config['intervention_time']):
            cpu_limit = math.ceil(MEM_VALUES[network_name] * int(s) * int(i) / 815) 
            cpu_limit = min(max(cpu_limit,1),20)
            # rough estimate of how many threads for optimizer to utilize, from 1 to 20
            print(network_name,alpha_S,alpha_LD,i,b,cpu_limit)
            slurmFile.write(f'''\
sbatch -o {logpath}/I{i}B{b}_log.txt \
--dependency=afterok:$jid \
--ntasks={cpu_limit} --mem={cpu_limit*8}G \
--export=ALL,prefix={prefix},single=1,\
hierarchy={master_config['input']['hierarchy']},budget={b},\
int_time={i} \
./pipe_int.sbatch; \
./qreg_single \n''')  


def parse_budget_int(master_config):
    '''Helper function to parse budget and intervention values.'''
    budgets = master_config['budget']
    if type(budgets) == list:
        out_b = " ".join([str(b) for b in budgets])
    else:
        out_b = str(budgets)
    ints = master_config['intervention_time']
    if type(ints) == list:
        out_i = " ".join([str(i)for i in ints])
    else:
        out_i = str(ints)
    return out_b, out_i
    

if __name__=="__main__":    
    # parser
    parser=argparse.ArgumentParser(description=DESC, 
            formatter_class=argparse.RawTextHelpFormatter)

    # feature vector arguments
    parser.add_argument("config_file",help="Config file", nargs='+')
    parser.add_argument("-r", "--run_file", 
            default="run.sh",
            help="It contains slurm invocation of training script for each instance.")
    
    # parser.add_argument("--shell", action="store_true",help="Plain shell command, no sbatch.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c","--configs_only", action="store_true",
                       help="Generate config files without preparing slurm scripts")
    group.add_argument("-s","--simulator_only", action="store_true",
                       help="Generate slurm scripts, but without running interventions")
    group.add_argument("-n","--no_job_array", action="store_true",
                       help="sbatch jobs one at a time, instead of as a job array")
    # parser.add_argument("-d", "--debug", action="store_true")
    # parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()
    
    slurmFile = open(args.run_file, 'w')
    slurmFile.write('#!/bin/bash\n')
    slurmFile.write('start=$SECONDS\n')
    for conf in args.config_file:
        #os.chdir(HOMEPATH)
        with open(conf, "r") as file:
            print(conf)
            master_config = json.load(file)
            generate_pipeline_instances_model(master_config, slurmFile,
                configs_only=args.configs_only,
                simulator_only=args.simulator_only,
                shell=False, # UNIMPLEMENTED
                jobArray=(not args.no_job_array) )
                # will not run job array if only one batch
            
    slurmFile.write('echo "Total time" $(($SECONDS-$start))\n')
    slurmFile.close()
