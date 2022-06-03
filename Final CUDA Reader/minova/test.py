from sklearn.model_selection import train_test_split
import pickle
from compress_pickle import load,dump
import matplotlib.pyplot as plt
from preprocess import smooth,timeseries_to_axis,reject_outliers,extract_timepionts
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from sklearn.metrics import precision_score, recall_score
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib
from sklearn.model_selection import cross_val_score,StratifiedKFold
from sklearn.base import clone


#positive = r"C:\Users\Hui\CloudStation\R&D\Users\Hui Kang\echem Data\positiveExport.picklez"
#negative = r"C:\Users\Hui\CloudStation\R&D\Users\Hui Kang\echem Data\negativeExport.picklez"
positive = "/Users/hui/Aptitude_Cloud/Aptitude Users/R&D/Users/Hui Kang/echem Data/positiveExport.picklez"
negative = "/Users/hui/Aptitude_Cloud/Aptitude Users/R&D/Users/Hui Kang/echem Data/negativeExport.picklez"
positive = '/Users/hui/Cloudstation/R&D/Users/Hui Kang/echem Data/positiveExport.picklez'
negative = '/Users/hui/Cloudstation/R&D/Users/Hui Kang/echem Data/negativeExport.picklez'


p = load(open(positive,'rb'),compression='gzip')
n = load(open(negative,'rb'),compression='gzip')


def plot_curves(data):
    fig,ax = plt.subplots()
    for i,(d) in enumerate(data):
        ax.plot(d,label=f"{i}")
    ax.set_ylim([0,25])
    # ax.legend()
    plt.show()
    


def normalize(row):
    return row/np.max(row)
    
def traceProcessPipe(
        outlier_para={"stddev":2,},
        smooth_para={"windowlenth":11,"window":'hanning'},
        extractTP_para={"cutoff":60,"n":150}):
    """
    process the [time,pc] data and 
    return the processed value to be used for prediction
    """
    def pipe(row):
        t,pc = row
        t,pc = reject_outliers(t,pc,**outlier_para)
        pc = smooth(pc,**smooth_para)
        row = extract_timepionts(t,pc,**extractTP_para)
        row = normalize(row)
        return row
    return pipe

class MyTransformer(BaseEstimator,TransformerMixin):
    def __init__(self,**params):
        self.params=params
        self.scaler = StandardScaler()
        
    def fit(self,X,y=None):
        smoothed = np.apply_along_axis(traceProcessPipe(**self.params),1,X,)
        self.scaler.fit(smoothed)
        return self
    def transform(self,X,y=None):
        "transform my data."
        smoothed = np.apply_along_axis(traceProcessPipe(**self.params),1,X,)
        return self.scaler.transform(smoothed)

class SmoothTransformer(BaseEstimator,TransformerMixin):
    def __init__(self,**params):
        self.params=params        
    def fit(self,X,y=None):
        return self 
    def transform(self,X,y=None):
        "transform my data."
        return np.apply_along_axis(traceProcessPipe(**self.params),1,X,)


pd,pm = getDataFromPicklez(p)
nd,nm = getDataFromPicklez(n)
len(nd)
X = np.array(pd+nd)
y = np.array(pm+nm)
X_train, X_test, y_train, y_test = train_test_split(X,y, test_size=0.2, random_state=2)
y.sum()
len(y)

svm_clf = Pipeline([
('my transform', SmoothTransformer()),
('scaler',StandardScaler()),
("linear_svc", LinearSVC(max_iter=10000)), ])

Xt = MyTransformer().transform(X)

stdscalar = StandardScaler()

stdscalar.fit(X_train)

Xt_scale = stdscalar.transform(Xt)

for row1,row2 in zip(Xt[54:,:],Xt_scale[54:,:]):
    plt.plot(row1)
    plt.plot(row2)
    plt.show()

for row in Xt_scale[0:53,:]:
    plt.plot(row)

cross_val_score(svm_clf,X,y,cv=5,scoring='precision',)
cross_val_score(svm_clf,X,y,cv=5,scoring='recall',)

# kfold cross-validation.
skfold = StratifiedKFold(n_splits=5,random_state=42, shuffle=True )
for train_idx, test_idx in skfold.split(X,y):
    cloneclf = clone(svm_clf)
    X_train_fold = X[train_idx]
    y_train_fold = y[train_idx]
    X_test_fold = X[test_idx]
    y_test_fold = y[test_idx]
    cloneclf.fit(X_train_fold,y_train_fold)    
    print("precision: ",precision_score(y_test_fold,cloneclf.predict(X_test_fold),))
    print("recall: ", recall_score(y_test_fold,cloneclf.predict(X_test_fold),))


transformerr = Pipeline([
('data_smoother',MyTransformer()),
('scaler',StandardScaler())
])

svm_clf = Pipeline([
('transform',transformerr),
("linear_svc", LinearSVC(C=1, loss="hinge",max_iter=100000))
])


transformerr.fit(X)
svm_clf.fit(X,y)

X_t1 = svm_clf[0:-1].transform(X)

X_t = transformerr.transform(X)

for i in X_t1[60:]:
    plt.plot(i)

for i in X_t[60:]:
    plt.plot(i)

for i in X_t[0:20]:
    plt.plot(i)



svm_clf.fit(X_train,y_train)

y

svm_clf.predict(X)

svm_clf


y_test
svm_clf.predict(X_test)

joblib.dump(svm_clf,'svm_clf.joblib')

new = joblib.load('svm_clf.model')

joblib.dump(new,'svm_clf.joblib')

import utils


test = joblib.load('/Users/hui/Cloudstation/R&D/Users/Hui Kang/echem Data/smoothSVC.model')

new.name='My pipe line'
new.name

new


new
svc = new[1]


print(svc.__dict__.keys())


svc.intercept_

svc.coef_

dir(new)


new.



t,c = pd[0]

X[0].shape


trans = MyTransformer()

temp = np.empty((1,2),dtype=list)

temp[0] = [t,c]

trans.transform(temp)[0]


X = np.array(pd+nd)
y = np.array(pm+nm)
svm_clf.fit(X,y)


new.predict(X)[0]==1

    print(i,ord(i))
    
    



svm_clf.fit(X_train,y_train)

svm_clf.predict(X)

y

svm_clf.decision_function(X_test)


precision_score(y,svm_clf.predict(X))

recall_score(y,svm_clf.predict(X))

from sklearn.model_selection import StratifiedKFold 
from sklearn.base import clone

from sklearn.model_selection import cross_val_predict


skfolds = StratifiedKFold(n_splits=3, random_state=42)

for train_index, test_index in skfolds.split(X_train, y_train_5): 
    clone_clf = clone(sgd_clf)
    X_train_folds = X_train[train_index]
    y_train_folds = y_train_5[train_index]
    X_test_fold = X_train[test_index] 
    y_test_fold = y_train_5[test_index]
    clone_clf.fit(X_train_folds, y_train_folds)
    y_pred = clone_clf.predict(X_test_fold)
    n_correct = sum(y_pred == y_test_fold)
    print(n_correct / len(y_pred)) # prints 0.9502, 0.96565 and 0.96495




import matplotlib.pyplot as plt
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import json


plt.plot(np.arange(1,10),',')

a = [([1,2,3],[4,5,6]),([1,2,4],[5,6,7]),([1,2,4],[5,6,7])]
X = np.empty((len(a),2),dtype=list)
X[:] = a
X
np.array(a,)



np.