DESC='''
Reads pipeline output files and combines them into large csv files.
Also conducts analysis on stability of solutions, by calculating Jaccard indices and producing boxplots'''

from glob import glob
import os
import re
import pandas as pd
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
except:
    print("Matplotlib or seaborn not found; plotting functions will be disabled.")
    pass
from itertools import combinations
import subprocess
from io import StringIO
from sys import argv

WORKPATH='../work'
SUMMARY_PATH=f'{WORKPATH}/summaries'
INTERVENTION_PATH=f'{WORKPATH}/interventions'
SIM_SUMMARY_PATH=f'{WORKPATH}/sim_summaries'
OUTPATH='results'

NETWORK_NODE_COUNT = {
    'BD':211,
    'ID':3296,
    'PH':673,
    'TH':738,
    'VN':503
}# number of nodes in each of the networks. Hardcoded for sake of time

try:
    plt.rcParams.update({
        # "text.usetex" : len(argv)>1 and 'l' in argv[1],
        'font.size': 22,
        'axes.titlesize':28,
        'axes.labelsize':26,  
    })
    if len(argv)>1 and 'l' in argv[1]:
        plt.rcParams.update({
            'text.usetex' : True,
            'font.family':'Computer Modern Roman'
        })
except:
    print("Matplotlib not found; plotting functions will be disabled.")
    pass


def combine_sim_summaries(path=SIM_SUMMARY_PATH, output=False, separate_headers=True):
    '''Combines simulation summary files into one csv file.
    Accounts for two different output formats'''
    if not separate_headers:
        # each csv file has the same header
        df_list = []
        for file in glob(f'{path}/*.csv'):
            df = pd.read_csv(file)
            df['filename'] = file
            df_list.append(df)
        if len(df_list)==0:
            print("No sim summaries found")
            return
        df_out = pd.concat(df_list, ignore_index=True)
        
    else:
        # One header file, multiple one-line files
        csv_string = subprocess.check_output(f"cat {path}/*.csv", shell=True, text=True) # use shell command (cat) to combine files
        df_out = pd.read_csv(StringIO(csv_string))
        df_out['filename'] = [s for s in sorted(glob(f'{path}/*.csv')) if s.endswith('summary.csv')]
        # ignores 0header.csv
        
    df_out['network'] = df_out['network_path'].str.slice(start=-2) # assumes two-letter networks
    df_out['node_count'] = df_out['network'].map(NETWORK_NODE_COUNT)

    df_out['input_code'] = df_out['filename'].str.extract(r"(?<=\/)([A-Z]+_S[0-9]+_[0-9]+)(?=_summary\.csv)", expand=False)
    df_out = df_out.sort_values(['network_path','number_of_simulations','input_code'])
    if output:
        df_out.to_csv(f'{OUTPATH}/sim_summaries.csv', index=False)
        print(f'{OUTPATH}/sim_summaries.csv')
    return df_out



def combine_summaries(path=SUMMARY_PATH, output=False, separate_headers=True):
    '''Combines intervention summary files into one csv file.
    Accounts for two different output formats (see combine_sim_summaries)'''
    if not separate_headers:
        df_list = []
        for file in glob(f'{path}/*.csv'):
            df_list.append(pd.read_csv(file))
        if len(df_list)==0:
            print("No summaries found")
            return
        df_out = pd.concat(df_list, ignore_index=True).sort_values(['network_path','num_sims','delay','budget'])
    else:
        csv_string = subprocess.check_output(f"cat {path}/*.csv", shell=True, text=True)
        df = pd.read_csv(StringIO(csv_string))
        
    network = df['int_filename'].str.extract(r"(?<=/)([A-Z]+)(?=[0-9]*_S)", expand=False) # depends on naming scheme
    df['network'] = network.fillna("")

    df_out = df.sort_values(['network','num_sims','delay','budget','input_code'])
    if output:
        df_out.to_csv(f'{OUTPATH}/summaries.csv', index=False)
        print(f'{OUTPATH}/summaries.csv')
    return df_out

