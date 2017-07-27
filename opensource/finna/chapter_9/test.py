# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import collections
import numpy as np
import numbers
import random
from itertools import combinations
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.cross_validation import train_test_split
import statsmodels.api as sm
import sys
import pickle
reload(sys)
sys.setdefaultencoding( "utf-8")
import scorecard_fucntions
reload(scorecard_fucntions)
from scorecard_fucntions import *
from sklearn.linear_model import LogisticRegressionCV



#########################################################################################################
#Step 0: Initiate the data processing work, including reading csv files, checking the consistency of Idx#
#########################################################################################################
#path= 'D:/workspace/DataScience/data/ppd/'
path= '/home/tanglek/workspace/DataScience/data/ppd/'


trainData = pd.read_csv(path+'bank_default/allData_1b.csv',header = 0, encoding='gbk')
allFeatures = list(trainData.columns)
allFeatures.remove('ListingInfo')
allFeatures.remove('target')
allFeatures.remove('Idx')
#devide the whole independent variables into categorical type and numerical type
numerical_var = []
for var in allFeatures:
    uniq_vals = list(set(trainData[var]))
    if np.nan in uniq_vals:
        uniq_vals.remove( np.nan)
    if len(uniq_vals) >= 10 and isinstance(uniq_vals[0],numbers.Real):
        numerical_var.append(var)

categorical_var = [i for i in allFeatures if i not in numerical_var]

for col in categorical_var:
    trainData[col] = trainData[col].map(lambda x: str(x).upper())


'''
For cagtegorical variables, follow the below steps
1, if the variable has distinct values more than 5, we calculate the bad rate and encode the variable with the bad rate
2, otherwise:
(2.1) check the maximum bin, and delete the variable if the maximum bin occupies more than 90%
(2.2) check the bad percent for each bin, if any bin has 0 bad samples, then combine it with samllest non-zero bad bin,
        and then check the maximum bin again
'''
deleted_features = []  #delete the categorical features in one of its single bin occupies more than 90%
encoded_features = {}
merged_features = {}
var_IV = {}  #save the IV values for binned features
var_WOE = {}
for col in categorical_var:
    print 'we are processing {}'.format(col)
    if len(set(trainData[col]))>5:
        print '{} is encoded with bad rate'.format(col)
        col0 = str(col)+'_encoding'
        #(1), calculate the bad rate and encode the original value using bad rate
        encoding_result = BadRateEncoding(trainData, col, 'target')
        trainData[col0], br_encoding = encoding_result['encoding'],encoding_result['br_rate']
        #(2), push the bad rate encoded value into numerical varaible list
        numerical_var.append(col0)
        #(3), save the encoding result, including new column name and bad rate
        encoded_features[col] = [col0, br_encoding]
        #(4), delete the original value
        #del trainData[col]
        deleted_features.append(col)
    else:
        maxPcnt = MaximumBinPcnt(trainData, col)
        if maxPcnt > 0.9:
            print '{} is deleted because of large percentage of single bin'.format(col)
            deleted_features.append(col)
            categorical_var.remove(col)
            #del trainData[col]
            continue
        bad_bin = trainData.groupby([col])['target'].sum()
        if min(bad_bin) == 0:
            print '{} has 0 bad sample!'.format(col)
            col1 = str(col) + '_mergeByBadRate'
            #(1), determine how to merge the categories
            mergeBin = MergeBad0(trainData, col, 'target')
            #(2), convert the original data into merged data
            trainData[col1] = trainData[col].map(mergeBin)
            maxPcnt = MaximumBinPcnt(trainData, col1)
            if maxPcnt > 0.9:
                print '{} is deleted because of large percentage of single bin'.format(col)
                deleted_features.append(col)
                categorical_var.remove(col)
                del trainData[col]
                continue
            #(3) if the merged data satisify the requirement, we keep it
            merged_features[col] = [col1, mergeBin]
            WOE_IV = CalcWOE(trainData, col1, 'target')
            var_WOE[col1] = WOE_IV['WOE']
            var_IV[col1] = WOE_IV['IV']
            #del trainData[col]
            deleted_features.append(col)
        else:
            WOE_IV = CalcWOE(trainData, col, 'target')
            var_WOE[col] = WOE_IV['WOE']
            var_IV[col] = WOE_IV['IV']


