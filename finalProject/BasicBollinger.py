"""
This is a template algorithm on Quantopian for you to adapt and fill in.
"""
"""
READ ME ^^^^^^^&&&&&&&&&*******************)))))))))))))))!!!!!
run backtest should see table of assests with lower middle upper columns
corresponging to the bollinger bands.
need to filter out stocks somehow currently using too many.
? Then somehow buy/sell using the band prices ??
"""
from quantopian.algorithm import attach_pipeline, pipeline_output
from quantopian.pipeline import Pipeline
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.factors import AverageDollarVolume, SimpleMovingAverage, BollingerBands
from quantopian.pipeline.filters.morningstar import Q1500US, Q500US
 
def initialize(context):
    """
    Called once at the start of the algorithm.
    """   
    # context.aapl = sid(24)
    # Rebalance every day, 1 hour after market open.
    schedule_function(make_orders, date_rules.every_day(), time_rules.market_open(hours=1))
     
    # Record tracking variables at the end of each day.
    schedule_function(my_record_vars, date_rules.every_day(), time_rules.market_close())
    
    pipe = make_pipeline()
     
    # Create our dynamic stock selector.
    attach_pipeline(pipe, 'my_pipeline')
         
def make_pipeline():
    """
    A function to create our dynamic stock selector (pipeline). Documentation on
    pipeline can be found here: https://www.quantopian.com/help#pipeline-title
    """
    
    # Base universe set to the Q1500US
    # base_universe = Q1500US()
    # initial asset funnel
    # base_universe = Q1500US()
    base_universe = Q500US()
    yesterday_close = USEquityPricing.close.latest
    # roll_mean = SimpleMovingAverage(inputs=[USEquityPricing.close],       window_length=10, mask=base_universe)
    bb = BollingerBands(inputs=[USEquityPricing.close], window_length=10,k=1, mask=base_universe)
    # bb = BollingerBands(inputs = context.aapl, window_length=10, k=1)
    upper_band = bb.upper
    mean_band = bb.middle
    lower_band = bb.lower
    # print bb
    # print upper_band
    percent_diff_upper = (upper_band - mean_band)/mean_band
    # shorts = percent_diff_upper.top(30)
    percent_diff_lower = (lower_band - mean_band)/mean_band
    longs = lower_band.top(20)
    shorts = upper_band.bottom(30)
    # print shorts
    # print longs 
    securities_to_trade = (shorts | longs)
    #-------------------------------------------------
    # mean_10 = SimpleMovingAverage(inputs=[USEquityPricing.close],window=10,mask=base_universe)
    # mean_30 = SimpleMovingAverage(inputs=[USEquityPricing.close],window=10,mase=base_universe)
    # percent_diff = (mean_10 - mean_30)/mean_30
    # shorts = percent_diff.top(25)
    # longs = percent_diff.bottom(25)
    # securities_to_trade = (shorts | longs)
    #-------------------------------------------------

    # Factor of yesterday's close price.

    
    pipe = Pipeline(columns = {
            'longs': longs,
            'shorts': shorts,
        },screen = (securities_to_trade),
    )
    return pipe

# def my_compute_weights(context):
#     long_weight = 0.5/len(context.longs)
#     return long_weight
 
def before_trading_start(context, data):
    
    """
    Called every day before market open.
    """
    # print '. 1 .'
    context.output = pipeline_output('my_pipeline')
    # print "here2", pipeline_output('my_pipeline')
    context.longs = context.output[context.output['longs']==True].index.tolist()
    print context.longs[0]
    context.shorts = context.output[context.output['shorts']==True].index.tolist()
    
    context.long_weight, context.short_weight = my_assign_weights(context)
  
    # These are the securities that we are interested in trading each day.
    context.security_list = context.output.index
     
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
    
    # for security in context.portfolio.positions:
    #     if security not in context.uppers and security not in context.lowers and data.can_trade(security):
    #         order_target_percent(security,0)
    
    # for security in context.lowers:
    #     if data.can_trade(security):
    #         order_target_percent(security,context.long_weight)
            
    # for security in context.uppers:
    #     if data.can_trade(security):
    #         order_target_percent(security,context.short_weight)
    
    pass
 
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
 
def handle_data(context,data):
    """
    Called every minute.
    """
    # make_orders(context, data)
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
