# TODO for later if more time left, but conversion of pd.DataFrame to xgb.DMatrix might conflict
# with SAGE implementation
"""Fit random xgboost for regression to data, simple template used in CG SAGE project"""
import xgboost as xgb
import pickle
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import sys
import os
import inspect


current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)


from functions import create_folder

# create folder to store models
create_folder("fitted_models/")

names = ["dag_s", "dag_m", "dag_l"]

col_names = ["data", "model", "target", "mse", "R2"]
rfreg_details = pd.DataFrame(columns=col_names)

# read data
for i in names:

    df = pd.read_csv(f"data/{i}/{i}_train.csv")
    col_names = df.columns.tolist()
    # We use "V1" as target, since we randomly sampled edges, this is w.l.o.g. a target at a random
    # position in the graph
    col_names.remove("1")
    X = df[col_names]
    y = df["1"]

    # standard train test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.1, random_state=42
    )

    # fit model
    rf = RandomForestRegressor(n_estimators=1000)
    rf.fit(X_train, y_train)

    y_pred = rf.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # fill df with info about model
    rfreg_details.loc[len(rfreg_details)] = [i, "rf reg", "1", mse, r2]

    # save model
    filename = f"fitted_models/{i}_rf.sav"
    pickle.dump(rf, open(filename, "wb"))

rfreg_details.to_csv(
    "fitted_models/rfreg_details.csv", index=False
)