# -*-coding:utf-8 -*-
"""
@Time    :   2024/07/14 11:17:24
@Author  :   Daniel Persaud
@Version :   1.0
@Contact :   da.persaud@mail.utoronto.ca
@Desc    :
"""
# %%
# IMPORT DEPENDENCIES------------------------------------------------------------------------------
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import numpy.matlib as nm
import pandas as pd
from pyro import param
import seaborn as sns
from baybe import Campaign
from baybe.constraints import DiscreteSumConstraint, ThresholdCondition
from baybe.objectives import SingleTargetObjective
from baybe.parameters import NumericalDiscreteParameter, TaskParameter
from baybe.searchspace import SearchSpace
from baybe.searchspace import SubspaceDiscrete
from baybe.simulation import simulate_scenarios
from baybe.targets import NumericalTarget
from baybe.utils.botorch_wrapper import botorch_function_wrapper
from baybe.utils.plotting import create_example_plots
from botorch.test_functions.synthetic import Hartmann
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ExpSineSquared

# import linear regression model
from sklearn.linear_model import LinearRegression

from pltTernary import pltTernary


#%%
# LOAD DATA----------------------------------------------------------------------------------------

# get the path to the directory before the current directory
strHomeDir = os.path.dirname(os.getcwd())

dfMP = pd.read_csv(
    os.path.join(strHomeDir, "data", "processed", "mp_bulkModulus_goodOverlap.csv"), index_col=0
)

# add a column to dfMP called 'load' and set all values to 1
dfMP["load"] = 1

dfExp = pd.read_csv(
    os.path.join(strHomeDir, "data", "processed", "exp_hardness_goodOverlap.csv"), index_col=0
)

lstElementCols = dfExp.columns.to_list()[4:]

#%%
# CLEAN DATA---------------------------------------------------------------------------------------

# make a dataframe for the task function (hardness) - dfExp [element columns, load]
dfSearchSpace_task = dfExp[lstElementCols + ["load"]]
# add a column to dfSearchSpace_task called 'Function' and set all values to 'taskFunction'
dfSearchSpace_task["Function"] = "taskFunction"

# make a lookup table for the task function (hardness) - add the 'hardness' column from dfExp to dfSearchSpace_task
dfLookupTable_task = pd.concat([dfSearchSpace_task, dfExp["hardness"]], axis=1)
# make the 'hardness' column the 'Target' column
dfLookupTable_task = dfLookupTable_task.rename(columns={"hardness": "Target"})

# make a dataframe for the source function (voigt bulk modulus) - dfMP [element columns, load]
dfSearchSpace_source = dfMP[lstElementCols + ["load"]]
# add a column to dfSearchSpace_source called 'Function' and set all values to 'sourceFunction'
dfSearchSpace_source["Function"] = "sourceFunction"

# make a lookup table for the source function (voigt bulk modulus) - add the 'vrh' column from dfMP to dfSearchSpace_source
dfLookupTable_source = pd.concat([dfSearchSpace_source, dfMP["vrh"]], axis=1)
# make the 'vrh' column the 'Target' column
dfLookupTable_source = dfLookupTable_source.rename(columns={"vrh": "Target"})

# concatenate the two dataframes
dfSearchSpace = pd.concat([dfSearchSpace_task, dfSearchSpace_source])

#%%
# GENERATE THE SEARCH SPACE------------------------------------------------------------------------

lstParameters = []

# for each column in dfSearchSpace except the last one, create a NumericalDiscreteParameter
for strCol_temp in dfSearchSpace.columns[:-1]:
    # create a NumericalDiscreteParameter
    parameter = NumericalDiscreteParameter(
        name=strCol_temp,
        values=np.unique(dfSearchSpace[strCol_temp]),
        tolerance=0.0,
    )
    # append the parameter to the list of parameters
    lstParameters.append(parameter)

# create a TaskParameter
taskParameter = TaskParameter(
    name="Function",
    values=["taskFunction", "sourceFunction"],
    active_values=["taskFunction"],
)

# append the taskParameter to the list of parameters
lstParameters.append(taskParameter)

