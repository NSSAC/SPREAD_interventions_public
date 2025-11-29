#!/bin/bash
# SLURM JOB SCRIPT OPTIONS:
#SBATCH --time=02:00:00
#SBATCH -n 1
# Partition option:
#SBATCH -p bii
# Charge code opton:
##SBATCH -A nssac_students
#SBATCH -A bii_nssac

# Load any modules you require:
# module add anaconda
module add miniforge
# change this as required, depending on Python installation

HOMEPATH="../scripts" # for scripts
WORKPATH="../work"
# Where files are saved, relative to WORKPATH:
CONFIG_PATH="configs"
# These are used for slurm, not for generating:
SIM_SUMMARY_PATH="sim_summaries"
DAG_PATH="dags"
#SUMMARY_PATH="summaries"
INTERVENTION_PATH="interventions"

set -e # exit on error

if [ -z "$single" ]; then
    prefix_index="_${SLURM_ARRAY_TASK_ID}"
else
    prefix_index=""
fi

echo "Running Simulator..."
python ${HOMEPATH}/run_spread_v2.py ${WORKPATH}/${CONFIG_PATH}/${prefix}${prefix_index}.json --dag_type ${dag_type:-1} -s -p ${WORKPATH}/${DAG_PATH} --summary_out ${WORKPATH}/${SIM_SUMMARY_PATH} #--suppress_outfile
echo "Done. Preparing intervention directory"
mkdir -p ${WORKPATH}/${INTERVENTION_PATH}/${prefix}${prefix_index}

