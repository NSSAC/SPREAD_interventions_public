DESC="""Defines multiscale network class and provides read/write
functionality. A multiscale network consists of (1) a sequence of networks
(specified as ((0.nodes,0.edges),(1.nodes,1.edges),...) and (2) a hierarchy
tree (hierarchy.tree) that specifies the parent-child relationship between
nodes of different levels.

Pending:
- Mandatory column testing.
- To verify the hierarchy tree, it is read in as a string dataframe. This is a
  potential performance issue. However, it permits using different data types
  at different levels.
By: MS and AA

(Unchanged, but other scripts depend on this)
"""
import argparse
import logging
import numpy as np
import pandas as pd
import pdb
from glob import glob
import networkx as nx
from pdb import set_trace

EPI="""The file format for node file is:
node,attr1,attr2
1,0,0
2,0,0
3,0,0
4,0,0
The file format for edge file is:
source,target,Time,Weight,Condition
1,2,0,0,0
2,3,0,0,0
2,4,0,0,0
4,3,0,0,0
4,1,0,0,0
The node and the edge file have levelnumber.node, levelnumber.edge naming convention. 
""" 

class MultiScaleNet:   

    def __init__(self):

        self.name=None
        self.nodes=[]
        self.edges=[]
        self.hierarchy=None
        self.number_of_levels=0    

    def read_from_folder(self,networkFolder):

        self.name=networkFolder

        # Number of levels
        nodeFiles = glob(networkFolder+'/*.nodes')
        edgeFiles = glob(networkFolder+'/*.edges')
        self.number_of_levels=len(nodeFiles)
        if self.number_of_levels != len(edgeFiles):
            raise Exception('Number of node files and number of edge files do not match.')

        # Read nodes
        nodeLevelMapper=pd.DataFrame(columns = {'node': [], 'level': []})
        df_list = []
        for l in range(self.number_of_levels):
            nodeFileName=f'{networkFolder}/{l}.nodes'
            try:
                currentLevelNodes=pd.read_csv(nodeFileName)
                if 'node' not in currentLevelNodes.columns:
                    raise Exception(f"{nodeFileName}: 'node' column should be present in node file.")
                elif currentLevelNodes.node.dtype!=int:
                    raise Exception(f"{nodeFileName}: 'node' should be of 'int' type.")
                self.nodes.append(currentLevelNodes)
            except FileNotFoundError:
                raise  FileNotFoundError(f'Expected file {nodeFileName} is absent.')
            df=self.nodes[l]['node'].to_frame()
            df['level']=l
            df_list.append(df)
        nodeLevelMapper=pd.concat(df_list, ignore_index=True)
        
        #nodeLevelMapper.loc[nodeLevelMapper.shape[0]]=[-1, self.number_of_levels]
        
        # Check if there are any duplicate node ids. That is, ids which occur in 
        # more than one level.
        x=nodeLevelMapper.node.drop_duplicates()
        if x.shape[0]<nodeLevelMapper.shape[0]:
            raise Exception("A node id has been used in multiple levels.")

        nodeLevelMapper = nodeLevelMapper.set_index('node',drop=True).squeeze()
        nodeLevelMapper[-1] = self.number_of_levels
        
        # Read hierarchy and check if hierarchy conditions are met
        self.hierarchy=pd.read_csv(f'{networkFolder}/hierarchy.tree')
        if self.hierarchy.parent.dtype!=int or self.hierarchy.child.dtype!=int:
            raise ValueError("Hierarchy file: All nodes should be integers.")
        levelMappedHierarchy=self.hierarchy.replace(nodeLevelMapper)
        
        if np.less(levelMappedHierarchy.parent,levelMappedHierarchy.child).any():  # Each child and each parents level compare
            raise Exception("A node has a parent at a lower level. Check input.")
        if not nx.is_tree(nx.from_pandas_edgelist(self.hierarchy,'parent','child')):
            raise Exception("The hierachy relationship is not a tree.")

        # Read edges
        for l in range(self.number_of_levels):
            edgeFileName='%s/%d.edges' %(networkFolder,l)
            try:
                x=pd.read_csv(edgeFileName)
                if ('source' and 'target' not in x.columns):
                    raise ValueError('Source and target columns should be present') 
                self.edges.append(x)
            except FileNotFoundError:
                raise  FileNotFoundError('Expected file %s is absent.' %edgeFileName)
            # MS: throw an error if mandatory columns are not present
        self.compute_summary()
   
    def compute_summary(self):
        self.number_of_nodes=[]
        self.number_of_edges=[]
        for l in range(self.number_of_levels):
            self.number_of_nodes.append(self.nodes[l].shape[0])
            self.number_of_edges.append(self.edges[l].shape[0])
        return

    def display_summary(self):
        logging.info(f"Name: {self.name}")
        logging.info(f"Levels: {self.number_of_levels}")
        logging.info(f"Nodes: {self.number_of_nodes}")
        logging.info(f"Edges: {self.number_of_edges}")
        return


if __name__=='__main__':
    # parser
    parser=argparse.ArgumentParser(description=DESC, epilog=EPI,formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("network", help="input network folder which contains (i.nodes,i.edges) for i=0,1,2,... and hierarchy.tree files.")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    net=MultiScaleNet()
    net.read_from_folder(args.network)
    net.display_summary()
