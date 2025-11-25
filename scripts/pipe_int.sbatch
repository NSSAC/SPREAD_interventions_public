#!/bin/bash
# SLURM JOB SCRIPT OPTIONS:
#SBATCH --time=06:00:00
##SBATCH -A nssac_students
#SBATCH -A bii_nssac
#SBATCH -p bii
# ntasks and memory handled by script

# Load any modules you require:
# module add anaconda
module add miniforge/24.3.0-py3.11
module add gurobi/10.0.1
export PYTHONPATH=$EBROOTGUROBI/lib/python3.11_utf32
# change these as required, depending on Python installation

HOMEPATH="../scripts" # for scripts
WORKPATH="../work"
# These are used for slurm, not for generating:
DAG_PATH="dags"
SUMMARY_PATH="summaries"
INTERVENTION_PATH="interventions"

set -e # exit on error

if [ -z "$single" ]; then
    prefix_index="_${SLURM_ARRAY_TASK_ID}"
else
    prefix_index=""
fi

echo "Running Interventions..."
python ${HOMEPATH}/algorithm_groupint_general_v2.py \
    ${WORKPATH}/${DAG_PATH}/*${prefix}${prefix_index}_dag.csv ${HOMEPATH}/${hierarchy} \
    -b ${budget} -i ${int_time} \
    --summary_path ${WORKPATH}/${SUMMARY_PATH} --intervention_path ${WORKPATH}/${INTERVENTION_PATH} \
    --input_code ${prefix}${prefix_index}
    #--fixed_budget # specify for heuristic budget. Remove otherwise