# create the search space
searchspace = SearchSpace.from_dataframe(dfSearchSpace, parameters=lstParameters)

#%%
# CREATE OPTIMIZATION OBJECTIVE--------------------------------------------------------------------
"""
the test functions have a single output (voigt bulk modulus and hardness) that is to be maximized
"""

objective = SingleTargetObjective(target=NumericalTarget(name="Target", mode="MAX"))

#%%
# SIMULATE SCENARIOS-------------------------------------------------------------------------------
'''
use the simulate_scenarios function to simulate the optimization process
'''

N_MC_ITERATIONS = 10
N_DOE_ITERATIONS = 10
BATCH_SIZE = 1

results: list[pd.DataFrame] = []
for n in (5, 15, 30):
    campaign = Campaign(searchspace=searchspace, objective=objective)
    initial_data = [dfLookupTable_source.sample(n) for _ in range(N_MC_ITERATIONS)] # frac = p
    result_fraction = simulate_scenarios(
        {f"{n}": campaign},                                                # int(100*p)
        dfLookupTable_task,
        initial_data=initial_data,
        batch_size=BATCH_SIZE,
        n_doe_iterations=N_DOE_ITERATIONS,
    )
    results.append(result_fraction)

# For comparison, we also optimize the function without using any initial data:

result_baseline = simulate_scenarios(
    {"0": Campaign(searchspace=searchspace, objective=objective)},
    dfLookupTable_task,
    batch_size=BATCH_SIZE,
    n_doe_iterations=N_DOE_ITERATIONS,
    n_mc_iterations=N_MC_ITERATIONS,
)
results = pd.concat([result_baseline, *results])

# All that remains is to visualize the results.
# As the example shows, the optimization speed can be significantly increased by
# using even small amounts of training data from related optimization tasks.

results.rename(columns={"Scenario": "Number of data used"}, inplace=True)
ax = sns.lineplot(
    data=results,
    marker="o",
    markersize=10,
    x="Num_Experiments",
    y="Target_CumBest",
    hue="Number of data used",
)
create_example_plots(ax=ax,
                     base_name="multiTask-v2",
                     path=os.path.join(strHomeDir, "reports", "figures"))

# add random and max

# # downselect the dataframes to only include the best combination
# dfMP = dfMP.loc[lstId_mp]
# dfExp = dfExp.loc[lstId_exp]

# # -----MP-----
# # initialize a list to store the columns with all zeros
# lstZeroCols_mp = []
# # initialize a list to store the columns with non-zero values
# lstNonZeroCols_mp = []

# for strCol_temp in lstElementCols:
#     if dfMP[strCol_temp].sum() == 0:
#         lstZeroCols_mp.append(strCol_temp)
#     else:
#         lstNonZeroCols_mp.append(strCol_temp)

# # drop the columns with all zeros
# dfMP.drop(columns=lstZeroCols_mp, inplace=True)

# # -----EXP-----
# # initialize a list to store the columns with all zeros
# lstZeroCols_exp = []
# # initialize a list to store the columns with non-zero values
# lstNonZeroCols_exp = []
# for strCol_temp in lstElementCols:
#     if dfExp[strCol_temp].sum() == 0:
#         lstZeroCols_exp.append(strCol_temp)
#     else:
#         lstNonZeroCols_exp.append(strCol_temp)

# # drop the columns with all zeros
# dfExp.drop(columns=lstZeroCols_exp, inplace=True)

# # %%
# # PLOT THE DATA-------------------------------------------------------------------------------------

# # -----MP-----

# pltTernary(
#     dfCompositionData=dfMP[lstNonZeroCols_mp] * 100,
#     lstElements=lstNonZeroCols_mp,
#     srColor=dfMP["voigt"],
#     strColorBarLabel="Voigt Bulk Modulus",
#     strTitle="MP Data",
#     intMarkerSize=100,
#     strSavePath=os.path.join(strHomeDir, "reports", "figures", "mpData.png"),

# )

# # -----EXP-----
# pltTernary(
#     dfCompositionData=dfExp[lstNonZeroCols_exp] * 100,
#     lstElements=lstNonZeroCols_exp,
#     srColor=dfExp["hardness"],
#     strColorBarLabel="Hardness",
#     strTitle="EXP Data",
#     intMarkerSize=100,
#     strSavePath=os.path.join(strHomeDir, "reports", "figures", "expData.png"),
# )


