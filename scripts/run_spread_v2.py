DESC="""Multipathway simulator.

This is a slightly modified version from run_spread.py from MULTIPATHWAY_SIMULATOR
"""

import argparse
from json import load
import logging
import numpy as np
import pandas as pd
from random import seed
from time import time
import os
import msc_network as msc # ensure msc_network.py is in the same folder

# Constants
SUSCEPTIBLE=0
EXPOSED=1
INFECTIOUS=2
FORMAT="[%(filename)s] [%(levelname)s]: %(message)s"
INFINITY=-1

def compute_infectivity_level0(nodeAttributes, month):
    # Level 0
    nodeAttributes[0]['infectivity']=nodeAttributes[0][month]\
            *(nodeAttributes[0].state==INFECTIOUS)
    return

def compute_infectivity_level1(nodeAttributes, month):
    # Level 1
    # Aggregating infectivity for each locality by summing up infectivity of
    # its constituent cells and computing edge probabilities.
    nodeAttributes[1]['total_infectivity']=\
            nodeAttributes[0].groupby('locality')['infectivity'].sum()
            #nodeAttributes[0].groupby('locality').sum().infectivity # HC: moved infectivity over to avoid Depreciation Warning
    return

def compute_interventions(nodeAttributes,interventions,timeStep):
    nodeAttributes[0].infectivity = nodeAttributes[0].locality.map(
            interventions.time>=timeStep
            ).fillna(True)*nodeAttributes[0].infectivity
    return

def compute_suitability(nodesLevel0,suit_threshold,month):    
    # AA: Currently, as per the McNitt paper, suitability is 1 if production in that
    # AA: month is > 0.
    nodesLevel0['suitability']=nodesLevel0[month]>suit_threshold
    return 

def compute_probability_S(nodesLevel0,edges,alphaS,kernel, model):#mooreRange):
    ## if kernel=='moore': 
    ##     range_type1 = 'moore_distance'
    ##     range_type2 = 'moore'
    ## else:
    ##     range_type1 = range_type2 = range_type
    # Level 0
    nodesLevel0.probability=1-(np.exp(-(alphaS*nodesLevel0['infectivity'])))
    edges['probability'] = edges['source'].map(nodesLevel0.probability)
    edges['probability'] = (edges[kernel]<=model['kernel_parameters'])*edges['probability']
    return

def compute_probability_L(nodes, edges, alphaL):
    if args.dag_type==0:
        nodes[1].probability = 1 - (
            np.exp(-(alphaL * nodes[1]['total_infectivity'])))
        edges['probability'] = edges.source.map(nodes[1].probability)
    else:
        nodes[0]['exponent'] = -alphaL * nodes[0]['infectivity']
        edges['probability'] = 1-np.exp(
                edges.source.map(nodes[0].exponent))
    return

def compute_probability_LD(nodes, edges, alphaLD):
    # nodesLevel1.probability has already been computed in compute_probability_L()
    if args.dag_type==0:
        sourceInfectiousness = edges['source'].map(nodes[1].total_infectivity)
        edges['probability'] = 1 - (
            np.exp(-alphaLD * sourceInfectiousness * edges.weight))
    else:
        nodes[0]['exponent'] = -alphaLD * nodes[0].infectivity
        edges['probability'] = 1-np.exp(
                edges.source.map(nodes[0].exponent).multiply(edges.weight))
        ## nodes[0].probability = 1 - (                                                      
        ##                     np.exp(-(alphaLD * nodes[0]['infectivity'])))                                 
        ## edges['probability'] = edges['source'].map(nodes[0].probability)   
    return

