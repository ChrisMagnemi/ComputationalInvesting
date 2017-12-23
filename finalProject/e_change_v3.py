"""
This is a template algorithm on Quantopian for you to adapt and fill in.
"""
from quantopian.algorithm import attach_pipeline, pipeline_output
from quantopian.pipeline import Pipeline
import numpy as np
import pandas as pd
from datetime import timedelta
from datetime import date
import statsmodels
from statsmodels.tsa.stattools import coint
import statsmodels.tsa.stattools as ts
from quantopian.pipeline.data import morningstar as ms
from quantopian.pipeline.data import Fundamentals
from quantopian.pipeline.filters.morningstar import Q1500US
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.classifiers.morningstar import Sector
from quantopian.pipeline.factors import CustomFactor, AverageDollarVolume
from quantopian.pipeline.data import morningstar as mstar
from quantopian.pipeline.filters.morningstar import IsPrimaryShare
from quantopian.pipeline.factors import SimpleMovingAverage
import statsmodels.api as sm
import quantopian.optimize as opt

# MUCH OF THIS ADAPTED FROM STEPHAN BOTES NOTEBOOK

# GLOBAL CONSTANTS
COMMON_STOCK= 'ST00000001'

TARGET_POSITIONS = 25
ANALYSIS_DATE = date.today()-timedelta(days=7)
WINDOW_START = ANALYSIS_DATE-timedelta(days=60)
WINDOW_END = ANALYSIS_DATE

COINT_TEST_NUM_DAYS = 252

def initialize(context):
    context.stock_pairs = []
    context.num_pairs = 0
    my_pipe = make_pipeline()
    attach_pipeline(my_pipe, 'my_pipeline')
    
    schedule_function(set_pairs, date_rules.week_start(), time_rules.market_open())
    
    schedule_function(close_positions_from_last_week, date_rules.week_start(), time_rules.market_open())
    
    schedule_function(take_positions, date_rules.every_day(), time_rules.market_open(hours = 1))

    schedule_function(exit_positions_end_of_week, date_rules.week_end(), time_rules.market_close())
    
    schedule_function(record_vars, date_rules.every_day(), time_rules.market_close(minutes=1))

#==============EVERYTHING AFTER THIS LINE IS FOR CREATING PIPELINE============#

def make_pipeline():
    pipe = Pipeline()
    stocksUniverse = universe_filters()
    industry_code = ms.asset_classification.morningstar_industry_code.latest
    pipe = Pipeline(
        screen = (stocksUniverse),
        columns = {
            'industry_code': industry_code,
        }
    )
    return pipe

def universe_filters():
    # Equities with an average daily volume greater than 750000.
    high_volume = (AverageDollarVolume(window_length=252) > 750000)
    # Not Misc. industry:
    indsutry_code_filter = ~ms.asset_classification.morningstar_industry_code.latest.isnull()
    
    # Equities that morningstar lists as primary shares.
    # NOTE: This will return False for stocks not in the morningstar database.
    primary_share = IsPrimaryShare()
    
    # Equities for which morningstar's most recent Market Cap value is above $300m.
    have_market_cap = mstar.valuation.market_cap.latest > 300000000
    
    # Equities not listed as depositary receipts by morningstar.
    # Note the inversion operator, `~`, at the start of the expression.
    not_depositary = ~mstar.share_class_reference.is_depositary_receipt.latest
    
    # Equities that listed as common stock (as opposed to, say, preferred stock).
    # This is our first string column. The .eq method used here produces a Filter returning
    # True for all asset/date pairs where security_type produced a value of 'ST00000001'.
    common_stock = mstar.share_class_reference.security_type.latest.eq('COMMON_STOCK')
    
    # Equities whose exchange id does not start with OTC (Over The Counter).
    # startswith() is a new method available only on string-dtype Classifiers.
    # It returns a Filter.
    not_otc = ~mstar.share_class_reference.exchange_id.latest.startswith('OTC')
    
    # Equities whose symbol (according to morningstar) ends with .WI
    # This generally indicates a "When Issued" offering.
    # endswith() works similarly to startswith().
    not_wi = ~mstar.share_class_reference.symbol.latest.endswith('.WI')
    
    # Equities whose company name ends with 'LP' or a similar string.
    # The .matches() method uses the standard library `re` module to match
    # against a regular expression.
    not_lp_name = ~mstar.company_reference.standard_name.latest.matches('.* L[\\. ]?P\.?$')
    # Equities with a null entry for the balance_sheet.limited_partnership field.
    # This is an alternative way of checking for LPs.
    not_lp_balance_sheet = mstar.balance_sheet.limited_partnership.latest.isnull()
    # Highly liquid assets only. Also eliminates IPOs in the past 12 months
    # Use new average dollar volume so that unrecorded days are given value 0
    # and not skipped over
    # S&P Criterion
    liquid = ADV_adj() > 250000
    # Add logic when global markets supported
    # S&P Criterion
    domicile = True
    # Keep it to liquid securities
    ranked_liquid = ADV_adj().rank(ascending=False) < 1500
    # universe_filter = (indsutry_code_filter & high_volume & primary_share & have_market_cap & not_depositary & common_stock & not_otc & not_wi & not_lp_name & not_lp_balance_sheet & liquid & domicile & liquid & ranked_liquid)
    universe_filter = (indsutry_code_filter & 
                       primary_share &
                       high_volume &
                       ranked_liquid
                      )
    
    return universe_filter

