from gurobipy import *

def gurobi_solver_MCLP(users, facilities, demand, PN, A):
    # Problem datas
    N = len(users)
    M = len(facilities)

    model = Model('MCLP')
    model.setParam('OutputFlag', False)  # 禁止输出求解过程的详细信息。
    model.setParam('MIPFocus', 2)  # 设置模型求解的重点为探索可行解空间。
    # Add variables
    client_var = {}
    serv_var = {}

    # 通过循环为每个用户创建一个决策变量，并将其添加到模型中。
    for j in range(N):
        client_var[j] = model.addVar(vtype="B", name="y(%s)"%j)
    # 通过循环为每个设施创建一个决策变量，并将其添加到模型中。
    for i in range(M):
        serv_var[i] = model.addVar(vtype="B", name="x(%s)"%i)
    # Update Model Variables
    model.update()
    #  设置模型的目标函数，其中按需求的加权和来最大化模型的目标。
    model.setObjective(quicksum(demand[j]*client_var[j] for j in range(N)), GRB.MAXIMIZE)
    #     Add Constraints
    # 通过循环为每个用户添加覆盖约束，确保至少有一个设施覆盖该用户。
    for j in range(N):
        model.addConstr(quicksum (A[i,j]*serv_var[i] for i in range(M)) - client_var[j] >= 0,
                        'Coverage_Constraint_%d' % j)

    # 添加设施约束，确保选择的设施数量等于给定的 PN 值。
    model.addConstr(quicksum(serv_var[i] for i in range(M)) == PN,
                "Facility_Constraint")
    # 对模型进行求解。
    model.optimize()

    # 通过循环将最优解中的设施和用户的决策变量值分别存储在结果列表 x_result 和 y_result 中。
    x_result = []
    for i in range(M):
        x_result.append(serv_var[i].X)
    y_result = []
    for j in range(N):
        y_result.append(client_var[j].X)
    # 获取模型的最优解值。
    obj = model.ObjVal
    return x_result, y_result, obj  # 返回最优解的设施列表、用户列表和模型的最优解值。

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# %%time
ls = gpd.read_file("./data/Chicago/demandsTY.shp")
ls['POINT_X'] = ls.geometry.x
ls['POINT_Y'] = ls.geometry.y
ls.head(3)
total_pop = sum(ls['RASTERVALU'])
# total_pop = sum(ls['value'])
print("The number of records is ", len(ls))
print("The total speed unit are ", total_pop)
print(ls['POINT_X'])

sitedf = gpd.read_file("./data/Chicago/candidatesClip.shp")
sitedf['POINT_X'] = sitedf.geometry.x
sitedf['POINT_Y'] = sitedf.geometry.y
# sites = np.array(sitedf[['NORM_X', 'NORM_Y']], dtype=np.float64)
print("The number of bicycle stations is ", len(sitedf))

def Normalization(x, y):
    max_x, max_y = np.max(x), np.max(y)
    min_x, min_y = np.min(x), np.min(y)
    S_x = (max_x-min_x)
    S_y = (max_y-min_y)
    S = max(S_x, S_y)
    new_x, new_y = (x-min_x)/S, (y-min_y)/S
    data_xy = np.vstack((new_x, new_y))
    Data = data_xy.T
    return new_x, new_y, S

ls_X = np.array(ls['POINT_X'])
ls_Y = np.array(ls['POINT_Y'])
bbs_X = np.array(sitedf['POINT_X'])
bbs_Y = np.array(sitedf['POINT_Y'])
X = np.concatenate([ls_X, bbs_X])
Y = np.concatenate([ls_Y, bbs_Y])
NORM_X, NORM_Y, S = Normalization(X, Y)
ls['NORM_X'] = NORM_X[:len(ls)]
ls['NORM_Y'] = NORM_Y[:len(ls)]
sitedf['NORM_X'] = NORM_X[len(ls):]
sitedf['NORM_Y'] = NORM_Y[len(ls):]

sitedf.head(3)



def generate_candidate_sites(sites, M=100, heuristic = None):
    '''
    Generate M candidate sites with the convex hull of a point set
    Input:
        sites: a Pandas DataFrame with X, Y and other characteristic
        M: the number of candidate sites to generate
        heuristic:
    Return:
        sites: a Numpy array with shape of (M,2)
    '''
    if M is not None:
        if M > len(sites):
            M = None
    if heuristic is None or heuristic == '':
        if M is None:
            return sites
        index = np.random.choice(len(sites), M)
        return sites.iloc[index]
    elif heuristic == 'coverage':
        sites = sites.sort_values(by='pop_covered_2km', ascending=False).reset_index()
        if M is None:
            return sites
        return sites.iloc[:M]
    elif heuristic == 'coverage_e':
        sites = sites.sort_values(by='pop_covered_2km_exclusive', ascending=False).reset_index()
        if M is None:
            return sites
        return sites.iloc[:M]
    elif heuristic == 'impression':
        sites = sites.sort_values(by='weeklyImpr', ascending=False).reset_index()
        if M is None:
            return sites
        return sites.iloc[:M]
    elif heuristic == 'impression_e':
        sites = sites.sort_values(by='weeklyImpr_2km_exclusive', ascending=False).reset_index()
        if M is None:
            return sites
        return sites.iloc[:M]



np.random.seed()
bbs_ = generate_candidate_sites(sitedf, M=None, heuristic="")
users = np.array(ls[['NORM_X', 'NORM_Y']])
facilities = np.array(bbs_[['NORM_X', 'NORM_Y']])
# demand = np.array(ls['speed_pct_freeflow_rev_norm'])
demand = np.array(ls['RASTERVALU'])

# print(facilities)

p = 50
real_radius = 800
radius = real_radius/S
A = np.sum((facilities[:, np.newaxis, :] - users[np.newaxis, :, :]) ** 2, axis=-1) ** 0.5
mask1 = A <= radius
A[mask1] = 1
A[~mask1] = 0

x_result, y_result, obj = gurobi_solver_MCLP(users, facilities, demand, p, A)
print(f"The avg objective of MCLP samples is: {obj}")
solutions = []
for i in range(len(sitedf)):
    if x_result[i] == 1.0:
        solutions.append(i)
solutions

print(solutions)