'''
For continous variables, we do the following work:
1, split the variable by ChiMerge (by default into 5 bins)
2, check the bad rate, if it is not monotone, we decrease the number of bins until the bad rate is monotone
3, delete the variable if maximum bin occupies more than 90%
'''
var_cutoff = {}
for col in numerical_var:
    print "{} is in processing".format(col)
    col1 = str(col) + '_Bin'
    #(1), split the continuous variable and save the cutoff points. Particulary, -1 is a special case and we separate it into a group
    if -1 in set(trainData[col]):
        special_attribute = [-1]
    else:
        special_attribute = []
    cutOffPoints = ChiMerge_MaxInterval(trainData, col, 'target',special_attribute=special_attribute)
    var_cutoff[col] = cutOffPoints
    trainData[col1] = trainData[col].map(lambda x: AssignBin(x, cutOffPoints,special_attribute=special_attribute))

    #(2), check whether the bad rate is monotone
    BRM = BadRateMonotone(trainData, col1, 'target',special_attribute=special_attribute)
    if not BRM:
        for bins in range(4,1,-1):
            cutOffPoints = ChiMerge_MaxInterval(trainData, col, 'target',max_interval = bins,special_attribute=special_attribute)
            trainData[col1] = trainData[col].map(lambda x: AssignBin(x, cutOffPoints,special_attribute=special_attribute))
            BRM = BadRateMonotone(trainData, col1, 'target',special_attribute=special_attribute)
            if BRM:
                break
        var_cutoff[col] = cutOffPoints

    #(3), check whether any single bin occupies more than 90% of the total
    maxPcnt = MaximumBinPcnt(trainData, col1)
    if maxPcnt > 0.9:
        #del trainData[col1]
        deleted_features.append(col)
        numerical_var.remove(col)
        print 'we delete {} because the maximum bin occupies more than 90%'.format(col)
        continue
    WOE_IV = CalcWOE(trainData, col1, 'target')
    var_IV[col] = WOE_IV['IV']
    var_WOE[col] = WOE_IV['WOE']
    #del trainData[col]



#trainData.to_csv(path+'bank_default/allData_2a.csv', header=True,encoding='gbk', columns = trainData.columns, index=False)

# filewrite = open(path+'bank_default/var_WOE.pkl','w')
# pickle.dump(var_WOE, filewrite)
# filewrite.close()
#
#
# filewrite = open(path+'bank_default/var_IV.pkl','w')
# pickle.dump(var_IV, filewrite)
# filewrite.close()
#

#########################################################
# Step 4: Select variables with IV > 0.02 and assign WOE#
#########################################################
# var_WOE = pickle.load(open(path+'bank_default/var_WOE.pkl','r'))
# var_IV = pickle.load(open(path+'bank_default/var_IV.pkl','r'))


trainData = pd.read_csv(path+'bank_default/allData_2a.csv', header=0, encoding='gbk')

num2str = ['SocialNetwork_13','SocialNetwork_12','UserInfo_6','UserInfo_5','UserInfo_10','UserInfo_17','city_match']
for col in num2str:
    trainData[col] = trainData[col].map(lambda x: str(x))


for col in var_WOE.keys():
    print col
    col2 = str(col)+"_WOE"
    if col in var_cutoff.keys():
        cutOffPoints = var_cutoff[col]
        special_attribute = []
        if - 1 in cutOffPoints:
            special_attribute = [-1]
        binValue = trainData[col].map(lambda x: AssignBin(x, cutOffPoints,special_attribute=special_attribute))
        trainData[col2] = binValue.map(lambda x: var_WOE[col][str(x)])
    else:
        trainData[col2] = trainData[col].map(lambda x: var_WOE[col][str(x)])

# trainData.to_csv(path+'bank_default/allData_3.csv', header=True,encoding='gbk', columns = trainData.columns, index=False)





### (i) select the features with IV above the thresould
iv_threshould = 0.02
varByIV = [k for k, v in var_IV.items() if v > iv_threshould]


### (ii) check the collinearity of any pair of the features with WOE after (i)

var_IV_selected = {k:var_IV[k] for k in varByIV}
var_IV_sorted = sorted(var_IV_selected.iteritems(), key=lambda d:d[1], reverse = True)
var_IV_sorted = [i[0] for i in var_IV_sorted]

removed_var  = []
roh_thresould = 0.6
for i in range(len(var_IV_sorted)-1):
    if var_IV_sorted[i] not in removed_var:
        x1 = var_IV_sorted[i]+"_WOE"
        for j in range(i+1,len(var_IV_sorted)):
            if var_IV_sorted[j] not in removed_var:
                x2 = var_IV_sorted[j] + "_WOE"
                roh = np.corrcoef([trainData[x1], trainData[x2]])[0, 1]
                if abs(roh) >= roh_thresould:
                    print 'the correlation coeffient between {0} and {1} is {2}'.format(x1, x2, str(roh))
                    if var_IV[var_IV_sorted[i]] > var_IV[var_IV_sorted[j]]:
                        removed_var.append(var_IV_sorted[j])
                    else:
                        removed_var.append(var_IV_sorted[i])

var_IV_sortet_2 = [i for i in var_IV_sorted if i not in removed_var]