# Average Dollar Volume without nanmean, so that recent IPOs are truly removed
class ADV_adj(CustomFactor):
    inputs = [USEquityPricing.close, USEquityPricing.volume]
    window_length = 252
    
    def compute(self, today, assets, out, close, volume):
        close[np.isnan(close)] = 0
        out[:] = np.mean(close * volume, 0)

#   ======EVERYTHING BEFORE THIS LINE IS FOR CREATING PIPELINE======#

# here instead of just pairing the stocks sequentially, we will get cointegrated pairs and use those to trade
    # first need a list of equities
    #     ** list of list of equities by industry, to slow if just one big list
    # Second need to convert equities array to prices dataframe
    #        (so cointegration function can check for pairs)
    # Third run the cointegration function ont he prices dataframe
    #        which will output all the cointegrated pairs
def get_2d_equities_from_pipe_by_industry(universe):
    universe = universe.sort_values(by='industry_code')
    equity_list_2d = []
    industry_list = []
    i=0
    while i in range(len(universe.industry_code)-1):
        if universe.industry_code[i] == universe.industry_code[i+1]:
            industry_list.append(universe.index[i])
            i += 1
        else:
            if len(industry_list) != 0:
                industry_list.append(universe.index[i])
                equity_list_2d.append(industry_list)
                industry_list = []
            i += 1
    return equity_list_2d

def eq_list_to_price_df(eq_list, num_days, data):
    price_df = data.history(eq_list,
                            fields=['price'],
                            bar_count=num_days,
                            frequency='1d')['price']
    return price_df

def find_cointegrated_pairs(df_array): # Takes in an array of dataframes, outputs cointegrated pairs
    for df in df_array:
        n = df.shape[1]
        score_matrix = np.zeros((n, n))
        pvalue_matrix = np.ones((n, n))
        keys = df.keys()
        pairs = []
        total_stocks = n
        total_tests = ((total_stocks)*(total_stocks - 1))/2 # n choose 2 total combinations
    for i in range(n):
        for j in range(i+1, n):
            S1 = df[keys[i]]
            S2 = df[keys[j]]
            result = ts.coint(S1, S2)
            score = result[0]
            pvalue = result[1]
            score_matrix[i, j] = score
            pvalue_matrix[i, j] = pvalue
            if pvalue < (0.05): # Applying Bonferroni correction 
                pairs.append((keys[i], keys[j]))
    total_stocks = 0
    # print pairs
    return pairs


#   =======EVERYTHING AFTER THIS LINE IS FOR ORDERING==========#



def set_pairs(context, data, COINT_TEST_NUM_DAYS):
    print "SET PAIRS BEGINNING"
    context.output = pipeline_output('my_pipeline')
    # turn pipeline output into 2d array of equities by industry
    context.eq_arr_by_indus = get_2d_equities_from_pipe_by_industry(context.output)
    # use loop to convert 2d array of equities into array of price dataframes by industry
    context.arr_of_price_dfs = []
    for i in range(len(context.eq_arr_by_indus)):
        this_industry = context.eq_arr_by_indus[i]
        this_price_df = eq_list_to_price_df(this_industry, COINT_TEST_NUM_DAYS, data)
        # print this_price_df
        context.arr_of_price_dfs.append(this_price_df)
    # find cointegrated pairs on this array of price dataframes
    context.stock_pairs= find_cointegrated_pairs(context.arr_of_price_dfs)
    #context.full_arr_of_stocks_traded.append(context.stock_pairs)
    print " LOOK AT THE PAIRS"
    context.num_pairs = len(context.stock_pairs)
    print context.stock_pairs
    
    print "YOU SAW THE PAIRS?"
    return
    
