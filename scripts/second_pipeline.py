DESC='''Code to generate a second batch of simulation pipelines,
this time incorporating intervention algorithm output, to calculate infection counts.
'''

import json
from glob import glob
import argparse
import pandas as pd
from pdb import set_trace
from create_batch_configs import generateConfigs 

HOMEPATH="../scripts"
WORKPATH="../work"
CONFIG_PATH = 'configs'
SIM_SUMMARY_PATH="sim_summaries"
DAG_PATH="dags"
RESULTSPATH='results'
# Where files are saved, relative to WORKPATH:
INPUTPATH= "../input/config_files"


def collect_configs(inputpath:str=INPUTPATH) -> dict:
	'''
	Reads in all config.json files in the config_files directory, 
	making it easier to match interventions based on prefix.
	For best results, make sure there are no repeated prefixes for desired config files (behavior is unpredictable otherwise)
	'''
	config_dict = {}
	for conf in glob(f'{inputpath}/*config.json'):
		with open(conf, 'r') as file:
			master_config = json.load(file)
		prefix = str(master_config['prefix']).replace('_','')
		config_dict[prefix] = master_config
	return config_dict

def generate_intervention_configs(df_int: pd.DataFrame) -> list[dict]:
	'''
	Generates a list of new dicts corresponding to simulator config files,
	with one config file per intervention output
	'''
	df_int = df_int.drop_duplicates('int_filename').reset_index(drop=True)
	 # want unique intervention files
	
	config_dict = collect_configs(INPUTPATH)
	out_configs_list = []
	for i in range(len(df_int)):
		master_config = config_dict.get(df_int.at[i,'prefix'])
		out_config = generateConfigs(master_config, intervention=df_int.at[i,'int_filename'])[0]
		# out_config should be a list of length 1 (since only one batch)

		out_config["simulation_output_prefix"] = (
			out_config["simulation_output_prefix"].replace('_0','') + f"_I{df_int.at[i,'delay']}-B{df_int.at[i,'budget']}"
		) # clean up the output prefix, since that'll be used to output configs and simulations
		out_configs_list.append(out_config)

	return	out_configs_list

def second_pipeline_instances(int_summary_file: str, slurmFile) -> None:
	'''
	Prepares the entire second config, including writing config files 
	and preparing job submits to slurm. Only prepares simulator runs, not interventions
	'''
	df_int = pd.read_csv(int_summary_file)
	out_configs_list = generate_intervention_configs(df_int)

	for c in out_configs_list:
		# create a new .json for each config file
		prefix = c['simulation_output_prefix']
		jsonpath = f"{WORKPATH}/{CONFIG_PATH}/{prefix}.json"
		with open(jsonpath, 'w') as file:
			json.dump(c, file)
		print(jsonpath)

		logpath=f"{WORKPATH}/logs/{prefix}"
		slurmFile.write(f'''\
mkdir -p {logpath} 
sbatch -o {logpath}/log.txt \
--export=ALL,prefix={prefix},dag_type=0,single=1 \
../scripts/pipe_sim.sbatch; ../scripts/qreg_batch \n''') # one statement per config files, no batches

def main():
	# parser
	parser=argparse.ArgumentParser(description=DESC, 
			formatter_class=argparse.RawTextHelpFormatter)

	# feature vector arguments
	parser.add_argument("int_summary_file",help="Interventions output summary file path",
						nargs='?', default=RESULTSPATH+'/interventions.csv')
	parser.add_argument("-r", "--run_file", 
			default="run.sh",
			help="It contains slurm invocation of training script for each instance.")
	args = parser.parse_args()
	
	slurmFile = open(args.run_file, 'w')
	slurmFile.write('#!/bin/bash\n')
	slurmFile.write('start=$SECONDS\n')

	slurmFile.write('../scripts/clear.sh -s\n') # need to clear simulation output
	second_pipeline_instances(args.int_summary_file, slurmFile)
			
	slurmFile.write('echo "Total time" $(($SECONDS-$start))\n')
	slurmFile.close()

if __name__ == '__main__':
	main()