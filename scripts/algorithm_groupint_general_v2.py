import os
import networkx as nx
from gurobipy import Model, GRB, quicksum # gurobi installation required
import argparse
from itertools import product
from gm_compute import gm # make sure gm_compute.py is in the same folder
import pandas as pd

DESC="""Intervention Algorithm: Given a set of cascade simulations, runs LP \
to determine ideal intervention groups.

This is an updated version of algorithm_groupint_general from MULTIPATHWAY_SIMULATOR"""

def parseOneSimulation(lines, sim_id, m, unique_groups, x, y, z, int_time, no_action, l, group):
    print("Simulation: "+str(sim_id))
    G = nx.DiGraph()
    infectednodes = set([]) # records nodes that are infected if no action is taken
    edge_labels = {}
    sources = set([])
    for line in lines:
        cols = line.split(",")
        # Column names from simulation files: simulation_step,source,source_time_step,source_index,
        # target,target_time_step,target_index,level_0_intervention,level_1_intervention,pathway,event
        edgetype = cols[len(cols)-1]
        if edgetype == "EtoE":
           continue
        u = ""
        u_t = int(cols[2])
           
        if cols[3] == "-1":
           u = cols[1]+","+cols[2]
        else: #bypassing the EtoE edges: e.g., u,i,2 -> u,i+3,-1 is replaced by u,i,0 -> u,i+3,-1
           u = cols[1]+","+cols[2]+",0"
        infectednodes.add(cols[1])
       
        v = ""
        v_t = int(cols[5])
        if cols[6] == "-1":
           v = cols[4]+","+cols[5]
        else:
           v = cols[4]+","+cols[5]+","+cols[6]
        infectednodes.add(cols[4])
        G.add_edge(u,v)
        edge_labels[u+","+v] = edgetype
        #create ids for y and z variables
        y_id_u = u+","+str(sim_id) # u,i,(j,)id
        y_id_v = v+","+str(sim_id) # v,i,(j),id
        z_id_u = cols[1]+","+str(sim_id)
        z_id_v = cols[4]+","+str(sim_id)
        #setup z variables
        if z_id_u not in z:
           z[z_id_u] = m.addVar(vtype = GRB.CONTINUOUS, lb = 0.0, ub = 1.0, name = "z["+z_id_u+"]")
        if z_id_v not in z:
           z[z_id_v] = m.addVar(vtype = GRB.CONTINUOUS, lb = 0.0, ub = 1.0, name = "z["+z_id_v+"]")
        #setup y variables
        if y_id_u not in y:
           y[y_id_u] = m.addVar(vtype = GRB.CONTINUOUS, lb = 0.0, ub = 1.0, name = "y["+y_id_u+"]")
           m.addConstr(z[z_id_u] >= y[y_id_u], name = "node_infected_or_exposed_at_some_timestep_"+str(z_id_u)+","+str(y_id_u))
           if u_t < int_time:
              m.addConstr(y[y_id_u] == 1, name = "initially_infected_"+str(y_id_u))
        if y_id_v not in y:
           y[y_id_v] = m.addVar(vtype = GRB.CONTINUOUS, lb = 0.0, ub = 1.0, name = "y["+y_id_v+"]")
           m.addConstr(z[z_id_v] >= y[y_id_v], name = "node_infected_or_exposed_at_some_timestep_"+str(z_id_v)+","+str(y_id_v))
           if v_t < int_time:
              m.addConstr(y[y_id_v] == 1, name = "initially_infected_"+str(y_id_v))
        
        if cols[1] in group:
           g_u = group[cols[1]]
        else:
           group[cols[1]] = -1
           g_u = group[cols[1]]
        if cols[4] in group:
           g_v = group[cols[4]]
        else:
           group[cols[4]] = -1
           g_v = group[cols[4]]
        if g_u not in unique_groups:
           x[g_u] = m.addVar(vtype = GRB.CONTINUOUS, lb = 0.0, ub = 1.0, name = "x["+str(g_u)+"]")
           unique_groups.add(g_u)
        if g_v not in unique_groups:
           x[g_v] = m.addVar(vtype = GRB.CONTINUOUS, lb = 0.0, ub = 1.0, name = "x["+str(g_v)+"]")
           unique_groups.add(g_v)
       
    print("DAG (nodes, edges) "+str(len(G.nodes()))+","+str(len(G.edges())))
    #find sources in G (nodes with in_degree 0)   
    for w in G.nodes():
        if G.in_degree(w) == 0:
           sources.add(w)
           m.addConstr(y[w+","+str(sim_id)] == 1, name = "sources_are_infected_"+str(w)+","+str(sim_id))
    print("Sources: "+str(sources))     
    #edge constraints
    for edge in G.edges():
        v1 = edge[0]
        v2 = edge[1]
        cols_v2 = v2.split(",")
        t_v2 = int(cols_v2[1])
        v2_v = cols_v2[0]
        if v2_v not in group:
           print(v2_v, "not in any group ")
           
        g = group[v2_v]
        if t_v2 < int_time:
           continue
        if edge_labels[v1+","+v2] == "StoE":
           m.addConstr(y[v2+","+str(sim_id)] >= y[v1+","+str(sim_id)] - x[g], name = "(StoE) "+str(v1)+","+str(v2))
        elif edge_labels[v1+","+v2] == "EtoI":
           m.addConstr(y[v2+","+str(sim_id)] >= y[v1+","+str(sim_id)] - x[g], name = "(EtoI) "+str(v1)+","+str(v2))
        elif edge_labels[v1+","+v2] == "ItoI":
           m.addConstr(y[v2+","+str(sim_id)] >= y[v1+","+str(sim_id)] - x[g], name = "(ItoI) "+str(v1)+","+str(v2))
        else:
           continue
       
    for key in y:
        cols_y = key.split(",")
        if int(cols_y[-1]) != sim_id:
            continue # reduces redundancy, by skipping if not current simulation
        vertex = cols_y[0]
        t_y = int(cols_y[1])
        g_key = group[vertex]
        if t_y >= int_time:
            m.addConstr(y[key] <= 1 - x[g_key], name = "not_infected_if_vaccinated_on_time_"+str(key))
    no_action += len(infectednodes)

    return m, unique_groups, x, y, z, no_action