def take_positions(context, data):
    num_std_dev = 2.5
    num_pairs = len(context.stock_pairs)
    for i in range(context.num_pairs):
        isYLong = False
        isYShort = False
        isXLong = False
        isXShort = False

        (stock_y, stock_x) = context.stock_pairs[i]
        
        Y = data.history(stock_y, 'price', 60, '1d')
        X = data.history(stock_x, 'price', 60, '1d')
        print "Y", Y
        print "Y[0]", Y[0]
        spread_60_day = Y - X
        #print y2
        mean = spread_60_day.mean()
        stddev = spread_60_day.std()
        # mean = 60_day_spread.mean()
        # stddev = 60_day_spread.std()
        print "stock y", stock_y
        print "stock x", stock_y
        print "mean", mean
        print "stddev", stddev
        current_priceY = data.current(stock_y, 'price')
        current_priceX = data.current(stock_x, 'price')
        spread = current_priceY - current_priceX
        hedgeR = hedge_ratio(Y, X)
        amt_Y = context.portfolio.positions[stock_y].amount
        amt_X = context.portfolio.positions[stock_x].amount
        if amt_Y < 0: 
            isYShort = True
        if amt_Y > 0:
            isYLong = True
        if amt_X < 0:
            isXShort = True
        if amt_X > 0:
            isXLong = True 
        if spread < mean and (isYShort or isXLong) and all(data.can_trade([stock_y,stock_x])):
            order_target(stock_y, 0)
            order_target(stock_x, 0)
            record(X_pct=0, Y_pct=0)
            isYShort = False
            isXLong = False
            return

        if spread > mean and (isYLong or isXShort) and all(data.can_trade([stock_y,stock_x])):
            order_target(stock_y, 0)
            order_target(stock_x, 0)
            record(X_pct=0, Y_pct=0)
            isYLong = False
            isXShort = False
            return
        if spread < mean - stddev * num_std_dev:
            order_target(stock_y, 0)
            order_target(stock_x, 0)
            isYLong = False
            isXShort = False
            context.stock_pairs.remove(context.stock_pairs[i])
            return
        if spread > mean + stddev * num_std_dev:
            order_target(stock_y, 0)
            order_target(stock_x, 0)
            isYShort = False
            isXLong = False
            context.stock_pairs.remove(context.stock_pairs[i])
            return
        if spread < mean - stddev and all(data.can_trade([stock_y,stock_x])):
            # Only trade if NOT already in a trade
            y_target_shares = 1
            X_target_shares = -hedgeR

            (y_target_pct, x_target_pct) = computeHoldingsPct( y_target_shares,X_target_shares, Y[-1], X[-1])
            order_target_percent( stock_y, y_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            order_target_percent( stock_x, x_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            record(Y_pct=y_target_pct, X_pct=x_target_pct)
            return
        #if zscore > 1 
        if spread > mean + stddev and all(data.can_trade([stock_y,stock_x])):
            # Only trade if NOT already in a trade
            y_target_shares = -1
            X_target_shares = hedgeR

            (y_target_pct, x_target_pct) = computeHoldingsPct( y_target_shares, X_target_shares, Y[-1], X[-1] )
            order_target_percent( stock_y, y_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            order_target_percent( stock_x, x_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            record(Y_pct=y_target_pct, X_pct=x_target_pct)

def hedge_ratio(Y, X):
    X = sm.add_constant(X)
    model = sm.OLS(Y, X).fit()
    return model.params[1]

def exit_positions_end_of_week(context, data):
    open_orders = get_open_orders()  
    if open_orders:
        for security, orders in open_orders.iteritems():
            order_target(security, 0)
    return
    

def close_positions_from_last_week(context, data):
    open_orders = get_open_orders()   
    if open_orders:  
        for security, orders in open_orders.iteritems():
            order_target(security, 0)
    return
    
def computeHoldingsPct(yShares, xShares, yPrice, xPrice):
    yDol = yShares * yPrice
    xDol = xShares * xPrice
    notionalDol =  abs(yDol) + abs(xDol)
    y_target_pct = yDol / notionalDol
    x_target_pct = xDol / notionalDol
    return (y_target_pct, x_target_pct)
            
#====================EVERYTHING BEFORE THIS LINE IS FOR ORDERING===============#
def record_vars(context, data):
    longs = shorts = 0
    for position in context.portfolio.positions.itervalues():
        if position.amount > 0:
            longs += 1
        if position.amount < 0:
            shorts += 1
    record(leverage = context.account.leverage, long_count=longs, short_count=shorts)
    return