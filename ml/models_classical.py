"""Track A: classical models on the feature CSV, each wrapped in a nested hyper-parameter search.

Every model is an sklearn Pipeline (scaler inside where the model needs it), searched with
GridSearchCV over a small grid. The inner CV splits the *training subjects* of the outer fold
(GroupKFold, 3 splits), scoring = macro-F1. Class imbalance: balanced class weights everywhere.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.utils.class_weight import compute_sample_weight

INNER_SPLITS = 3


class XGBBalanced(ClassifierMixin, BaseEstimator):
    """XGBoost with string labels and balanced sample weights (sklearn-compatible)."""

    def __init__(self, max_depth=6, learning_rate=0.1, n_estimators=300, subsample=0.9, colsample_bytree=0.8):
        self.max_depth, self.learning_rate, self.n_estimators = max_depth, learning_rate, n_estimators
        self.subsample, self.colsample_bytree = subsample, colsample_bytree

    def fit(self, X, y):
        from xgboost import XGBClassifier
        self.le_ = LabelEncoder().fit(y)
        self.classes_ = self.le_.classes_
        self.m_ = XGBClassifier(max_depth=self.max_depth, learning_rate=self.learning_rate,
                                n_estimators=self.n_estimators, subsample=self.subsample,
                                colsample_bytree=self.colsample_bytree, tree_method="hist", n_jobs=1,
                                random_state=0, verbosity=0)
        self.m_.fit(X, self.le_.transform(y), sample_weight=compute_sample_weight("balanced", y))
        return self

    def predict_proba(self, X):
        p = self.m_.predict_proba(X)
        return p if p.ndim == 2 and p.shape[1] == len(self.classes_) else np.column_stack([1 - p, p])

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def _lgbm():
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=300, class_weight="balanced", n_jobs=1, random_state=0, verbose=-1)


MODELS = {
    # name: (estimator factory, grid, complexity rank for the selection rule: lower = simpler)
    "logreg": (lambda: Pipeline([("sc", StandardScaler()), ("m", LogisticRegression(max_iter=3000, class_weight="balanced"))]),
               {"m__C": [0.01, 0.1, 1, 10]}, 1),
    "knn": (lambda: Pipeline([("sc", StandardScaler()), ("m", KNeighborsClassifier(weights="distance"))]),
            {"m__n_neighbors": [5, 15, 31]}, 2),
    "svm_rbf": (lambda: Pipeline([("sc", StandardScaler()), ("m", SVC(kernel="rbf", class_weight="balanced", probability=True, random_state=0))]),
                {"m__C": [1, 10], "m__gamma": ["scale", 0.01]}, 3),
    "rf": (lambda: RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", n_jobs=1, random_state=0),
           {"min_samples_leaf": [1, 3, 8], "max_features": ["sqrt", 0.3]}, 4),
    "extra_trees": (lambda: ExtraTreesClassifier(n_estimators=300, class_weight="balanced", n_jobs=1, random_state=0),
                    {"min_samples_leaf": [1, 3, 8], "max_features": ["sqrt", 0.3]}, 4),
    "hist_gb": (lambda: HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=0),
                {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [15, 31]}, 5),
    "xgboost": (lambda: XGBBalanced(), {"max_depth": [3, 6], "learning_rate": [0.05, 0.1]}, 5),
    "lightgbm": (_lgbm, {"num_leaves": [15, 31], "learning_rate": [0.05, 0.1]}, 5),
}


def make_search_factory(name: str):
    est, grid, _ = MODELS[name]

    def make(train_folds):
        cv = list(GroupKFold(n_splits=INNER_SPLITS).split(np.zeros(len(train_folds)), groups=train_folds))
        return GridSearchCV(est(), grid, scoring="f1_macro", cv=cv, n_jobs=1, refit=True, error_score="raise")
    return make
