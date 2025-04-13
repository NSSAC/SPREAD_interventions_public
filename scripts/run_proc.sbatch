#!/bin/bash
# SLURM JOB SCRIPT OPTIONS:
#SBATCH --time=06:00:00
#SBATCH -n 1
#SBATCH --mem-per-cpu=18G
#SBATCH -p bii
# charge code
#SBATCH -A bii_nssac

# This is an older script that simply prints and runs whatever commands are passed to it. Not really used anymore

# Load any modules you require:
module add anaconda
module add gurobi

echo "###################################"
echo "$command"
echo "###################################"
eval "$command"