def combine_interventions(path=INTERVENTION_PATH, output=False):
    '''Combines detailed intervention output files across multiple folders into one csv file;
    also adds additional columns based on folder and file names'''
    df_list = []
    for folder in glob(path+'/*'):
        # summary files in folders; folder name is number of simulations
        foldername = os.path.basename(folder)
        num_sims = int(re.search(r"(?<=S)[0-9]+(?=_)", foldername)[0])
        network = re.search(r"^[A-Z]+(?=[0-9]*_S)", foldername)
        network = "" if network is None else network[0]
        # Highly dependent on folder naming scheme; may need to modify if prefix is different
        prefix = re.search(r"^[A-Z]+[0-9]*(?=_S)", foldername)
        prefix = "" if prefix is None else prefix[0]
        for file in glob(folder+'/*.csv'):
            filename = os.path.basename(file)
            delay = int(re.search(r"(?<=I)[0-9]+(?=-)", filename)[0])
            budget = int(re.search(r"(?<=[0-9]-B)[0-9]+", filename)[0])
            int_df = pd.read_csv(file)
            int_df = int_df.assign(
                num_sims=num_sims,
                delay=delay,
                budget=budget,
                int_filename=file,
                network=network,
                prefix=prefix )
            int_df = int_df[['network','prefix','num_sims','delay','budget','group','time','int_filename']]
            df_list.append(int_df)
        # one row contains one node.
    if len(df_list)==0:
        print('No files found!')
        return
    df_out = pd.concat(df_list, ignore_index=True).sort_values(['num_sims','int_filename'])
    if output:
        df_out.to_csv(f'{OUTPATH}/interventions.csv', index=False)
        print(f'{OUTPATH}/interventions.csv')
    return df_out
        
            
def summary_plotter(df, use_IB=True):
    '''Function to create boxplots when provided summary data for a network.'''
    df = df.copy()
    df['bud_ratio'] = df['budget_used']/df['lp_budget']
    df = df.dropna(subset=['obj_value','bud_ratio'])
    df[r'(Budget, Delay)'] = '('+ df['budget'].astype(str) + ',' + \
                                    df['delay'].astype(str) + ')'
    fig1, ax1 = plt.subplots(figsize=[12,4.8]) # obj value plot 
    if use_IB:
        # split by intervention delay and budget
        df = df.sort_values(['budget','delay'])
        sns.boxplot(data=df, x='num_sims', y='obj_value', ax=ax1,
                          orient='v', hue="(Budget, Delay)", showmeans=True)
        sns.move_legend(ax1, "center right")# , bbox_to_anchor=(1, 1))
        ax1.get_legend().set_title(r"$(B, \tau_D)$")
    else:
        # don't split
        sns.boxplot(data=df, x='num_sims', y='obj_value', ax=ax1,
                          orient='v', showmeans=True)
        sns.move_legend(ax1, "center right", bbox_to_anchor=(1, 1))

    ax1.set_xlabel("Number of Simulations")
    ax1.set_ylabel("Objective Value")
    
    fig2, ax2 = plt.subplots(figsize=[12,4.8])
    if use_IB:
        # split by intervention delay and budget
        sns.boxplot(data=df, x='num_sims', y='bud_ratio', ax=ax2,
                          orient='v', hue="(Budget, Delay)", showmeans=True)
        sns.move_legend(ax2, "center right")# , bbox_to_anchor=(1, 1))
        ax2.get_legend().set_title(r"$(B, \tau_D)$")
    else:
        # don't split
        sns.boxplot(data=df, x='num_sims', y='bud_ratio', ax=ax2,
                          orient='v', showmeans=True)
        sns.move_legend(ax2, "center right")#, bbox_to_anchor=(1, 1))

    ax2.set_xlabel("Number of Simulations")
    ax2.set_ylabel("Budget Used / LP_Budget")
    
    return (fig1,ax1), (fig2,ax2)