#Rounding Algorithm
def rounding(x, y, z, denom, fixed_budget=None):
    X = {} # stores if group is intervened, yes/no; rounded
    # Y = {} # unused?
    Y = None
    Z = {} # stores if node has been infected at some point, yes/no (for objective value); rounded
    # refer to detailed explanations below
 
    #round z values to Z (0 or 1)   
    for key, gv in z.items():
        # key refers to group number; gv refers to gurobi output
        val = gv.X # z value in question
        if val >= 0.5:
           Z[key] = 1
        else:
           Z[key] = 0
    
    #round x values to X
    if fixed_budget is None:
        gs = []
        vs = []
        ints = []
        count = 0
        frac_k = 1.0/(2*denom)
        print("Threshold: "+str(frac_k))
        for key, gv in x.items():
            val = gv.X # x value in question
            # 1/(2*denom), either GM or no_groups
            if val >= frac_k:
               X[key] = 1
               count = count+1
            else:
               X[key] = 0
            gs.append(key)
            vs.append(val)
            ints.append(X[key])
        df = pd.DataFrame({'group': gs, 'intervene': ints, 'val': vs})
        print("X rounded to 1: "+str(count))
    else:
        # Heuristic algorithm; guarantees interventions 
        # at a specified no. of groups, rather than those that pass threshold
        key_list, val_dict = [],{}
        for key, gv in x.items():
            key_list.append(key)
            val_dict[key] = gv.X
        # sort key list in descending order of corresponding x values
        key_list.sort(key=(lambda k: val_dict[k]), reverse=True)
        # now take top B nodes. Ties are handled arbitrarily
        for i in range(len(key_list)):
            key = key_list[i]
            if i<fixed_budget:
                X[key] = 1
            else:
                X[key] = 0
        print('Heuristic applied')
        print(X)
        df = pd.DataFrame()

    return X, Y, Z, df

