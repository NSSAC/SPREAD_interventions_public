'''
Fill gaps in intervention solutions by a rank-based approach.

AA
'''

import os
from glob import glob
import pandas as pd
from pdb import set_trace

# Step 1: Collect all intervention files
files = glob('interventions/**/comp_I*csv', recursive=True)

if not files:
    print("No intervention files found. Please check the directory and file naming pattern.")
    exit()

# Step 2: Read each file, add columns for file path and parent folder
all_dfs = []
for file in files:
    tdf = pd.read_csv(file)
    tdf['file_path'] = file
    parent = os.path.dirname(file)
    tdf['parent'] = parent + '/'

    # Step 3: Parse filename to extract delay and budget
    fname = os.path.basename(file)
    # Expected format: comp_I3-B4.csv
    parts = fname.replace('comp_I', '').replace('.csv', '').split('-')
    delay = int(parts[0])
    budget = int(parts[1].replace('B', ''))
    tdf['delay'] = delay
    tdf['budget'] = budget

    # Step 4: Compute score as val / budget
    tdf['score'] = tdf['val'] / tdf['budget']

    all_dfs.append(tdf)

# Combine all dataframes
df = pd.concat(all_dfs, ignore_index=True)

# Step 5: Create idf by grouping by parent and delay, summing scores for each group
idf = df.groupby(['parent', 'delay', 'group'], as_index=False)['score'].sum()

# Step 6: Create ossdf by grouping by parent, delay, and budget, summing intervene as sol_size
ossdf = df.groupby(['parent', 'delay', 'budget'], as_index=False)['intervene'].sum()
ossdf.rename(columns={'intervene': 'sol_size'}, inplace=True)

# Step 7: For each unique (parent, delay, budget)
for (parent, delay, budget) in ossdf[['parent', 'delay', 'budget']].drop_duplicates().values:
    # Find row in ossdf with highest sol_size <= budget
    subset = ossdf[(ossdf['parent'] == parent) & (ossdf['delay'] == delay) & (ossdf['sol_size'] <= budget)]
    if subset.empty:
        best_budget = 0
    else:
        best_budget = subset.sort_values('sol_size', ascending=False).iloc[0]['budget']

    # Build initial solution from corresponding groups in df
    sol_df = df[(df['parent'] == parent) & (df['delay'] == delay) & (df['budget'] == best_budget)]
    sol_groups = set(sol_df[sol_df.intervene==1].group) if not sol_df.empty else set()

    # Fill remaining budget
    remaining = budget - len(sol_groups)
    if remaining > 0:
        # Get candidates from idf not in sol_groups, sorted by score descending
        candidates = idf[(idf['parent'] == parent) & (idf['delay'] == delay) & (~idf['group'].isin(sol_groups))]
        candidates = candidates.sort_values('score', ascending=False)
        add_groups = []
        for g in candidates['group']:
            if remaining <= 0:
                break
            add_groups.append(g)
            remaining -= 1  # Assuming each group costs 1 unit
        sol_groups.update(add_groups)

    # Prepare final solution dataframe
    final_df = pd.DataFrame({'group': list(sol_groups), 'time': delay})

    # Save to new file
    out_path = os.path.join(parent, f'new_I{delay}-B{budget}.csv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    set_trace()
    final_df.to_csv(out_path, index=False)

print("Rank-based intervention solutions have been generated and saved.")


# collect all intervention files
xx = glob('interventions/**/comp_I*csv')
set_trace()

# read each file, add a column for file path, concat to df. Each file has group,val,intervene as columns

# separate parent folder from file path and assign to a new column parent

# files are of the form comp_I3-B4.csv, parse to set new column delay=3 and budget=4

# create a column called score by dividing val by budget

# groupby parent and delay, selecting only columns group and score, sum score. this fill be called idf.

# groupby parent, delay and budget, and sum intervene, and call the column sol_size. call this ossdf (original solution size df)

# for each unique (parent, delay, budget) do the following

### find the row in ossdf with the highest sol_size <= budget, say budget_

### now build solution by first inheriting the groups corresponding this (parent, delay, budget_) in df. Handle empty by making empty list

### suppose sol is this set. fill gap of budget-budget_ by adding nodes that are not in this set by adding nodes in idf that not present in sol in descending order.

### save this as new_I3-B4.csv in the parent folder with columns group,delay(renamed as time)