### (iii) check the multi-colinearity according to VIF > 10
for i in range(len(var_IV_sortet_2)):
    x0 = trainData[var_IV_sortet_2[i]+'_WOE']
    x0 = np.array(x0)
    X_Col = [k+'_WOE' for k in var_IV_sortet_2 if k != var_IV_sortet_2[i]]
    X = trainData[X_Col]
    X = np.matrix(X)
    regr = LinearRegression()
    clr= regr.fit(X, x0)
    x_pred = clr.predict(X)
    R2 = 1 - ((x_pred - x0) ** 2).sum() / ((x0 - x0.mean()) ** 2).sum()
    vif = 1/(1-R2)
    if vif > 10:
        print "Warning: the vif for {0} is {1}".format(var_IV_sortet_2[i], vif)



#############################################################################################################
# Step 5: build the logistic regression using selected variables after single analysis and mulitple analysis#
#############################################################################################################

### (1) put all the features after single & multiple analysis into logisitic regression
var_WOE_list = [i+'_WOE' for i in var_IV_sortet_2]
y = trainData['target']
X = trainData[var_WOE_list]
X['intercept'] = [1]*X.shape[0]


LR = sm.Logit(y, X).fit()
summary = LR.summary()
pvals = LR.pvalues
pvals = pvals.to_dict()

### Some features are not significant, so we need to delete feature one by one.
varLargeP = {k: v for k,v in pvals.items() if v >= 0.1}
varLargeP = sorted(varLargeP.iteritems(), key=lambda d:d[1], reverse = True)
while(len(varLargeP) > 0 and len(var_WOE_list) > 0):
    # In each iteration, we remove the most insignificant feature and build the regression again, until
    # (1) all the features are significant or
    # (2) no feature to be selected
    varMaxP = varLargeP[0][0]
    if varMaxP == 'intercept':
        print 'the intercept is not significant!'
        break
    var_WOE_list.remove(varMaxP)
    y = trainData['target']
    X = trainData[var_WOE_list]
    X['intercept'] = [1] * X.shape[0]

    LR = sm.Logit(y, X).fit()
    summary = LR.summary()
    pvals = LR.pvalues
    pvals = pvals.to_dict()
    varLargeP = {k: v for k, v in pvals.items() if v >= 0.1}
    varLargeP = sorted(varLargeP.iteritems(), key=lambda d: d[1], reverse=True)


'''
Now all the features are significant and the sign of coefficients are negative
var_WOE_list = ['UserInfo_15_encoding_WOE', u'ThirdParty_Info_Period6_10_WOE', u'ThirdParty_Info_Period5_2_WOE', 'UserInfo_16_encoding_WOE', 'WeblogInfo_20_encoding_WOE',
            'UserInfo_7_encoding_WOE', u'UserInfo_17_WOE', u'ThirdParty_Info_Period3_10_WOE', u'ThirdParty_Info_Period1_10_WOE', 'WeblogInfo_2_encoding_WOE',
            'UserInfo_1_encoding_WOE']
'''


saveModel =open(path+'bank_default/LR_Model_Normal.pkl','w')
pickle.dump(LR,saveModel)
saveModel.close()



######################################################################################################
# Step 6(a): build the logistic regression using lasso and weights based on variables given in Step 5#
######################################################################################################
### use cross validation to select the best regularization parameter
X = trainData[var_WOE_list]   #by default  LogisticRegressionCV() fill fit the intercept
X = np.matrix(X)
y = trainData['target']
y = np.array(y)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.4, random_state=0)
X_train.shape, y_train.shape

model_parameter = {}
for C_penalty in np.arange(0.005, 0.2,0.005):
    for bad_weight in range(2, 101, 2):
        LR_model_2 = LogisticRegressionCV(Cs=[C_penalty], penalty='l1', solver='liblinear', class_weight={1:bad_weight, 0:1})
        LR_model_2_fit = LR_model_2.fit(X_train,y_train)
        y_pred = LR_model_2_fit.predict_proba(X_test)[:,1]
        scorecard_result = pd.DataFrame({'prob':y_pred, 'target':y_test})
        performance = KS_AR(scorecard_result,'prob','target')
        KS = performance['KS']
        model_parameter[(C_penalty, bad_weight)] = KS

####################################################################################
# Step 6(b): build the logistic regression using according to RF feature importance#
####################################################################################
### build random forest model to estimate the importance of each feature
### In this case we use the original feautures with WOE encoding before single analysis

X = trainData[var_WOE_list]
X = np.matrix(X)
y = trainData['target']
y = np.array(y)

RFC = RandomForestClassifier()
RFC_Model = RFC.fit(X,y)
features_rfc = trainData[var_WOE_list].columns
featureImportance = {features_rfc[i]:RFC_Model.feature_importances_[i] for i in range(len(features_rfc))}
featureImportanceSorted = sorted(featureImportance.iteritems(),key=lambda x: x[1], reverse=True)
# we selecte the top 10 features
features_selection = [k[0] for k in featureImportanceSorted[:10]]

y = trainData['target']
X = trainData[features_selection]
X['intercept'] = [1]*X.shape[0]


LR = sm.Logit(y, X).fit()
summary = LR.summary()

print summary