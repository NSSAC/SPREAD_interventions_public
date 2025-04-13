DESC='''
Reads pipeline output files and combines them into large csv files.
Also conducts analysis on influence of pathways, by creating contour plots'''

from glob import glob
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from itertools import product
import subprocess
from io import StringIO
from sys import argv

WORKPATH='../work'
SUMMARY_PATH=f'{WORKPATH}/summaries'
INTERVENTION_PATH=f'{WORKPATH}/interventions'
SIM_SUMMARY_PATH=f'{WORKPATH}/sim_summaries'
OUTPATH='../results'
plt.rcParams.update({
    "text.usetex" : len(argv)>1 and 'l' in argv[1],
    'font.size': 20,
    'axes.titlesize':26,
    'axes.labelsize':24,
    # 'xtick.labelsize':20,
    # 'ytick.labelsize':20,
    'font.family':'Computer Modern Roman'
})

def combine_sim_summaries(path=SIM_SUMMARY_PATH, output=False, separate_headers=True):
    '''Combines simulation summary files into one csv file.
    Accounts for two different output formats'''
    if not separate_headers:
        df_list = []
        for file in glob(f'{path}/*.csv'):
            df = pd.read_csv(file)
            df['filename'] = file
            df_list.append(df)
        if len(df_list)==0:
            print("No sim summaries found")
            return
        df_out = pd.concat(df_list, ignore_index=True).sort_values(['network_path','alpha_S','alpha_LD'])
        
    else:
        # One header file, multiple one-line files
        csv_string = subprocess.check_output(f"cat {path}/*.csv", shell=True, text=True)
        #os.system(f"cat {path}/*.csv > {OUTPATH}/sim_summaries.csv") 
        df_out = pd.read_csv(StringIO(csv_string))
        df_out['filename'] = sorted(glob(f'{path}/*.csv'))[1:]
        # ignores 0header.csv
        
    df_out['input_code'] = df_out['filename'].str.extract(r"(?<=\/)([A-Z]+_as[0-9]+_ald[0-9]+)(?=_summary\.csv)", expand=False)
    if output:
        df_out.to_csv(f'{OUTPATH}/sim_summaries.csv', index=False)
    return df_out
        

def combine_summaries(path=SUMMARY_PATH, output=False, separate_headers=True):
    '''Combines intervention summary files into one csv file.
    Accounts for two different output formats, and parses input filename to obtain alpha_S/alpha_LD'''
    if not separate_headers:
        df_list = []
        for file in glob(f'{path}/*.csv'):
            df_list.append(pd.read_csv(file))
        if len(df_list)==0:
            print("No summaries found")
            return
        df = pd.concat(df_list, ignore_index=True)
    else:
        csv_string = subprocess.check_output(f"cat {path}/*.csv", shell=True, text=True)
        df = pd.read_csv(StringIO(csv_string))
        
    network = df['int_filename'].str.extract(r"(?<=/)([A-Z]+)(?=_as)", expand=False) # CHANGED: depends on naming scheme!!
    df['network'] = network.fillna("")
    # It is impossible to get alphas from reading DAGs. Need to parse it from the input filename
    df['alpha_S'] = df['input_file'].str.extract(r"(?<=as)([0-9.]+)(?=_)", expand=False).astype(float) # can be decimal
    df['alpha_LD'] = df['input_file'].str.extract(r"(?<=_ald)([0-9.]+)(?=_)", expand=False).astype(float)
    df_out = df.sort_values(['network','alpha_S','alpha_LD','input_code'])
    if output:
        df_out.to_csv(f'{OUTPATH}/summaries.csv', index=False)
    return df_out

def combine_interventions(path=INTERVENTION_PATH, output=False):
    '''Combines detailed intervention output files across multiple folders into one csv file;
    also adds additional columns based on folder and file names'''
    df_list = []
    for folder in glob(path+'/*'):
        # summary files in folders; folder name is number of simulations
        foldername = os.path.basename(folder)
        network = re.search(r"^[A-Z]+(?=_S)", foldername)
        network = "" if network is None else network[0]
        # Highly dependent on folder naming scheme! May need to change if prefix is different
        alpha_S = float(re.search(r"(?<=as)[0-9.]+(?=_)", foldername)[0])
        alpha_LD = float(re.search(r"(?<=_ald)[0-9.]+", foldername)[0])
        for file in glob(folder+'/*.csv'):
            filename = os.path.basename(file)
            delay = int(re.search(r"(?<=I)[0-9]+(?=-)", filename)[0])
            budget = int(re.search(r"(?<=[0-9]-B)[0-9]+", filename)[0])
            int_df = pd.read_csv(file)
            int_df = int_df.assign(
                delay=delay,
                budget=budget,
                int_filename=file,
                network=network,
                alpha_S=alpha_S,
                alpha_LD=alpha_LD)
            int_df = int_df[['network','alpha_S','alpha_LD','delay','budget','group','time','int_filename']]
            df_list.append(int_df)
        # one row contains one node.
    if len(df_list)==0:
        print("No interventions found")
        return
    df_out = pd.concat(df_list, ignore_index=True).sort_values(['alpha_S','alpha_LD','int_filename'])
    if output:
        df_out.to_csv('../results/interventions.csv', index=False)
    return df_out