def calculate_jaccards(df, use_IB=True):
    '''Uses output data to calculate and output pairwise Jaccard indices from intervention outputs'''
    group_names = df['group'].astype(str) + ',' + df['time'].astype(str)
    # New dataframe; one row per filename
    df_files = df[['num_sims','delay','budget','int_filename']].groupby('int_filename').first()
    df_files['group_set'] = group_names.groupby(df['int_filename'], group_keys=False).apply(set) # series of sets
    
    def jaccard_list(group_sets):
        # input is a subsetted series of sets
        jaccard_list = []
        for a,b in combinations(list(group_sets), 2):
            jaccard_list.append(jaccard(a,b))
        return jaccard_list
    
    if use_IB:
        grouped = df_files.groupby(['num_sims','budget','delay'], group_keys=True)
    else:
        grouped = df_files.groupby(['num_sims'], group_keys=True)
    
    df_out = grouped['group_set'].apply(jaccard_list).explode().reset_index() # one row = one jaccard index
    df_out = df_out.rename(columns={'group_set':'jaccard'})
    return df_out
    
def jaccard(s1, s2):
    '''Helper function: given two sets, returns their Jaccard index.'''
    num = len(s1.intersection(s2))
    denom = len(s1.union(s2))
    return num/denom # float by default

def jaccard_plotter(df):
    '''Uses the Jaccard dataframe (from calculate_jaccards) to create boxplots of Jaccard indices.'''
    fig,ax = plt.subplots(figsize=[12,4.8])
    if 'budget' in df.columns and 'delay' in df.columns:
        # grouped
        df = df.sort_values(['budget','delay'])
        df['(Budget, Delay)'] = '('+ df['budget'].astype(str) + ',' + \
            df['delay'].astype(str) + ')'
        sns.boxplot(data=df, x='num_sims', y='jaccard', hue='(Budget, Delay)',
                    ax=ax, orient='v', showmeans=True)
        sns.move_legend(ax, "center right")#, bbox_to_anchor=(1, 1))
        ax.get_legend().set_title(r"$(B, \tau_D)$")
    else:
        # not grouped
        sns.boxplot(data=df, x='num_sims', y='jaccard',
                    ax=ax, orient='v', showmeans=True)
        sns.move_legend(ax, "center right")#, bbox_to_anchor=(1, 1))
    ax.set_xlabel("Number of Simulations")
    ax.set_ylabel("Pairwise Jaccard Index")
    return fig,ax
  
def plot_multiple(df_s, df_i, jc=None):
    '''Handles creating multiple plots at once, given summary and interventions data'''
    networks = df_s['network'].unique()
    for n in networks:
        print(n)
        df1 = df_s[df_s['network']==n]
        (fig1, ax1), (fig2, ax2) = summary_plotter(df1, use_IB=True)
        ax1.title.set_text(n)
        ax2.title.set_text(n)
        fig1.savefig(f'../results/objective_plot_{n}.pdf',bbox_inches='tight')
        fig2.savefig(f'../results/budget_plot_{n}.pdf',bbox_inches='tight')
        df2 = df_i[df_i['network']==n]
        # Outputs jaccards by default
        jc = calculate_jaccards(df2, use_IB=True)
        jc.to_csv(f'../results/jaccard_indices_{n}.csv', index=False)
        fig, ax = jaccard_plotter(jc)
        ax.title.set_text(n)
        fig.savefig(f'../results/jaccard_plot_{n}.pdf',bbox_inches='tight')


if __name__=='__main__':
    a = argv[1] if len(argv)>1 else ""
    # simple command line options
    if 'p' not in a:
        if 'i' not in a:
            print("Combining Simulations...")
            _ = combine_sim_summaries(output=True)
        if 's' not in a:
            print("Combining Summaries...")
            df1 = combine_summaries(output=True)
            print("Combining Interventions...")
            df2 = combine_interventions(output=True)
    else:
        df1 = pd.read_csv(f'{OUTPATH}/summaries.csv')
        df2 = pd.read_csv(f'{OUTPATH}/interventions.csv')
    if 'o' not in a and 'i' not in a and 's' not in a:
        print('Plotting...')
        plot_multiple(df1,df2)
    
    
    
