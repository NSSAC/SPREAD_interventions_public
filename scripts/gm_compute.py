DESC = '''
Computing gm, the maximum number of groups corresponding to a path.

By: AA
(Unchanged, but other scripts depend on this)
'''

import argparse
import pandas as pd
from pdb import set_trace

def gm_per_cascade(df, tree):
    # Assumes that the ordering of the edges respects topological ordering
    gm = 0
    instance = df.iloc[0].simulation_step

    # Pathgroups dictionary
    pgv = dict()

    # Initiate seeds
    seeds = df[['source', 'source_time_step', 'source_index']][
            df.source_time_step==0].values
    
    for row in seeds:
        gp = tree[row[0]]
        if gp != -1:
            pgv[tuple(row)] = set([frozenset([gp])])
        else:
            pgv[tuple(row)] = set([frozenset()])

    live_edges = df[['source', 'source_time_step', 'source_index',
            'target', 'target_time_step', 'target_index']].values

    for le in live_edges:
        source = tuple(le[0:3])
        target = tuple(le[3:])

        if le[0] == le[3]:
            pgv[target] = pgv[source] # inherits parent node's pathgroups
            continue

        gp = tree[le[3]]

        # Add target group to pathgroups of source
        source_spec_target_set = set()
        for pg in pgv[source]:
            pgs = set(pg)   # converting frozenset to frozen
            pgs.add(gp)
            gm = max(len(pgs), gm)
            source_spec_target_set.add(frozenset(pgs))

        # Merge the new set of pathgroups with existing pathgroups set of the target
        try:
            pgv[target] = pgv[target].union(source_spec_target_set)
        except KeyError:
            pgv[target] = source_spec_target_set
    
    return gm

def gm(sim, tree):
    tree = tree[['child', 'parent']].set_index('child', drop=True).squeeze()
    gmH = sim.groupby('simulation_step').apply(gm_per_cascade, tree)
    return gmH.max()

def main():
    # parser
    parser=argparse.ArgumentParser(description=DESC,
            formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-i', '--simulations_file', required=True,
            help='Simulation DAGs. CSV format')
    parser.add_argument('-t', '--hierarchy_tree', required=True,
            help='Hierarchy tree containing group membership information')
    args = parser.parse_args()

    df = pd.read_csv(args.simulations_file)
    tree = pd.read_csv(args.hierarchy_tree)

    gmax = gm(df, tree)

    print(gmax)

if __name__ == '__main__':
    main()