# # %%
# # TRAIN A GAUSSIAN PROCESS REGRESSOR---------------------------------------------------------------
# """
# the Gaussian Process Regressor is trained on the MP data to predict the voigt bulk modulus and
# another one is trained on the Exp data to predict the hardness. Each model will then be used to
# predict the the same values for a more filled in grid of the elements. These predictions will be
# used to generate the lookup tables for the test functions. (ie. the test functions will be the
# ground truth values of the voigt bulk modulus and hardness)
# """

# # make a grid of test points (0 to 1 with steps of 0.02 for each element in lstNonZeroCols_exp)
# lstTestPoints = np.meshgrid(*[np.arange(0, 1.02, 0.02) for _ in lstNonZeroCols_exp])
# # make a dataframe of the test points
# dfX_test_mp = pd.DataFrame(
#     {
#         strElement: lstTestPoints[idx].ravel()
#         for idx, strElement in enumerate(lstNonZeroCols_exp)
#     }
# )
# # round the values to 2 decimal places
# dfX_test_mp = dfX_test_mp.round(2)
# # remove rows where the sum of the row is not equal to 1
# dfX_test_mp = dfX_test_mp[np.isclose(dfX_test_mp.sum(axis=1), 1, atol=1e-3)]
# # sort dfX_test_mp by the columns
# dfX_test_mp = dfX_test_mp.sort_values(by=lstNonZeroCols_exp)
# # reset the index
# dfX_test_mp.reset_index(drop=True, inplace=True)

# # make a dataframe of the test points
# dfX_test_exp = pd.DataFrame(
#     {
#         strElement: lstTestPoints[idx].ravel()
#         for idx, strElement in enumerate(lstNonZeroCols_exp)
#     }
# )
# # round the values to 2 decimal places
# dfX_test_exp = dfX_test_exp.round(2)
# # remove rows where the sum of the row is not equal to 1
# dfX_test_exp = dfX_test_exp[np.isclose(dfX_test_exp.sum(axis=1), 1, atol=1e-3)]
# # sort dfX_test_exp by the columns
# dfX_test_exp = dfX_test_exp.sort_values(by=lstNonZeroCols_exp)
# # reset the index
# dfX_test_exp.reset_index(drop=True, inplace=True)


# # train the Gaussian Process Regressor on the MP data

# gp_mp = LinearRegression()
# gp_mp.fit(dfMP[lstNonZeroCols_exp], dfMP["voigt"])

# # train the Gaussian Process Regressor on the EXP data
# gp_exp = LinearRegression()
# gp_exp.fit(dfExp[lstNonZeroCols_exp], dfExp["hardness"])

# # predict the voigt bulk modulus and make it a series
# srY_test_mp = pd.Series(gp_mp.predict(dfX_test_mp), name="voigt")
# # predict the hardness and make it a series
# srY_test_exp = pd.Series(gp_exp.predict(dfX_test_exp), name="hardness")

# # -----PLOT THE PREDICTIONS-----

# # -----MP-----
# pltTernary(
#     dfCompositionData=dfX_test_mp * 100,
#     lstElements=lstNonZeroCols_exp,
#     srColor=srY_test_mp,
#     strColorBarLabel="Voigt Bulk Modulus",
#     strTitle="LR Voigt Bulk Modulus",
#     intMarkerSize=100,
#     strSavePath=os.path.join(strHomeDir, "reports", "figures", "mpPredictions.png"),
# )

# # -----EXP-----
# pltTernary(
#     dfCompositionData=dfX_test_exp * 100,
#     lstElements=lstNonZeroCols_exp,
#     srColor=srY_test_exp,
#     strColorBarLabel="Hardness",
#     strTitle="LR Hardness",
#     intMarkerSize=100,
#     strSavePath=os.path.join(strHomeDir, "reports", "figures", "expPredictions.png"),
# )


# # %%
# # GENERATE LOOKUP TABLES---------------------------------------------------------------------------
# """
# the lookup tables are generated from the predictions of the Gaussian Process Regressors
# """

