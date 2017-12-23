
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
    
    context.non_coint_low = 0
    context.non_coint_high = 0
    
    my_pipe = make_pipeline()
    attach_pipeline(my_pipe, 'my_pipeline')
    
    schedule_function(set_pairs, date_rules.week_start(), time_rules.market_open())
    
    schedule_function(close_positions_from_last_week, date_rules.week_start(), time_rules.market_open())
    
    schedule_function(take_positions, date_rules.every_day(), time_rules.market_open(hours = 1))

    # schedule_function(exit_positions_end_of_week, date_rules.week_end(), time_rules.market_close())
    
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
def set_pairs(context, data):
    print "IT IS A NEW WEEK - set pairs"
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
    found_some_pairs = find_cointegrated_pairs(context.arr_of_price_dfs)
    for pair in found_some_pairs:
        if pair not in context.stock_pairs:  
            context.stock_pairs.append(pair)
    #context.full_arr_of_stocks_traded.append(context.stock_pairs)
    # print " LOOK AT THE PAIRS FOR THE WEEK"
    context.num_pairs = len(context.stock_pairs)
    # print context.stock_pairs
    
    # print "YOU SAW THE PAIRS?"
    return
    
def take_positions(context, data):
    print "IT IS A NEW DAY - take positions"
    num_std_dev = 2.5
    extreme_num_std_dev = 3.5
    i = 0
    num_pairs = len(context.stock_pairs)
    print "all pairs in take positions right now"
    print context.stock_pairs
    while i in range(len(context.stock_pairs)):
        isYLong = False
        isYShort = False
        isXLong = False
        isXShort = False
        
        # print len(context.stock_pairs)
        # print i
        (stock_y, stock_x) = context.stock_pairs[i]
        print "We're currently trading on this pair"
        print context.stock_pairs[i]
        
        Y = data.history(stock_y, 'price', 60, '1d')
        X = data.history(stock_x, 'price', 60, '1d')
        spread_60_day = Y - X
        mean = spread_60_day.mean()
        print "the mean of their spread is", mean
        stddev = spread_60_day.std()
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
        if amt_Y < 0 and amt_X > 0:
            position = 'Short'
        elif amt_Y > 0 and amt_X < 0:
            position = 'Long'
        else:
            position = 'None'
        
        if position == 'Long' and all(data.can_trade([stock_y,stock_x])):
        #if in a long position on the spread of Y - X (shortY,longX)
            print "currently longing the spread"
            if spread > mean:

            # if the spread then goes below the mean, exit position
                print "current spread is below the mean, close both"
                order_target(stock_y, 0)
                order_target(stock_x, 0)
                # record(X_pct=0, Y_pct=0)
                context.stock_pairs.remove(context.stock_pairs[i])
                i += 1
            # elif spread < mean - stddev * num_std_dev:
            # # if the spread goes too high above the mean, cut losses
            # # because this pair is probably not cointegrated anymore
            #     # want to do momentum here
            #     #test for coint:
            #     test = ts.coint(Y,X)
            #     pval = test[1]
            #     if pval > 0.05: # meaning this pair is not cointed
            #         y_target_shares = -1
            #         X_target_shares = hedgeR

            #         (y_target_pct, x_target_pct) = computeHoldingsPct( y_target_shares, X_target_shares, Y[-1], X[-1] )
            #         order_target_percent( stock_y, y_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            #         order_target_percent( stock_x, x_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
                    
            #     i += 1
                
                # print "we're up 2.5 std deviations, cut our losses"
                # order_target(stock_y, 0)
                # order_target(stock_x, 0)
                # context.non_coint_high += 1
                # record(spread_too_high = context.non_coint_high)
                # context.stock_pairs.remove(context.stock_pairs[i])
                # num_pairs -= 1
            else: # hold this position
                print "still above mean but below 2.5 std devs, do nothing"
                i += 1
        elif position == 'Short' and all(data.can_trade([stock_y,stock_x])):
            print "currently shorting the spread"
        #if in a short position on the spread of Y-X (longX, shortY)
            if spread < mean:
            # if the spread then goes below the mean, exit position
                print "current spread is above mean, close both"
                order_target(stock_y, 0)
                order_target(stock_x, 0)
                context.stock_pairs.remove(context.stock_pairs[i])
                # record(X_pct=0, Y_pct=0)
                i += 1
            # elif spread > (mean + stddev * num_std_dev):
            # # if the spread goes too high above the mean+stddev, cut losses
            # # because this pair is probably not cointegrated anymore
            #     test = ts.coint(Y,X)
            #     pval = test[1]
            #     if pval > 0.05: # meaning this pair is not cointed
            #         #short X long Y
            #         y_target_shares = 1
            #         X_target_shares = -hedgeR

            #         (y_target_pct, x_target_pct) = computeHoldingsPct( y_target_shares,X_target_shares, Y[-1], X[-1])
            #         order_target_percent( stock_y, y_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            #         order_target_percent( stock_x, x_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
            #     i += 1
            
                # print "we're down 2.5 std deviations, cut our losses"
                # order_target(stock_y, 0)
                # order_target(stock_x, 0)
                # context.non_coint_low += 1
                # record(spread_too_low = context.non_coint_low)
                # context.stock_pairs.remove(context.stock_pairs[i])
                # num_pairs -= 1
            else: # hold this position
                print "still below mean but above 2.5 stddevs, do nothing"
                i += 1
        else: # in a neutral position on the spread Y-X
            print "not currently in a position for this pair"
            if spread < mean - stddev and all(data.can_trade([stock_y,stock_x])):
                # if the spread (Y-X) is currently 1 stddev or more below the mean, then we long the spread, (want to long Y and short X)
                print "below lower band, long spread"
            # Only trade if NOT already in a trade
                y_target_shares = 1
                X_target_shares = -hedgeR

                (y_target_pct, x_target_pct) = computeHoldingsPct( y_target_shares,X_target_shares, Y[-1], X[-1])
                order_target_percent( stock_y, y_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
                order_target_percent( stock_x, x_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
                # record(Y_pct=y_target_pct, X_pct=x_target_pct)
                i += 1
          
            elif spread > mean + stddev and all(data.can_trade([stock_y,stock_x])):
                # if the spread (Y-X) is currently 1 stddev or more above the mean, then we short the spread, (want to short Y and long X)
                print "above upper band, long spread"
                # Only trade if NOT already in a trade
                y_target_shares = -1
                X_target_shares = hedgeR

                (y_target_pct, x_target_pct) = computeHoldingsPct( y_target_shares, X_target_shares, Y[-1], X[-1] )
                order_target_percent( stock_y, y_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
                order_target_percent( stock_x, x_target_pct * (1.0/context.num_pairs) / float(context.num_pairs) )
                # record(Y_pct=y_target_pct, X_pct=x_target_pct)
                i += 1
            else:
                print "neither above nor below band, do nothing"
                i += 1
                
        print "Now I have this much of stock Y", context.portfolio.positions[stock_y].amount
        print "Now I have this much of stock X", context.portfolio.positions[stock_x].amount


def momentum_long(Y, X):
    pass
     

def hedge_ratio(Y, X):
    X = sm.add_constant(X)
    model = sm.OLS(Y, X).fit()
    return model.params[1]

def exit_positions_end_of_week(context, data):
    open_orders = get_open_orders()
    print "It's the end of the week"
    list_of_secs = []
    #print "Here's a list of open orders", open_orders
    if open_orders:
        for security, orders in open_orders.iteritems():
            list_of_secs.append(security)
            order_target(security, 0)
    print "Here's a list of open orders", list_of_secs
    return
    

def close_positions_from_last_week(context, data):
    open_orders = get_open_orders()
    print "It's the beginning of the week"
    list_of_secs = []
    if open_orders:  
        for security, orders in open_orders.iteritems():
            list_of_secs.append(security)
            order_target(security, 0)
    print "Here's a list of open orders", list_of_secs
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