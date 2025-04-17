# Interventions Experiments: Pipeline and Analyses

These files were used to conduct two types of analyses: stability of solutions and influence of pathways.

All code is in `./scripts`, and the necessary inputs are in `./inputs`. There are five networks available for use in analyses: BD (Bangladesh), ID (Indonesia), PH (Philippines), TH (Thailand), and VN (Vietnam).

It is recommended to also have a `./work` directory and a `./results`directory to ensure code output functions properly. `./work` should contain directories named `configs`, `sim_summaries`, `dags`, `summaries`, and `interventions`.

The code was written to be run on a Linux/Unix high-performance computing cluster with SLURM job scheduling (https://www.rc.virginia.edu/userinfo/rivanna/overview/) It makes heavy use of parallelism, with pipeline inputs and outputs spread out across many files. If a SLURM cluster is available, complete with anaconda (or a similar python installation) and gurobipy, the code may be run as intended with slight adjustments to job script options in `pipe_sim.sbatch`, `pipe_int.sbatch`, and `run_proc.sbatch`.

Assume all commands below are run within the `scripts` directory. Use `chmod +x` to provide execute permissions to `master.sh`, `clear.sh`, `qreg_batch`, `qreg_single`, and (when it is created) `run.sh`.

## Stability of solutions analysis

Experiments are conducted using config files in `./input/config_files` that do not end with "model":  `bdconfig.json`, `idconfig.json`, `phconfig.json`, `thconfig.json`, and `vnconfig.json`. These may be configured to change input parameters, number of batches, or the lists of simulation counts, budgets, and intervention times to experiment on.

The `hierarchy.tree` files within `../input/networks/{network}` are also required for the interventions algorithm.

### Using SLURM

Run `./master.sh prepare_pipeline {network}` to prepare jobs for a single network, or `./master.sh prepare_all_pipelines {networks}` for multiple networks. The former uses 'BD' by default, and the latter uses all 5 networks by default.

Run the generated `./run.sh` to submit the jobs to SLURM.

Once all jobs have completed successfully, run `python gather_outputs.py` to collect outputs and create plots.

### Example invocations (no SLURM)

`python generate_pipelines.py ../input/configs/bdconfig.json`: reads the config file for the BD network and populates `../work/configs` with json config files for separate batches of simulations. (Also creates `./run.sh`)

`python run_spread_v2.py ../work/configs/BD_S100_24.json --dag_type 1 -s -p ../work/dags --summary_out ../work/sim_summaries --suppress_outfile`: runs a single batch of simulations, outputs the simulation results (as a directed acyclic graph csv) to `../work/dags`, and outputs summary info for the simulations to `../work/sim_summaries`.

`python algorithm_groupint_general_v2.py ../work/dags/BD_S100_24_dag.csv ../input/networks/BD/hierarchy.tree -b [3,5] -i [3,6,12] --summary_path ../work/summaries --intervention_path ../work/interventions --input_code BD_S100_24`: uses simulation output and hierarchy file to run the intervention algorithm, outputs summary info for the results to `../work/summaries/`, and outputs detailed intervention info (separate files for different budget/intervention delay combinations) to `../work/interventions/BD_S100_24`.

`python gather_outputs.py` : combines output data to create `../results/summaries.csv`, `../results/sim_summaries.csv`, and `../results/interventions.csv`, outputs calculated jaccard indices to `../results/jaccard_indices_{network}.csv`, and creates plots `../results/budget_plot_{network}.pdf`, `../results/objective_plot_{network}.pdf`, and `../results/jaccard_plot_{network}.pdf`.

`./clear.sh`: clears out folders in `work`. By default, clears out all folders. (Use the -h option to see other options.)

## Influence of pathways analysis

Experiments are conducted using config files in `./input/config_files` ending in "model": `bdconfig_model.json`, `idconfig_model.json`, `phconfig_model.json`, `thconfig_model.json`, and `vnconfig_model.json`. These may be configured to change input parameters, number of batches, or the lists of simulation counts, budgets, and intervention times to experiment on.

The `hierarchy.tree` files within `../input/networks/{network}` are also required for the interventions algorithm.

### Using SLURM

Run `./master.sh generate_pipelines_model {network}` to prepare jobs for a single network, or `./master.sh prepare_all_pipelines_model {networks}` for multiple networks.

Run the generated `./run.sh` to submit the jobs to SLURM.

Once all jobs have completed successfully, run `python gather_outputs_model.py` to collect outputs and create plots.

### Example invocations (no SLURM)

`python generate_pipelines_model.py ../input/config_files/bdconfig_model.json`: reads the config file for the BD network and populates `../work/configs` with json config files for separate simulations or batches of simulations. (Also creates `./run.sh`)

`python run_spread_v2.py ../work/configs/BD_as44_ald32.json --dag_type 1 -s -p ../work/dags --summary_out ../work/sim_summaries --suppress_outfile`: runs a single batch of simulations, outputs the simulation results (as a directed acyclic graph csv) to `../work/dags`, and outputs summary info for the simulations to `../work/sim_summaries`.

`python algorithm_groupint_general_v2.py ../work/dags/BD_as44_ald32_dag.csv ../input/networks/BD/hierarchy.tree -b [3,5] -i [3,6,12] --summary_path ../work/summaries --intervention_path ../work/interventions --input_code BD_as44_ald32`: uses simulation output and hierarchy file to run the intervention algorithm, outputs summary info for the results to `../work/summaries/`, and outputs detailed intervention info (separate files for different budget/intervention delay combinations) to `../work/interventions/BD_as44_ald32`.

`python gather_outputs_model.py` : gathers outputs into `../results/summaries.csv`, `../results/sim_summaries.csv`, and `../results/interventions.csv`, and creates plots `../results/{network}_contours.pdf`.

`./clear.sh`: clears out all folders in `work`. (Use the -h option to see other options.)

### 