# # -----MP-----
# lookup_training_task = pd.concat([dfX_test_mp.round(2), srY_test_mp], axis=1)
# lookup_training_task["Function"] = "Training_Function"
# # change voigt to target
# lookup_training_task = lookup_training_task.rename(columns={"voigt": "Target"})
# # cast everything in the Target column to float
# lookup_training_task["Target"] = lookup_training_task["Target"].astype(float)

# # -----EXP-----
# lookup_test_task = pd.concat([dfX_test_exp.round(2), srY_test_exp], axis=1)
# lookup_test_task["Function"] = "Test_Function"
# # change hardness to target
# lookup_test_task = lookup_test_task.rename(columns={"hardness": "Target"})
# # cast everything in the Target column to float
# lookup_test_task["Target"] = lookup_test_task["Target"].astype(float)


# # %%
# # CREATE OPTIMIZATION OBJECTIVE--------------------------------------------------------------------
# """
# the test functions have a single output (voigt bulk modulus and hardness) that is to be maximized
# """

# objective = SingleTargetObjective(target=NumericalTarget(name="Target", mode="MAX"))

# # %%
# # CREATE SEARCH SPACE-------------------------------------------------------------------------------
# """
# the bounds of the search space are dictated by the upper and lower bounds of each of the elements
# """

# lstContinuousParameters = [
#     NumericalDiscreteParameter(
#         name=f"{strElement}",
#         values=np.arange(0, 1.02, 0.02).round(2),
#     )
#     for strElement in ['a', 'b', 'c']#lstNonZeroCols_exp
# ]

# SumConstraint = [
#     DiscreteSumConstraint(
#         parameters=['a', 'b', 'c'],#lstNonZeroCols_exp,
#         condition=ThresholdCondition(  # set condition that should apply to the sum
#             threshold=1.0,
#             operator="=",
#             tolerance=0.001,  # optional; here, everything between 0.999 and 1.001 would also be considered valid
#         ),
#     )
# ]

# taskParameters = TaskParameter(
#     name="Function",
#     values=["Test_Function", "Training_Function"],
#     active_values=["Test_Function"],
# )

# lstParameters = [*lstContinuousParameters, taskParameters]

# searchspace = SearchSpace.from_product(
#     parameters=lstParameters, constraints=SumConstraint
# )

# # %%

# N_MC_ITERATIONS = 10
# N_DOE_ITERATIONS = 10
# BATCH_SIZE = 1

# results: list[pd.DataFrame] = []
# for p in (0.01, 0.05, 0.1):
#     campaign = Campaign(searchspace=searchspace, objective=objective)
#     initial_data = [lookup_training_task.sample(frac=p) for _ in range(N_MC_ITERATIONS)]
#     result_fraction = simulate_scenarios(
#         {f"{int(100*p)}": campaign},
#         lookup_test_task,
#         initial_data=initial_data,
#         batch_size=BATCH_SIZE,
#         n_doe_iterations=N_DOE_ITERATIONS,
#     )
#     results.append(result_fraction)

# # For comparison, we also optimize the function without using any initial data:

# result_baseline = simulate_scenarios(
#     {"0": Campaign(searchspace=searchspace, objective=objective)},
#     lookup_test_task,
#     batch_size=BATCH_SIZE,
#     n_doe_iterations=N_DOE_ITERATIONS,
#     n_mc_iterations=N_MC_ITERATIONS,
# )
# results = pd.concat([result_baseline, *results])

# # All that remains is to visualize the results.
# # As the example shows, the optimization speed can be significantly increased by
# # using even small amounts of training data from related optimization tasks.

# results.rename(columns={"Scenario": "% of data used"}, inplace=True)
# ax = sns.lineplot(
#     data=results,
#     marker="o",
#     markersize=10,
#     x="Num_Experiments",
#     y="Target_CumBest",
#     hue="% of data used",
# )
# create_example_plots(ax=ax,
#                      base_name="multitask learning",
#                      path=os.path.join(strHomeDir, "reports", "figures"))

# # %%

dfLookupTable_task
# %%
