"""
This is a template algorithm on Quantopian for you to adapt and fill in.
"""
import numpy as np
import pandas as pd
from quantopian.algorithm import attach_pipeline, pipeline_output
from quantopian.pipeline import Pipeline
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.factors import AverageDollarVolume
from quantopian.pipeline.filters.morningstar import Q1500US
from quantopian.pipeline.data import morningstar as ms
from quantopian.pipeline.data import Fundamentals
 
def initialize(context):
    """
    Called once at the start of the algorithm.
    """   
    context.stock1 = sid(2)
    context.stock2 = sid(25)
    context.stddev_limit = 1.75
    context.qty = 400
    # Rebalance every day, 1 hour after market open.
    schedule_function(my_rebalance, date_rules.every_day(), time_rules.market_open(hours=1))
     
    # Record tracking variables at the end of each day.
    schedule_function(my_record_vars, date_rules.every_day(), time_rules.market_close())
    
    # schedule_function(order_handling, date_rules.every_day(), time_rules.market_open(hours=1))
    schedule_function(make_orders, date_rules.every_day(), time_rules.market_open(hours=1))
     
    # Create our dynamic stock selector.
    attach_pipeline(make_pipeline(), 'my_pipeline')
         
def make_pipeline():
    print "START"
    industry_code = ms.asset_classification.morningstar_industry_code.latest
    ebitda = ms.income_statement.ebitda.latest
    sic = ms.asset_classification.sic.latest
    common_stock_equity = ms.balance_sheet.common_stock_equity.latest
    #     morningstar_sector = Sector()
    #     exchange = Fundamentals.exchange_id.latest
    
    
    # sample_industry = 10106008
    
#     one_industry = (industry_code == sample_industry)
    
    
#     industry_code_filter = industry_code.eq(sample_industry) | industry_code.eq(10102002)
    
    print "END"
    return Pipeline(
        columns={
            #'exchange': exchange,
            #'sector_code': morningstar_sector,
            'sic': sic,
            'industry_code': industry_code,
            'ebitda': ebitda,
            'common_stock_equity': common_stock_equity
        }
    )

def clean_the_pipe(context, data):
	# get rid on all rows with NaN values
	workingdf = context.output
 	# workingdf = pipeline_output('my_pipeline')
 	# print "shape of dropping all nans: ", workingdf.dropna(axis=0).shape
	df_nonans = workingdf.dropna(axis=0)
	# df_nonans.industry_code.value_counts()
	# get rid of industry 10320045 cause it only has 1 company in it
	df_nonans = df_nonans[df_nonans.industry_code != 10320045]
	df_nonans.industry_code.value_counts()
	# get rid of industry -1 cause its misceallaneous industry and only has 4 companies in it
	df_nonans = df_nonans[df_nonans.industry_code != -1]
 # print "PENIS, ", df_nonans.industry_code.value_counts()
	# Wahoo! clean dataframe
	df_clean = df_nonans
	return df_clean

def get_industry_codes_no_repeats(df):
    goal_length = len(df.industry_code.value_counts())
    industry_code_array = []
    for code in df.industry_code:
        if code not in industry_code_array:
            industry_code_array.append(code)
    if len(industry_code_array) == goal_length:
        return industry_code_array
    else:
        return "NOPE"
    
    
def before_trading_start(context, data):
    """
    Called every day before market open.
    """
    print "IN before trading start"
    context.output = pipeline_output('my_pipeline')
    df = clean_the_pipe(context,data)
    print df
    industry_codes = get_industry_codes_no_repeats(df)
    # These are the securities that we are interested in trading each day.
    # go long on companies in first industry of industry_codes list
    context.longs = df[df['industry_code']==industry_codes[0]].index.tolist()
    context.shorts = df[df['industry_code']==industry_codes[1]].index.tolist()
    
    context.long_weight, context.short_weight = my_assign_weights(context)
    
    context.security_list = context.output.index
    print "end before trading start"
     
def my_assign_weights(context):
    """
    Assign weights to securities that we want to order.
    """
    long_weights = 0.5/len(context.longs)
    short_weights = -0.5/len(context.shorts)
    # print long_weights
    
    return long_weights, short_weights
 
def my_rebalance(context,data):
    """
    Execute orders according to our schedule_function() timing. 
    """
    pass

import statsmodels.api as sm
def hedge_ratio(Y, X):
    X = sm.add_constant(X)
    model = sm.OLS(Y, X).fit()
    return model.params[1]

def order_handling(context, data):
    current_price1 = data.current(context.stock1, 'price')
    price_history1 = data.history(context.stock1, 'price', 20, '1d')
    current_price2 = data.current(context.stock2, 'price')
    price_history2 = data.history(context.stock2, 'price', 20, '1d')
    mean = price_history1.mean() - price_history2.mean()
    stddev = price_history1.std() - price_history2.std()
    upper_bb = mean + 2*stddev
    lower_bb = mean - 2*stddev
    spread = current_price1 - current_price2
    
    # # #NEED TO SOMEHOW CHANGE THIS TO CURRENT SPREAD
    # record(CMG=current_price)
    # record(Upper=upper_bb)
    # record(MA20=mean)
    # record(Lower=lower_bb)
    # At top of bands?
    if spread > mean + stddev * context.stddev_limit :
        # Are we long or neutral?
        if context.portfolio.positions[context.stock1].amount >= context.portfolio.positions[context.stock2].amount:
            #CALCULATE HEDGERATIO
            hedgeR = hedge_ratio(price_history1, price_history2)
            # Close our long position if we have one
            #close_position(context, data)
            #short stock1
            order(context.stock1, -context.qty)
            #buy stock2
            order(context.stock2, hedgeR*context.qty)
            # At bottom of bands?
	if spread < mean - stddev * context.stddev_limit:
        # Are we short or neutral?
		if context.portfolio.positions[context.stock1].amount <= context.portfolio.positions[context.stock2].amount:
			hedgeR = hedge_ratio(price_history1, price_history2)
            # Close our short position if we have one
            #close_position(context, data)
            #buy stock1
			order(context.stock1, context.qty)
            #short stock2
			order(context.stock2, hedgeR*context.qty*(-1))
        return


 
def my_record_vars(context, data):
    """
    Plot variables at the end of each day.
    
    """
    longs = shorts = 0
    # longs = context.longs
    # shorts = context.shorts
    for position in context.portfolio.positions.itervalues():
        if position.amount > 0:
            longs +=1
        elif position.amount < 0:
            shorts +=1
    
    record(leverage=context.account.leverage, long_count=longs, short_counts=shorts)
    
    pass

def make_orders(context, data):
    # make orders here cause cannot be done before trading start
    print "-------- in make orders -------------- "
    
    for security in context.portfolio.positions:
        if security not in context.longs and security not in context.shorts and data.can_trade(security):
            order_target_percent(security,0)
     
    for security in context.longs:
        if data.can_trade(security):
            order_target_percent(security,context.long_weight)
        
    for security in context.shorts:
        if data.can_trade(security):
            order_target_percent(security, context.short_weight)
    pass
 
def handle_data(context,data):
    """
    Called every minute.
    """
    pass
