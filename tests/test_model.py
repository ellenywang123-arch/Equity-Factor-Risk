import unittest
import numpy as np
import pandas as pd
from data import annual_metrics
from factors import standardize,STYLES,raw_factors
from risk import portfolio_risk,covariance,regress
from main import synthetic_panel


class ModelTests(unittest.TestCase):
    def test_euler_contributions_sum_to_direct_variance(self):
        X=pd.DataFrame([[1.,-.5],[1.,1.]],index=["A","B"],columns=["market","value"])
        F=pd.DataFrame([[.0002,.00003],[.00003,.0001]],index=X.columns,columns=X.columns)
        D=pd.Series({"A":.0001,"B":.0002})
        w=pd.Series({"B":.4,"A":.6})
        result,table,specific=portfolio_risk(X,F,D,w)
        vector=w.reindex(X.index).to_numpy()
        direct=vector@(X.to_numpy()@F.to_numpy()@X.to_numpy().T+np.diag(D.reindex(X.index)))@vector
        self.assertAlmostEqual(result["daily_variance"],direct)
        self.assertAlmostEqual(table.total_variance_share.sum()+result["specific_variance_share"],1.)

    def test_missing_specific_variance_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"insufficient"):
            portfolio_risk(pd.DataFrame({"m":[1.]},index=["A"]),pd.DataFrame({"m":[.1]},index=["m"]),pd.Series({"A":np.nan}),{"A":1.})

    def test_statement_lag_and_annual_growth(self):
        cols=["2022-12-31","2023-12-31"]
        inc=pd.DataFrame([[100,120],[10,12]],index=["Total Revenue","Net Income Common Stockholders"],columns=cols)
        bal=pd.DataFrame([[50,60]],index=["Common Stock Equity"],columns=cols)
        m=annual_metrics(inc,bal,180)
        self.assertEqual(m.index[1],pd.Timestamp("2023-12-31")+pd.Timedelta(days=180))
        self.assertAlmostEqual(m.growth.iloc[1],.2)
        self.assertAlmostEqual(m.roe.iloc[1],12/55)

    def test_standardization_and_lagged_regression(self):
        panel=synthetic_panel()
        x=standardize(raw_factors(panel),35)
        section=x.xs(x.index.get_level_values("date").max())
        np.testing.assert_allclose(section.mean(),0,atol=1e-12)
        np.testing.assert_allclose(section.std(ddof=0),1,atol=1e-12)
        f,eps,ranks,design=regress(x,panel)
        date=f.index[-1]
        prev=x.index.get_level_values("date").unique()[-2]
        np.testing.assert_allclose(design.xs(date)[STYLES],x.xs(prev)[STYLES])
        F,D,_=covariance(f.tail(126),eps.reindex(f.tail(126).index))
        self.assertGreater(np.linalg.eigvalsh(F).min(),0)
        self.assertTrue((D.dropna()>=0).all())

    def test_future_data_does_not_change_past_regressions(self):
        panel=synthetic_panel()
        cutoff=panel.index.get_level_values("date").unique()[600]
        before=panel.loc[panel.index.get_level_values("date")<=cutoff]
        small=standardize(raw_factors(before))
        full=standardize(raw_factors(panel))
        a=regress(small,before)[0]
        b=regress(full,panel)[0].loc[a.index]
        np.testing.assert_allclose(a,b,atol=1e-12)


if __name__=="__main__":
    unittest.main()