def alpha_plotter(df_ss, df_summary):
    '''Function to create a set of multiple contour plots when provided sim_summary and summary data for a network.'''
    df_ss = df_ss.copy()
    df_m = pd.merge(df_ss, df_summary, on=['alpha_S','alpha_LD','input_code'])
    
    plots_list = [] # save figs
    networks = df_m['network'].unique()
    for n in networks:
        print(n)
        delays = np.unique(df_m.loc[df_m['network']==n,'delay'])
        budgets = np.unique(df_m.loc[df_m['network']==n,'budget']) # np sorts, pd does not
        fig, axs = plt.subplots(len(budgets), len(delays), figsize=[6*len(delays), 5.25*len(budgets)])
        cmaps = ['viridis','magma','cividis','inferno','plasma']
        
        contour_levels = [None for _ in range(len(delays))]
        for i,j in product(range(len(budgets)), range(len(delays))):
            d,b = delays[j], budgets[i]
            print(d,b)
            print('Levels:', contour_levels[j])
            df_sub = df_m[(df_m.network==n) & (df_m.delay==d) & (df_m.budget==b)]
            if len(df_sub)<676:
                print("Missing points")
            _,_,levels=contour_plotter(df_sub, fig, axs[i,j], "lp_obj_value", cmap=cmaps[j],
                    cbar_label="Infected Nodes" if j==len(delays)-1 else "",
                    cbar_axs=(axs[:,j] if i==len(budgets)-1 else None),
                    levels=contour_levels[j]) # starts as 10, then becomes a set of levels
            if i==0:
                contour_levels[j] = levels # save levels
            axs[i,j].set_title(f"$B={int(b)}, \\: \\tau_D={int(d)}$")
        for i in range(len(budgets)):
            axs[i,0].set_ylabel(r"$\alpha_{LD}$")
        for j in range(len(delays)):
            axs[i,j].set_xlabel(r"$\alpha_S$")
            
        plots_list.append((fig,axs,n)) # save network name
        
    return plots_list

def contour_plotter(df_m, fig=None, ax=None, stat='infections_mean', stat_label='',
                    cbar_label='', cbar_axs=None, title=None, cmap='viridis', levels=9):    
    '''Helper function to create individual contour plots, to be packaged together'''
    if fig is None or ax is None:
        fig, ax = plt.subplots()
    df_m = df_m.sort_values(['alpha_LD', 'alpha_S']) # y first, for easier sorting
    
    X = np.unique(df_m['alpha_S'])
    Y = np.unique(df_m['alpha_LD'])
    Z = np.reshape(df_m[stat].to_numpy(), (len(Y), len(X))) # rows are y's, columns are X's
    CS = ax.contourf(X,Y,Z,cmap=cmap, levels=levels)
    if cbar_axs is not None:
        _ = fig.colorbar(CS, ax=cbar_axs, label=cbar_label)
    return fig, ax, CS.levels


if __name__=='__main__':
    a = argv[1] if len(argv)>1 else ""
    # does everything by default. If -o, skips plotting. If -p, skips combining and reads from csv
    if 'p' not in a:
        print("Combining Simulations...")
        df_ss = combine_sim_summaries(output=True)
        print("Combining Summaries...")
        df1 = combine_summaries(output=True)
    else:
        df_ss = pd.read_csv(f'{OUTPATH}/sim_summaries.csv')
        df1 = pd.read_csv(f'{OUTPATH}/summaries.csv')
    
    if 'o' not in a:
        print("Plotting...")  
        plots_list = alpha_plotter(df_ss, df1)
        print("Outputting")
        for fig,_,n in plots_list:
              fig.savefig(f'../results/{n}_contours.pdf',bbox_inches='tight')
    
    
    
