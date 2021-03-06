"""
Experiment file for CGExplainer with continuous DAGs pt. I

Compute SAGE and use the (random) orderings in SAGE with d-separation tests based on a true
and an estimated graph (both have to be stored in ~/data/...)

Command line args:
    --data CSV file in folder ~/data/ (string without suffix)
    --model choice between linear model ('lm') and random forest regression ('rf')
    --size slice dataset to df[0:size] (int)
    --runs nr_runs in explainer.sage()
    --orderings nr_orderings in explainer.sage()
    --thresh threshold for convergence detection

"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from rfi.explainers.cgexplainer import CGExplainer
from rfi.explainers.explainer import Explainer
from rfi.samplers.gaussian import GaussianSampler
from rfi.decorrelators.gaussian import NaiveGaussianDecorrelator
import pickle
import time
import argparse


parser = argparse.ArgumentParser(
    description="Experiment to compare SAGE estimation with and without d-separation tests")

parser.add_argument(
    "-d",
    "--data",
    type=str,
    default="dag_s",
    help="Dataset from ~/data/ folder; string with suffix; default: 'dag_s.csv'")

parser.add_argument(
    "-m",
    "--model",
    type=str,
    default="lm",
    help="linear model ('lm') or random forest regression ('rf'); default: 'lm'")

parser.add_argument(
    "-n",
    "--size",
    type=int,
    default=None,
    help="Custom sample size to slice df, default: None",
)

parser.add_argument(
    "-r",
    "--runs",
    type=int,
    default=5,
    help="Number of runs for each SAGE estimation; default: 5",
)

parser.add_argument(
    "-o",
    "--orderings",
    type=int,
    default=20,
    help="Number of orderings; default : 20",
)

parser.add_argument(
    "-t",
    "--thresh",
    type=float,
    default=0.025,
    help="Threshold for convergence detection; default: 0.025",
)

parser.add_argument(
    "-s",
    "--split",
    type=float,
    default=0.2,
    help="Train test split; default: 0.2 (test set size)",
)

parser.add_argument(
    "-rs",
    "--randomseed",
    type=int,
    default=1902,
    help="Numpy random seed; default: 1902",
)

parser.add_argument(
    "-y",
    "--target",
    type=str,
    default="1",
    help="Target variable; default: '1'",
)

arguments = parser.parse_args()

# seed
np.random.seed(arguments.randomseed)


def main(args):

    savepath_true = f"examples/experiments_cg/results/continuous/true_amat/{args.data}"
    savepath_est = f"examples/experiments_cg/results/continuous/est_amat/{args.data}"

    # df to store some metadata
    col_names = ["Data", "Model", "Runtime SAGE", "Runtime SAGE cg (o)",
                 "Runtime SAGE cg", "Runtime SAGE cg (est, o)", "Runtime SAGE cg (est)"]
    metadata = pd.DataFrame(columns=col_names)

    # import and prepare data
    df = pd.read_csv(f"data/{args.data}.csv")
    if args.size is not None:
        df = df[0:args.size]
    col_names = df.columns.tolist()
    col_names.remove(args.target)
    X = df[col_names]
    y = df[args.target]

    # split data for train and test purpose
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.split, random_state=42
    )

    # capture model performance
    col_names = ["data", "model", "target", "MSE", "R2"]
    model_details = pd.DataFrame(columns=col_names)

    # fit model
    if args.model == "lm":
        # fit model
        model = LinearRegression()
        model.fit(X_train, y_train)
        # model evaluation
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        # fill df with info about model
        model_details.loc[len(model_details)] = [args.data, "lin reg", args.target, mse, r2]
        model_details.to_csv(
            f"examples/experiments_cg/results/continuous/true_amat/{args.data}/model_details_lm.csv", index=False
        )
    else:
        # fit model
        model = RandomForestRegressor(n_estimators=100)
        model.fit(X_train, y_train)
        # model evaluation
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        # fill df with info about model
        model_details.loc[len(model_details)] = [args.data, "rf reg", args.target, mse, r2]
        model_details.to_csv(
            f"examples/experiments_cg/results/continuous/true_amat/{args.data}/model_details_rf.csv", index=False
        )

    # load adjacency matrices for CGExplainer
    amat_true = pd.read_csv(f"results_py/true_amat/{args.graph}.csv", index_col=0)
    amat_true.index = amat_true.index.map(str)
    amat_est = pd.read_csv(f"results_py/{args.method}/{args.graph}_{args.size}_obs.csv", index_col=0)
    amat_est.index = amat_est.index.map(str)

    # model prediction linear model
    def model_predict(x):
        return model.predict(x)

    # set up sampler and decorrelator (same for Explainer and CGExplainer)
    sampler = GaussianSampler(X_train)
    decorrelator = NaiveGaussianDecorrelator(X_train)

    # features of interest
    fsoi = X_train.columns

    # SAGE explainer
    wrk = Explainer(model_predict, fsoi, X_train, loss=mean_squared_error, sampler=sampler,
                    decorrelator=decorrelator)

    # NO partial order
    partial_order = [tuple(X_train.columns)]

    # track time with time module
    start_time = time.time()
    ex_d_sage, orderings_sage = wrk.sage(X_test, y_test, partial_order, nr_orderings=args.orderings,
                                         nr_runs=args.runs, detect_convergence=True, thresh=args.thresh)
    time_sage = time.time() - start_time

    # CGExplainer
    wrk_cg_true = CGExplainer(model_predict, fsoi, X_train, amat_true, loss=mean_squared_error,
                              sampler=sampler, decorrelator=decorrelator)

    # CG Sage run with same orderings as SAGE run
    start_time_cg = time.time()
    ex_d_cg, ordering_cg = wrk_cg_true.sage(X_test, y_test, partial_order,
                                            nr_orderings=orderings_sage.shape[0],
                                            nr_runs=args.runs, orderings=orderings_sage)
    time_cg = time.time() - start_time_cg

    # Separate CG SAGE run with convergence detection
    start_time_cg_cd = time.time()
    ex_d_cg_cd, orderings_cg_cd = wrk_cg_true.sage(X_test, y_test, partial_order, nr_runs=args.runs,
                                                   nr_orderings=args.orderings, detect_convergence=True,
                                                   thresh=args.thresh)
    time_cg_cd = time.time() - start_time_cg_cd

    # CGExplainer (with estimated amat)
    wrk_cg_est = CGExplainer(model_predict, fsoi, X_train, amat_est, loss=mean_squared_error,
                             sampler=sampler, decorrelator=decorrelator)

    # CG Sage run with same orderings as SAGE run
    start_time_cg_est = time.time()
    ex_d_cg_est, ordering_cg_est = wrk_cg_est.sage(X_test, y_test, partial_order,
                                                   nr_orderings=orderings_sage.shape[0],
                                                   nr_runs=args.runs, orderings=orderings_sage)
    time_cg_est = time.time() - start_time_cg_est

    # Separate CG SAGE run with convergence detection
    start_time_cg_cd_est = time.time()
    ex_d_cg_cd_est, orderings_cg_cd_est = wrk_cg_est.sage(X_test, y_test, partial_order, nr_runs=args.runs,
                                                          nr_orderings=args.orderings, detect_convergence=True,
                                                          thresh=args.thresh)
    time_cg_cd_est = time.time() - start_time_cg_cd_est

    # save  orderings
    orderings_sage.to_csv(f'{savepath_true}/order_sage_{args.data}_{args.model}.csv')
    orderings_cg_cd.to_csv(f'{savepath_true}/order_cg_cd_{args.data}_{args.model}.csv')
    orderings_cg_cd_est.to_csv(f'{savepath_est}/order_cg_cd_{args.data}_{args.model}.csv')

    # save the SAGE/cg values for every ordering (Note: not split by runs anymore)
    sage_values_ordering = ex_d_sage.scores.mean(level=0)
    sage_values_ordering.to_csv(f"{savepath_true}/sage_o_{args.data}_{args.model}.csv")
    cg_values = ex_d_cg.scores.mean(level=0)
    cg_values.to_csv(f"{savepath_true}/cg_o_{args.data}_{args.model}.csv")
    cg_cd_values = ex_d_cg_cd.scores.mean(level=0)
    cg_cd_values.to_csv(f"{savepath_true}/cg_cd_o_{args.data}_{args.model}.csv")
    cg_values_est = ex_d_cg_est.scores.mean(level=0)
    cg_values_est.to_csv(f"{savepath_est}/cg_o_{args.data}_{args.model}.csv")
    cg_cd_values_est = ex_d_cg_cd_est.scores.mean(level=0)
    cg_cd_values_est.to_csv(f"{savepath_est}/cg_cd_o_{args.data}_{args.model}.csv")

    # fi_values for the runs
    ex_d_sage.fi_vals().to_csv(f"{savepath_true}/sage_r_{args.data}_{args.model}.csv")
    ex_d_cg.fi_vals().to_csv(f"{savepath_true}/cg_r_{args.data}_{args.model}.csv")
    ex_d_cg_cd.fi_vals().to_csv(f"{savepath_true}/cg_cd_r_{args.data}_{args.model}.csv")
    ex_d_cg_est.fi_vals().to_csv(f"{savepath_est}/cg_r_{args.data}_{args.model}.csv")
    ex_d_cg_cd_est.fi_vals().to_csv(f"{savepath_est}/cg_cd_r_{args.data}_{args.model}.csv")

    # fi_mean values across runs + stds
    ex_d_sage.fi_means_stds().to_csv(f"{savepath_true}/sage_{args.data}_{args.model}.csv")
    ex_d_cg.fi_means_stds().to_csv(f"{savepath_true}/cg_{args.data}_{args.model}.csv")
    ex_d_cg_cd.fi_means_stds().to_csv(f"{savepath_true}/cg_cd_{args.data}_{args.model}.csv")
    ex_d_cg_est.fi_means_stds().to_csv(f"{savepath_est}/cg_{args.data}_{args.model}.csv")
    ex_d_cg_cd_est.fi_means_stds().to_csv(f"{savepath_est}/cg_cd_{args.data}_{args.model}.csv")

    content = [args.data, args.model, time_sage, time_cg, time_cg_cd, time_cg_est, time_cg_cd_est]
    # fill evaluation table with current run
    metadata.loc[len(metadata)] = content
    metadata.to_csv(f"{savepath_true}/metadata_{args.data}_{args.model}.csv", index=False)


if __name__ == "__main__":
    main(arguments)