def run_spread(network,
        model, 
        simulation, 
        simulationPrefix,
        seedNodes,interventions):

    logging.info('Initiating simulator ...')
    # Importing Hierarchy tree
    # This will establish parent-child relationship between level 1 and level 0 nodes
    # for the human-assisted pathways.

    hierarchyTree=network.hierarchy

    #PW: only cells within localities
    localityCellMap=hierarchyTree[hierarchyTree.parent!=-1]
    hierarchyTreeDict=hierarchyTree.groupby('parent')['child'].apply(list)
    hierarchyTreeDict=hierarchyTreeDict.to_dict()
    
    #PW: group cells by locality
    hierarchyTree=hierarchyTree.set_index('child').parent

    if not interventions is None:
        interventions = interventions.set_index('node')

    # Map "m#" to "#"
    renameMap={}
    for month in range(1,13):
        renameMap['m'+str(month)]=month

    # Prepare node attributes
    logging.info('Preparing node attributes table ...')
    nodeAttributes=[]
    
    ## Level 0
    nodeAttributes.append(network.nodes[0])
    nodeAttributes[0]=nodeAttributes[0].set_index('node')
    nodeAttributes[0]['locality']=\
            nodeAttributes[0].index.to_series().map(hierarchyTree)
    nodeAttributes[0]=nodeAttributes[0].rename(columns=renameMap)

    ## Level 1
    nodeAttributes.append(network.nodes[1])
    nodeAttributes[1]=nodeAttributes[1][nodeAttributes[1].node!=-1]
    nodeAttributes[1]=nodeAttributes[1].rename(columns=renameMap)
    nodeAttributes[1]=nodeAttributes[1].set_index('node')

    ## Simulation related parameters
    nodeAttributes[0]['state']=0
    nodeAttributes[0]['time_of_infection']=INFINITY
    nodeAttributes[0]['probability']=0
    nodeAttributes[1]['total_infectivity']=0
    nodeAttributes[1]['probability']=0

    # Prepare edgeAttribute table
    logging.info('Preparing edge attributes table ...')
    edgeAttributes={}

    ## Short distance natural pathway
    if 'haversine' not in network.edges[0].columns:
        network.edges[0]['haversine'] = -1
    edgeAttributes['S']=network.edges[0][['source','target','moore', 'haversine']].copy()

    ## edgeAttributes['S']=edgeAttributes['S'].rename(columns={
    ##     'moore': 'moore_distance'})
    edgeAttributes['S']['source_state']=SUSCEPTIBLE
    edgeAttributes['S']['target_state']=SUSCEPTIBLE
    edgeAttributes['S']['target_suitability']=0
    edgeAttributes['S']['live_edge']=False

    ### AA: Remove isolated cells or level 0 nodes
    nodeAttributes[0]=nodeAttributes[0][
            nodeAttributes[0].index.isin(
                edgeAttributes['S'].source.drop_duplicates().to_list())]

    ## Short distance human-assisted pathway
    ## These are edges from locality to its own cells.
    edgeAttributes['L']=localityCellMap.rename(columns={
        'parent': 'source',
        'child': 'target'})
    edgeAttributes['L']=edgeAttributes['L'].reset_index(drop=True)
    edgeAttributes['L']['target_state']=SUSCEPTIBLE
    edgeAttributes['L']['target_suitability']=0
    edgeAttributes['L']['live_edge']=False

    if args.dag_type == 1:
        # Taking the Cartesian product of a locality's set of cells with itself.
        edgeAttributes['L']['source'] = edgeAttributes['L'][
            'source'].map(hierarchyTreeDict)
        edgeAttributes['L'] = edgeAttributes['L'].explode('source')
        edgeAttributes['L'] = edgeAttributes['L'][
                edgeAttributes['L'].source!=edgeAttributes['L'].target]

    ## Long distance human-assisted pathway
    ## These are edges from a locality to cells belonging to other localities.
    ## These are grouped by month.
    longDistanceEdges=network.edges[1].merge(localityCellMap,
            left_on='target',right_on='parent')
    longDistanceEdges=longDistanceEdges.drop(['target','parent'],axis=1)
    longDistanceEdges['target_state']=SUSCEPTIBLE
    longDistanceEdges['target_suitability']=0
    longDistanceEdges['probability']=0
    longDistanceEdges['live_edge']=False

    
    if args.dag_type == 1:
        longDistanceEdges['source'] = longDistanceEdges['source'].map(
            hierarchyTreeDict)
        longDistanceEdges = longDistanceEdges.explode('source')
        longDistanceEdges=longDistanceEdges[
                longDistanceEdges.source!=longDistanceEdges.child]
    edgeAttributes['LD']=longDistanceEdges.rename(columns={
        'child': 'target'}).groupby('month')
    # Remove variables not required from this point
    del network
    
    # Map each timestep to the corresponding month.
    monthTimeStepMap=np.roll(
            np.arange(simulation['time_steps']+1) % 12, 
            -simulation['start_month']+1) + 1
    # Table which gives count of number of times a node v was infected at
    # time t. For now, it is a matrix of size 
    # (number of level 0 nodes) x (number of simulation steps + 1). The first 
    # column corresponds to time step 0.
    infectionCountTable = pd.DataFrame(np.zeros(
            (len(nodeAttributes[0]),simulation['time_steps']+1),
            dtype=int))
    infectionCountTable = infectionCountTable.set_index(nodeAttributes[0].index)
    numNodesInf = pd.DataFrame(np.zeros(
            (simulation['number_of_simulations'],simulation['time_steps']+1),
            dtype=int))
    # This table is being created to store the DAG.
    # It will be used only when dag_type!=1
    if args.dag_type==1:
        dagFile=f'{args.outpath if args.dag_outpath is None else args.dag_outpath}/{simulationPrefix}_dag.csv'
        timeExpandedTable = pd.DataFrame(columns=[
            'simulation_step',
            'source',
            'source_time_step',
            'source_index',
            'target',
            'target_time_step',
            'target_index',
            'level_0_intervention',
            'level_1_intervention',
            'pathway',
            'event'])

        timeExpandedTable.to_csv(dagFile,index=False)

    # Start simulations
    for simStep in range(simulation['number_of_simulations']): 
        logging.info(f'Iteration {simStep} ...')
        # Flush (or reset) system state
        nodeAttributes[0].state=SUSCEPTIBLE

        # Seed node state and bookkeeping
        nodeAttributes[0].loc[seedNodes.node.to_list(),'state']=np.less(
                np.random.random(seedNodes.shape[0]),
                seedNodes.probability).to_numpy()*INFECTIOUS
        infectionCountTable.loc[seedNodes.node,0] += nodeAttributes[0].loc[
                seedNodes.node.to_list(),'state'] == INFECTIOUS

        #for value counts of number of nodes infected
        numNodesInf.loc[simStep,0]=(nodeAttributes[0].state!=0).sum()

        # Set time of infection to 0 if seed node, else infinity 
        nodeAttributes[0].time_of_infection= \
                (nodeAttributes[0].state!=INFECTIOUS)*INFINITY
       
        # Simulating for the current iteration.
        for timeStep in range(1,config['simulation_parameters']['time_steps']+1):
            
            if args.dag_type==1:
                # nodeAttributes[0][ (nodeAttributes[0].state==EXPOSED) & (timeStep-nodeAttributes[0].time_of_infection-1 < model['exposure_delay'])]
                # E to E events
                EtoE = nodeAttributes[0][(nodeAttributes[0].state==EXPOSED) 
                        & (timeStep-nodeAttributes[0].time_of_infection
                            < model['exposure_delay'])].reset_index()[
                                    ['node','time_of_infection']]
                EtoE=EtoE.rename(columns={
                    "time_of_infection": "source_time_step",
                    "node":"source"})
                EtoE['simulation_step'] = simStep
                EtoE['source_index'] = timeStep-EtoE['source_time_step']-1
                EtoE['target'] = EtoE['source']
                EtoE['target_time_step'] = EtoE['source_time_step']
                EtoE['target_index'] = timeStep-EtoE['source_time_step']
                EtoE['level_0_intervention'] = -1
                EtoE['pathway'] = ""
                EtoE['event']="EtoE"

                # E to I events
                EtoI = nodeAttributes[0][(nodeAttributes[0].state==EXPOSED) & 
                        (timeStep-nodeAttributes[0].time_of_infection
                            == model['exposure_delay'])].reset_index()[
                                    ['node','time_of_infection']]
                EtoI=EtoI.rename(columns={
                    "time_of_infection": "source_time_step",
                    "node":"source"})
                EtoI['simulation_step'] = simStep
                EtoI['source_index'] = timeStep-EtoI['source_time_step']-1
                EtoI['target'] = EtoI['source']
                EtoI['target_time_step'] =  EtoI['source_time_step'] + \
                        EtoI['source_index'] + 1
                EtoI['target_index'] = -1
                EtoI['level_0_intervention'] = -1
                EtoI['pathway'] = ""
                EtoI['event']="EtoI"

            # Checking for E to I transitions
            # The extra minus 1 is necessary due to the following interpretation of
            # exposure delay: exposure_delay=k means wait for k time steps starting
            # from time_of_infection to transition from E to I.
            nodeAttributes[0].loc[ \
                (nodeAttributes[0].state==EXPOSED) & 
                (timeStep-nodeAttributes[0].time_of_infection-1==model['exposure_delay']), \
                'state']=INFECTIOUS

            if args.dag_type==1:
                # I to I events
                ItoI = nodeAttributes[0][
                    nodeAttributes[0].state==INFECTIOUS].reset_index()[['node']]
                ItoI=ItoI.rename(columns={"node":"source"})
                ItoI['simulation_step'] = simStep
                ItoI['source_index'] = -1
                ItoI['target'] = ItoI['source']
                ItoI['target_time_step'] = timeStep
                ItoI['source_time_step'] = timeStep-1
                ItoI['target_index'] = -1
                ItoI['level_0_intervention'] = -1
                ItoI['pathway'] = ""
                ItoI['event']="ItoI"


            # Compute infectivity and suitability of cells/localities.
            ### Set infectiousness of level0 nodes
            compute_infectivity_level0(nodeAttributes,str(monthTimeStepMap[timeStep]))
            ### Intervene at level0 nodes
            if not interventions is None:
                compute_interventions(nodeAttributes, interventions, timeStep)
            ### Set infectiousness of level1 nodes
            compute_infectivity_level1(nodeAttributes,str(monthTimeStepMap[timeStep]))
            compute_suitability(nodeAttributes[0],
                    model['suitability_thresh'],
                    str(monthTimeStepMap[timeStep]))
            
            #--------Natural or short distance pathway--------
            # Computing edge probabilities
            
            
            #compute_probability_S(nodeAttributes[0],
                    #edgeAttributes['S'],
                    #model['alpha_S'],
                    #model['moore_range'])
            compute_probability_S(nodeAttributes[0],
                    edgeAttributes['S'],
                    model['alpha_S'],
                    model['kernel'], model)                 

            # Updating source and target states and attributes
            edgeAttributes['S']['source_state']=\
                    edgeAttributes['S']['source'].map(nodeAttributes[0].state)
            edgeAttributes['S']['target_state']=\
                    edgeAttributes['S']['target'].map(nodeAttributes[0].state)
            edgeAttributes['S']['target_suitability']=\
                    edgeAttributes['S']['target'].map(nodeAttributes[0].suitability)

            # Computing live edges and state transitions
            # Removed edgeAttributes['S']['source_state']==INFECTIOUS) & \ for consistency
            edgeAttributes['S']['live_edge'] = \
                    (edgeAttributes['S']['target_suitability']==True) & \
                    (np.random.random(edgeAttributes['S'].shape[0])
                            <=edgeAttributes['S']['probability'])
            edgeAttributes['S']['newly_infected'] = \
                    (edgeAttributes['S']['target_state']==SUSCEPTIBLE) & \
                    (edgeAttributes['S'].live_edge)
            
            # Collecting live edges and adding them to the DAG
            if args.dag_type == 1:
                liveEdges=edgeAttributes['S'][
                        edgeAttributes['S']['live_edge']==True][['source','target']]
                liveEdges['time_step']=timeStep
                liveEdges['simulation_step']=simStep

                StoES=edgeAttributes['S'][edgeAttributes['S']['live_edge']==True]\
                        [['source','target']]
                StoES['simulation_step']=simStep
                StoES['source_time_step'] = timeStep - 1
                StoES['source_index'] = -1
                StoES['level_0_intervention'] = StoES['source']
                StoES['target_time_step'] = timeStep
                StoES['pathway'] = 'S'

                if model['exposure_delay']:
                    StoES['target_index'] = 0
                    StoES['event']="StoE"
                else:
                    StoES['target_index'] = -1 
                    StoES['event']="StoI"
            
            #--------- Local human-Mediated dispersal -----
            # This is common to both local and long-distance pathways.

            # Computing edge probabilities
            compute_probability_L(nodeAttributes,edgeAttributes['L'],model['alpha_L'])

            # Mapping current node states and attributes
            edgeAttributes['L']['target_state']=\
                edgeAttributes['L']['target'].map(nodeAttributes[0].state)
            edgeAttributes['L']['target_suitability']=\
                edgeAttributes['L']['target'].map(nodeAttributes[0].suitability)

            # Computing state transitions
            edgeAttributes['L']['live_edge'] = \
                    ((edgeAttributes['L']['target_suitability']==True) & \
                    (np.random.random(edgeAttributes['L'].shape[0])
                        <=edgeAttributes['L']['probability']))
            edgeAttributes['L']['newly_infected'] = \
                    (edgeAttributes['L']['target_state']==SUSCEPTIBLE) & \
                    (edgeAttributes['L'].live_edge)

            # Collecting live edges and adding it to the DAG.
            if args.dag_type==1:
                StoEL=edgeAttributes['L'][edgeAttributes['L']['live_edge']==True]\
                        [['source','target']]
                StoEL['simulation_step']=simStep
                StoEL['source_time_step'] = timeStep - 1
                StoEL['source_index'] = -1
                StoEL['target_time_step'] = timeStep
                StoEL['level_0_intervention'] = StoEL['source']
                StoEL['pathway'] = 'L'

                if model['exposure_delay']:
                    StoEL['target_index'] = 0
                    StoEL['event']="StoE"
                else:
                    StoEL['target_index'] = -1 
                    StoEL['event']="StoI"

            #--------- Long Distance human-mediated dispersal -------
            currentEdgesLD=edgeAttributes['LD'].get_group(
                    monthTimeStepMap[timeStep]).reset_index()
            # Computing edge probabilities
            compute_probability_LD(nodeAttributes,currentEdgesLD,model['alpha_LD'])

            # Mapping current node states and attributes
            currentEdgesLD['target_state']=\
                    currentEdgesLD['target'].map(nodeAttributes[0].state)
            currentEdgesLD['target_suitability']=\
                    currentEdgesLD['target'].map(nodeAttributes[0].suitability)

            # Computing state transitions
            currentEdgesLD['live_edge'] = (\
                    (currentEdgesLD['target_suitability']==True) & \
                    (np.random.random(currentEdgesLD.shape[0])
                        <=currentEdgesLD['probability']))
            currentEdgesLD['newly_infected']=\
                    (currentEdgesLD['target_state']==SUSCEPTIBLE) & \
                    (currentEdgesLD.live_edge)
            #print(currentEdgesLD.newly_infected.sum())

            # Collecting live edges and adding it to the DAG.
            if args.dag_type==1:
                StoELD = currentEdgesLD[
                        currentEdgesLD['live_edge']==True][['source','target']]
                StoELD['simulation_step']=simStep
                StoELD['source_time_step'] = timeStep - 1
                StoELD['source_index'] = -1
                StoELD['target_time_step'] = timeStep
                StoELD['level_0_intervention'] = StoELD['source']
                StoELD['pathway'] = 'LD'

                if model['exposure_delay']:
                    StoELD['target_index'] = 0
                    StoELD['event']="StoE"
                else:
                    StoELD['target_index'] = -1 
                    StoELD['event']="StoI"
                
            # End of time step. Updating all tables.
            newInfectedNodes=\
                    edgeAttributes['S'].groupby('target').newly_infected.max() | \
                    edgeAttributes['L'].groupby('target').newly_infected.max() | \
                    currentEdgesLD.groupby('target').newly_infected.max()
            numNodesInf.loc[simStep,timeStep]=newInfectedNodes.sum()
            nodeAttributes[0].loc[newInfectedNodes,['state','time_of_infection']]=(EXPOSED,timeStep)

            infectionCountTable.loc[newInfectedNodes,timeStep] +=1

            if args.dag_type==1:
                timeExpandedTable=pd.concat(
                        [timeExpandedTable, EtoE, EtoI, ItoI, 
                            StoES, StoEL, StoELD])
        if args.dag_type==1:
            timeExpandedTable['level_1_intervention']=\
                    timeExpandedTable.source.map(hierarchyTree)
            timeExpandedTable[[
                'simulation_step',
                'source',
                'source_time_step',
                'source_index',
                'target',
                'target_time_step',
                'target_index',
                'level_0_intervention',
                'level_1_intervention',
                'pathway',
                'event']].to_csv(dagFile,index=False,header=False,mode='a')
            timeExpandedTable=timeExpandedTable[0:0]

    logging.info('End of simulation. Collecting results ...')
    infectionCountTable = infectionCountTable/simulation['number_of_simulations']

    # Assign control variable to DAG.
    return infectionCountTable,numNodesInf