#LP for group interventions
def prepareLP_group(input_file, budget_groups, int_time, l, group, hierarchy_file, 
                    use_gm=True, runtime=True, fixed_budget=None):
    
    no_action = 0.0
    # no_action1 = 0.0
    # current_sim_id = 0
    # count = -1
    m = Model('Group-Interventions-ILP')
    
    # templines = []
    unique_groups = set()
    # y_keys = set()
    # z_keys = set()
    x = {} # x[g_u]: stores whether a group is intervened or not. Between 0 and 1; represents probability of intervention
    y = {} # y[u,i,j]: stores if node in time-expanded graph is infected, at a given time/simulation
    z = {} # z[u,j]: stores if node u is infected in a given simuluation j, at some (any) timestep
    
    # Memory-efficient input file reading:
    # First, loop through entire file once to get rows in which new simulations start
    sim_starts = []
    current_sim_id=-1
    with open(input_file, 'r') as fp:
        next(fp) # discard header row
        for i, line in enumerate(fp, start=1): # iterate through rows
            sim_id = int(line[0:line.index(',')])
            if sim_id != current_sim_id:
                sim_starts.append(i)
                current_sim_id = sim_id
        sim_starts.append(i+1) # to signify end
    print("Simulation Cutoffs:\n"+str(sim_starts))
    
    #m.Params.Method = 1 if sim_id < 299 else -1 # dual simplex; else automatic
    #m.Params.Threads = 1 if sim_id < 99 else 2 if sim_id < 199 else 3 if sim_id < 299 else 0
    threads = int(os.environ['SLURM_NTASKS']) # number of threads specified in generate_pipelines
    m.Params.Threads = threads
    m.Params.Method = 2 if threads==1 else 3
         
    # Now use these cutoffs to create generators, which are passed to the function in lieu of lists
    fp = open(input_file, 'r')
    next(fp) # discard header row
    for index in range(len(sim_starts)-1):
        # index corresponds to current sim id
        lines = (next(fp).strip() for _ in range(sim_starts[index], sim_starts[index+1])) # a generator
        m, unique_groups, x, y, z, no_action = parseOneSimulation(lines, index, m, unique_groups, x, y, z, int_time, no_action, l, group)
    fp.close()
    M = float(index+1) # M: total number of simulations       
    
    no_action = no_action/M
    print("No Action: avg. # nodes infected "+str(no_action))
    print("Unique groups "+str(unique_groups))
    #budget constraint & group -1 cannot be intervened
    m.addConstr(quicksum(x[g] for g in unique_groups) <= budget_groups, name = "C4: budget constraint")
    if -1 in unique_groups:
        m.addConstr(x[-1] == 0, name = "C5: group -1 cannot be intervened")
    m.setObjective(quicksum(z[key] for key in z.keys())/M, GRB.MINIMIZE)
    m.update()
    m.optimize()
    LP_objValue = m.objVal
    for key in x.keys():
        print(key, x[key])
    print("Re-done budget")
    lp_budget = 0.0
    for key, gv in x.items():
        val = gv.X
        lp_budget += val
    print("budget used by LP "+str(lp_budget))
    no_groups = len(unique_groups)-1 if -1 in unique_groups else len(unique_groups)
    print("# groups: " + str(no_groups))
    if use_gm:
        # use gm to round instead
        gm_val = gm(pd.read_csv(input_file), pd.read_csv(hierarchy_file))
        print("GM value: "+str(gm_val))
        X,Y,Z,full_info = rounding(x,y,z, gm_val, fixed_budget=fixed_budget)
    else:
        gm_val=-1 # placeholder
        X,Y,Z,full_info = rounding(x,y,z, no_groups, fixed_budget=fixed_budget)
    r = m.runtime
    print("Optimizer runtime: "+str(r))
    w = m.work
    print("Optimizer work time: "+str(w))
    m.dispose()
    if runtime:
        return X,Y,Z, no_groups, LP_objValue, M, lp_budget, sim_id, gm_val, r, w, full_info # output runtime if specified
    else:
        return X,Y,Z, no_groups, LP_objValue, M, lp_budget, sim_id, gm_val # added: max sim_id, gm_val, runtime, work

