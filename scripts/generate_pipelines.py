DESC='''Code to generate simulation pipeline instances given a "master"
config file with model parameters and their values.

Multiple input values are supported for # of simulations, budget, and intervention delay.
Uniquely-named config files will be placed in placed in the configs folder, depending
on # of simulations and number of batches, and a script file (./run.sh by default)
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
# May be changed if necessary

MEM_VALUES = {
    'BD': math.log(52000),
    'ID': math.log(3400),
    'PH': math.log(1200),
    'TH': math.log(1800),
    'VN': math.log(27000)
} # a set of constants used to estimate the number of threads to allow interventions to use

def generate_pipeline_instances(master_config, slurmFile, configs_only=False, simulator_only=False, shell=False, jobArray=True):
    '''Main function, handling pipeline instances. Can choose to only generate configs, or omit interventions'''
    simulations = master_config['simulations']
    if type(simulations) == list:
        batch_configs = []
        for s in simulations:
            l = generateConfigs(master_config, sims=s) # obtain a list of config files from create_batch_configs.py
            batch_configs.extend(l)
    else:
        batch_configs = generateConfigs(master_config)
    
    budgets, ints = parse_budget_int(master_config)
    
    #os.chdir(WORKPATH) 
    for c in batch_configs:
        # create a new .json
        jsonpath = f"{WORKPATH}/{CONFIG_PATH}/{c['simulation_output_prefix']}.json"
        with open(jsonpath, 'w') as file:
            json.dump(c, file)
        print(jsonpath)
    
    # done with creating jsons. write to slurm if needed
    if configs_only:
        return True
    
    if jobArray:
        job_array_write(master_config, slurmFile, simulator_only) # see helper function below
        
        
    else: # writes jobs one by one, instead of in an array
        budgets, ints = parse_budget_int(master_config)
        for i,c in enumerate(batch_configs):
            # write to the run_file
            command=f"python {HOMEPATH}/run_spread_v2.py {WORKPATH}/{CONFIG_PATH}/{c['simulation_output_prefix']}.json --dag_type 1 -p {WORKPATH}/{DAG_PATH} --suppress_outfile"
            if not simulator_only:
                command += f"""; python {HOMEPATH}/algorithm_groupint_general_v2.py \
{WORKPATH}/{DAG_PATH}/*{c['simulation_output_prefix']}_*.csv {master_config['input']['hierarchy']} \
-b {budgets} -i {ints} \
--summary_path {WORKPATH}/{SUMMARY_PATH} --intervention_path {WORKPATH}/{INTERVENTION_PATH} \
--input_code {c['simulation_output_prefix']}"""
    
            # if shell:   # invoke as a simple bash command
            #     slurmFile.write('cd %s; %s > %s\n\n; cd -' %(folder,command,LOGFILE))
            # else:
            
            s = c['simulation_parameters']['number_of_simulations']
            mem_limit = '9G' if s<=100 else '18G' if s<=200 else '27G' if s<=300 else '100G' # SLURM memory limit for simulations
            # Be VERY careful about file directory, and where files are stored
            slurmFile.write(f'''sbatch \
-o {WORKPATH}/logs/{c['simulation_output_prefix']}_log.txt \
--export=ALL,command="{command}" --mem-per-cpu={mem_limit} \
./run_proc.sbatch; \
./qreg_single\n''')
            # log files and directories will be automatically created, if they do not exist
        print(f"Number of instances processed: {i+1}")

def job_array_write(master_config, slurmFile, simulator_only=False):
    '''Helper function to utilize SLURM's job array functionality to submit jobs.'''
    batches = master_config['batches']
    simulations = master_config['simulations']
    net_ind = (master_config['input']['network']).rindex('/')+1
    network_name = (master_config['input']['network'])[net_ind:]
    if type(simulations) != list:
        simulations = [simulations]
    for s in simulations:
        prefix=f"{master_config['prefix']}S{s}" # no need to add _%a here
        slurmFile.write(f'''\
mkdir -p {WORKPATH}/logs/{prefix}_{{0..{batches-1}}}
jid=$(sbatch \
-o {WORKPATH}/logs/{prefix}_%a/S{s}_%a_log.txt \
--array=0-{batches-1} \
--export=ALL,prefix={prefix} \
../scripts/pipe_sim.sbatch | awk '{{print $NF}}' )
echo "Submitted batch job $jid"; ../scripts/qreg_batch \n''')
        
        # interventions part
        if simulator_only:
            continue
        budgets = master_config['budget'] if type(master_config['budget'])==list else [master_config['budget']]
        ints = master_config['intervention_time'] if type(master_config['intervention_time'])==list else [master_config['intervention_time']]
        for b,i in itertools.product(budgets, ints):
            cpu_limit = math.ceil(MEM_VALUES[network_name] * int(s) * int(i) / 815) 
            cpu_limit = min(max(cpu_limit,1),20)
            # rough estimate of how many threads for optimizer to utilize, from 1 to 20
            print(network_name,s,i,b,cpu_limit)
            slurmFile.write(f'''\
sbatch -o {WORKPATH}/logs/{prefix}_%a/I{i}B{b}_log.txt \
--array=0-{batches-1} \
--dependency=aftercorr:$jid \
--ntasks={cpu_limit} --mem={cpu_limit*8}G \
--export=ALL,prefix={prefix},\
hierarchy={master_config['input']['hierarchy']},budget={b},\
int_time={i} \
../scripts/pipe_int.sbatch; \
../scripts/qreg_batch \n''')           


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
            generate_pipeline_instances(master_config, slurmFile,
                configs_only=args.configs_only,
                simulator_only=args.simulator_only,
                shell=False, # UNIMPLEMENTED
                jobArray=(not args.no_job_array)) 
            
    slurmFile.write('echo "Total time" $(($SECONDS-$start))\n')
    slurmFile.close()