if __name__ == "__main__":

    # Parser
    parser=argparse.ArgumentParser(description=DESC,formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("config_file", help="Config file in json format.")
    parser.add_argument("--dag_type", type=int, help='''\
"Enter the type of DAG, \
0 = no DAG, \
1 = Level 0 nodes only, \
''', default=0)
    
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--no_time", action="store_true", help="Do not display time taken")
    parser.add_argument("-s","--summary", action="store_true", 
            help="Display summary of results. If no output path specified, prints out directly")
    parser.add_argument("-o", "--outpath", default="",
            help="Default directory for output")
    parser.add_argument("-p", "--dag_outpath",
            help="Default directory for DAG file output, if different")
    parser.add_argument("--summary_outpath",
            help="Default directory for summary file output")
    parser.add_argument("--include_headers", action="store_true",
            help="Write headers in every summary file. If false, header is written in a separate file")
    parser.add_argument("--summary_table", default="summary", 
            help="Summary table name to be used.")
    parser.add_argument("--sim_table", default="simulations", 
            help="Number of nodes infected in each simulation table name to be used.")
    parser.add_argument("--interventions_type", default="none", 
            help="This is just for book keeping in the database.")
    parser.add_argument("--suppress_outfile", action="store_true",
            help="Suppress output file generation.")
    args = parser.parse_args()
    
    
    #adding range types
   # parser.add_argument("--range type")

    # set logger
    if args.debug:
       logging.basicConfig(level=logging.DEBUG,format=FORMAT)
    elif args.quiet:
       logging.basicConfig(level=logging.WARNING,format=FORMAT)
    else:
       logging.basicConfig(level=logging.INFO,format=FORMAT)

    start=time()

    # Reading config file
    logging.info("Reading config file '%s' ..." %args.config_file)
    with open(args.config_file) as f:
        config = load(f)
    
    # Read network
    logging.info("Reading network '%s' ..." 
            %config['network_specific_input']['network'])
    network=msc.MultiScaleNet()

    network.read_from_folder(config['network_specific_input']['network'])
    network.display_summary()
    # Read interventions
    interventions=None
    try:
        logging.info(
            f"Reading interventions file \
                    '{config['network_specific_input']['interventions']}' ...")
        interventions = pd.read_csv(config['network_specific_input']['interventions'])
    except:
        logging.warning('No interventions found.')
        config['network_specific_input']['interventions']=""

    # Read seed nodes file
    logging.info(
        f"Reading seed file '{config['network_specific_input']['seeding']}' ..."
    )
    seedNodes = pd.read_csv(config['network_specific_input']['seeding'])
    # Set random seed for reproducibility
    try:
        logging.info("Setting random seed to %d ..." %config['random_seed'])
        np.random.seed(config['random_seed'])
        seed(config['random_seed'])  
    except KeyError:
        logging.warning('No seed for random number generator given.')

    # DAG type
    logging.info(f"DAG type: {args.dag_type}.")
    
    # Run simulation
    infectionProbability,numNodesInf=run_spread(
            network, 
            config['model_parameters'],
            config['simulation_parameters'],
            config['simulation_output_prefix'],
            seedNodes,
            interventions)
    # Post processing simulation output.
    if args.suppress_outfile:
        logging.info("Skipping generation of infections file ...")
    else:
        infectionProbability.to_csv(
                f"{args.outpath}/{config['simulation_output_prefix']}_infections.csv")

    if args.summary:
        # use pandas cumsum followed by regular sum
        # (time,value) pairs 0 - .5, 1 - 2.3, 2 - 4, ... (non-decreasing)
        accumulatedInfection = infectionProbability.sum().cumsum()
        infectionStats=numNodesInf.cumsum(axis=1).describe()
        #numNodesInf.cumsum(axis=1).to_csv('temp.csv',index=False)
        for timeStep,value in accumulatedInfection.items():
            if timeStep==0:
                continue
            if timeStep % 6:   # Half-a-year timesteps recorded
                continue
            header_string = "\
network_path, \
random_seed, \
suitability_thresh, \
exposure_delay, \
kernel, \
kernel_parameters, \
alpha_S, \
alpha_L, \
alpha_LD, \
start_month, \
number_of_time_steps, \
number_of_simulations, \
seeding, \
interventions, \
interventions_type, \
time_step, \
accumulated_probabilities, \
infections_mean, \
infections_std, \
infections_min, \
infections_25_per, \
infections_50_per, \
infections_75_per, \
infections_max\n"
            out_string = f"\
{config['network_specific_input']['network']}, \
{config['random_seed']}, \
{config['model_parameters']['suitability_thresh']}, \
{config['model_parameters']['exposure_delay']}, \
{config['model_parameters']['kernel']}, \
{config['model_parameters']['kernel_parameters']}, \
{config['model_parameters']['alpha_S']}, \
{config['model_parameters']['alpha_L']}, \
{config['model_parameters']['alpha_LD']}, \
{config['simulation_parameters']['start_month']}, \
{config['simulation_parameters']['time_steps']}, \
{config['simulation_parameters']['number_of_simulations']}, \
{config['network_specific_input']['seeding']}, \
{config['network_specific_input']['interventions']}, \
{args.interventions_type}, \
{timeStep},\
{value},\
{infectionStats[timeStep]['mean']},\
{infectionStats[timeStep]['std']},\
{infectionStats[timeStep]['min']},\
{infectionStats[timeStep]['25%']},\
{infectionStats[timeStep]['50%']},\
{infectionStats[timeStep]['75%']},\
{infectionStats[timeStep]['max']}\n" # do not omit newline.

        if args.summary_outpath is not None:
            if not args.include_headers:
                header_file = f"{args.summary_outpath}/0header.csv"
                if not os.path.isfile(header_file):
                    # possible race condition, but unlikely to cause problems
                    with open(header_file, 'w') as f:
                        f.write(header_string.replace(", ", ","))
            else:
                out_string = header_string + out_string
            with open(f"{args.summary_outpath}/{config['simulation_output_prefix']}_summary.csv", 'w') as file:
                # remove spaces after commas
                out_string = out_string.replace(", ", ",")
                file.write(out_string)
        else:
            print(header_string + out_string)
    totalTime=time()-start
    if not args.no_time:
        logging.info(f"Done. {totalTime/3600: .0f} hours {(totalTime-int(totalTime/3600)*3600)/60: .0f} minutes {totalTime%60: .0f} seconds")