def outputGenerator(X,Y,Z,no_groups,LP_objValue, M, int_time, budget_given, inputcode, outpath, full_info=None):
    
    # write to intervention file
    filename = outpath+"/"+str(inputcode)+"/"+ \
        f"I{str(int_time)}-B{str(budget_given)}.csv" #str(r)+"_"+str(r2)+"_"+ 
    if not os.path.isdir(outpath+"/"+str(inputcode)):
        os.mkdir(outpath+"/"+str(inputcode))
        # CAREFUL: this is a race condition! This is bypassed using mkdir in pipe_sim.sbatch
    fq = open(filename, 'w')
    fq.write("group,time,xval\n")
    budget_used = 0
    for key in X.keys():
        if X[key] == 1:
           budget_used += 1
           fq.write(str(key)+","+str(int_time)+"\n")
    fq.close()
    algo_value = 0
    for key in Z.keys():
        if Z[key] == 1:
           algo_value += 1
    algo_value = algo_value/M # algorithmic obj value: average number of infected nodes across all simulations
    print("Algorithm objective value "+str(algo_value))

    if full_info is not None:
        filename = outpath+"/"+str(inputcode)+"/"+ \
            f"comp_I{str(int_time)}-B{str(budget_given)}.csv" #str(r)+"_"+str(r2)+"_"+ 
        full_info[full_info.group!=-1].to_csv(filename, index=False)
    return budget_used, algo_value, filename

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=DESC,formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("input_file", help="Input DAG file to run simulation on")
    parser.add_argument("hierarchy_file", help="Input Hierarchy file of network")
    parser.add_argument("-b", "--budgets", nargs="+", type=int, required=True,
                        help="List of budgets; written as numbers separated by spaces")
    parser.add_argument("-i", "--intervention_times", nargs="+", type=int, required=True,
                        help="List of intervention times")
    parser.add_argument("-f","--out_filename", help="Filename for output summary, without path", default="summary.csv")
    #parser.add_argument("-n","--network_name", default="",
    #                    help="Name of network that input files correspond to")
    parser.add_argument("--summary_path", help="Output summary file path", default="output/summaries")
    parser.add_argument("--intervention_path", help="Output directory for intervention folders", default="../work/interventions")
    parser.add_argument("--input_code", help="Add a prefix to each output file", default="")
    parser.add_argument("--no_gm", action='store_true', help="Round results using number of groups instead of GM")
    parser.add_argument("--fixed_budget", action='store_true', help="Specify to force algorithm to intervene with a fixed budget instead of rounding")
    args = parser.parse_args()

    # read hierarchy file for group mapping, line by line
    group = {}
    fq = open(args.hierarchy_file,'r')
    next(fq) # discard header
    # for line in lines:
    for line in fq: # can iterate through file directly
        cols = line.strip().split(",")
        g = cols[0]
        node = cols[1]
        group[node] = int(g)
    fq.close()
    print("Groups:")
    print(group)
    
    header_file = f"{args.summary_path}/0header.csv" # file containing headers
    # one file per budget/int_time instance
    if not os.path.isfile(header_file):    
        with open(header_file, 'w') as f:
            f.write("input_code,num_sims,budget,delay,budget_used,lp_budget,obj_value,lp_obj_value,gm_value,lp_runtime,lp_work,input_file,int_filename\n")
    # separate header file helps avoid race conditions.
    
    # we write headers ahead of time. the delay below should be long enough so as to not overwrite anything
    for budget, int_time in product(args.budgets, args.intervention_times):
        print("budget, int_time: "+str(budget)+","+str(int_time))
        # output string for summary
        X,Y,Z, no_groups, LP_objValue, M, lp_budget, max_sim, gm_val, runtime, work, full_info = prepareLP_group(args.input_file, budget, int_time,0, group, 
        args.hierarchy_file, use_gm=(not args.no_gm), fixed_budget=(budget if args.fixed_budget else None))
        budget_used, algo_value, int_filename = outputGenerator(X,Y,Z,no_groups,LP_objValue, M, int_time, budget, args.input_code,  outpath=args.intervention_path, full_info=full_info)
        #budget_given is used as name for lp_budget due to change in notion
        
        output = f"{args.input_code},{max_sim+1},{budget},{int_time},{budget_used},{lp_budget},{algo_value},{LP_objValue},{gm_val},{runtime},{work},{args.input_file},{int_filename}\n"
        summary_file = f"{args.summary_path}/{args.input_code}_I{int_time}B{budget}_{args.out_filename}"
        with open(summary_file, "w") as fp:
             fp.write(output)
        del X,Y,Z,no_groups,LP_objValue,M,lp_budget,max_sim,budget_used,algo_value,int_filename # free up memory
        print()
  
