
# coding: utf-8

# # <center>EC3382 - Assignment 2</center>

# Importing  packages

# In[1]:

import numpy as np


# Example variables, you can see what these numbers are and work through your solutions. We will use different numbers for grading.

# In[2]:

from assignment2_variables import example_stock_prices, example_riskfree, example_target, example_events, example_holdings
print "example_stock_prices", example_stock_prices
print "example_holdings", example_holdings
print "example_riskfree", example_riskfree
print "example_target", example_target
print "example_events", example_events


# ## Part A: Descriptive statistics

# Note that we have imported some variables from the file assignment2_variables. The print statements show you what these variables are so that you can verify what your code is doing. The assert statements provided here in this notebook helps you check whether you solutions are correct. For grading, you will submit only the .py version of the notebook, and we will use a different set of values to evaluate whether your functions are correct.
# 
# To get started, first construct the value of your porfolio from the prices and the holdings. example_prices contains two lists, one for each ticker. example_holdings contains two lists as well, one for each ticker. As we discussed in class, you now construct your portfolio value over time, and from there, your portfolio's returns to use the portfolio evaluation tools that we learned in class. Construct a function that works even if there are more than 2 ticker symbols and more or fewer time periods. That is, do not assume 2 tickers and 6 periods as we did in this example.
# 
# If we ran the code:
# 
# ```python 
# example_prices = get_pf_val(example_stock_prices,example_holdings)
# print example_prices
# ```
# 
# the output would be
# 
# ```python 
# [ 50.  60.  75.  40.  48.  40.]
# ```

# In[13]:

def get_pf_val(prices,holdings):
    holdings = holdings * prices
    output = np.sum(holdings, 0)
    return output
#     frimbob = len(prices) - 1
#     start_prices = prices[0]
#     end_prices = prices[frimbob]
#     start_holdings = holdings[0]
#     end_holdings = holdings[frimbob]
#     return start_prices*start_holdings + end_prices*end_holdings
    

example_prices = get_pf_val(example_stock_prices,example_holdings)
print example_prices


# With the value of the portfolio calculated, we can treat it as the "price" of a single asset. In this first problem, you need to construct a function that computes the mean and the standard deviation of the portfolio. Your function takes a single input, which is a **numpy array** containing the "price" of portfolio at different points in time (note that there isn't a particular sampling frequency: these prices could be prices sampled every minute, every hour, or even every year,) and returns the mean and the standard deviation of the returns, calculated from these prices. The assumption is that prices in the vector are ordered from **oldest to more recent**.  
# 
# Assume that this column vector of prices contains at least 2 elements. Please make use of built-in functions where possible.

# ### Problem A1 
# 
# Create a function `get_returns(a)` that computes the returns (i.e., the percentage difference) of values in a `numpy array`. You may assume that none of the entries is exactly zero. For the zeroth entry, return `np.nan` (for not a number), since there is no entry before it.
# 
# For example, if we ran the code
# ```python
# example_returns = get_returns(a = example_prices)
# print example_returns
# ```
# 
# The output would be
# ```
# [        nan  0.2         0.25       -0.46666667  0.2        -0.16666667]
# ```
# 
# 

# In[4]:

def get_returns(a):
    percentages = [np.nan]
    for i in range(len(a)-1):
        percentages.append((a[i+1]-a[i])/a[i])
    return np.around(percentages, decimals=8)

example_returns = get_returns(a = example_prices)
print example_returns


# ### Problem A2: 
# 
# Create a functions `get_mean(a)` and `get_stddev(a)` that return the mean and standard deviation of a numpy array, *ignoring `np.nan` elements*. You can assume that the input will have at least two non-missing entries.
# 
# For the of standard deviation, use the unbiased definition (i.e., with `n-1` in the denominator).

# Example input
# 
# ```python
# example_returns = get_returns(a = example_prices)
# m = get_mean(a = example_returns)
# s = get_stddev(a = example_returns)
# print "Mean: ", m
# print "Std: ", s
# ```
# 
# Example output
# ```python
# Mean:  0.00333333333333
# Std:  0.311448230048
# ```
# 

# In[5]:

def get_mean(a):
    no_nans_a = [value for value in a if not np.isnan(value)]
    return np.sum(no_nans_a) / len(no_nans_a)

def get_stddev(a):
    m = get_mean(a)
    no_nans_a = [value for value in a if not np.isnan(value)]
    sumy = 0
    for item in no_nans_a:
        sumy += (item - m)**2
    return (sumy/(len(no_nans_a)-1))**.5
    
m = get_mean(a = example_returns)
s = get_stddev(a = example_returns)
print "Mean: ", m
print "Std: ", s


# ##  Part B: Risk measures

# A central goal in attaining returns is doing so while undertaking the least amount of risk. There are multiple measures for the amount of return per unit risk taken. One popular measure is the Sharpe ratio which measures the averaged excess return of the portfolio (including cash) per unit risk taken as measured by the standard deviation of the portfolio's returns. Excess return is the portfolio's return minus the risk free rate.
# 
# The information ratio uses benchmark or target returns instead of the risk free rate. This small change now permits measuring the fund manager's ability to consistently beat a benchmark (eg SP500) instead of just doing better than the risk free rate.
# 
# One critique of the Sharpe ratio is that its measure of risk includes both upside and downside risk. That it, it treats equally a portfolio's tendency to appreciate in value as well as lose value. Clearly, the investor prefers one over the other.
# 
# The Sortino ratio is an attempt to rectify this problem. In the calculation of the standard deviation, it sets equal to zero the returns that are in excess of a user's determined target. In practice, it is common to set the user's target to the risk free rate.
# 
# You will write a set of functions that will allow you to compute the Sharpe, Sortino and information ratios of a `numpy array`.

# ### Part B1: Excess returns
# 
# Write a function `get_excess_returns(returns, baseline)` that takes two `numpy arrays` and returns their difference in a new `numpy array`.

# Expected output
# 
# ```python
# print get_excess_returns(returns = example_returns, baseline = example_riskfree)
# 
# [        nan  0.          0.15       -0.96666667  0.1        -0.26666667]
# ```

# In[6]:

def get_excess_returns(returns, baseline):
    return returns - baseline

print get_excess_returns(returns = example_returns, baseline = example_riskfree)


# ### Part B2: Sharpe and information ratios
# 
# Now use the three functions you just defined in parts A1, A2 and B1 to create a function `get_ratio(a, baseline)`. This function does the following:
# 
# + Computes the returns on the a
# 
# + Computes the difference between the returns above and baseline
# 
# + Outputs the ratio of the mean and standard deviation of this difference
# 
# Explain how to use your function to compute the Sharpe and information ratios.

# ```python
# Example output:
# sharpe      = get_ratio(...)
# print sharpe
# -0.427974678811
# 
# information      = get_ratio(...)
# print information
# -0.513327002339
# ```

# In[7]:

def get_ratio(a, baseline):
    pass

sharpe = get_ratio(a=example_prices, baseline=example_riskfree)
print sharpe
#information = get_ratio(...)
#print information


# ### Part B3: Downside semideviation

# Now create a function `get_downside_semideviation(a)` that:
# 
# + Changes all positive entries of the input `a` to zero
# + Outputs the standard deviation of the modified a
# 
# Example output to guide you:
# ```python
# print get_downside_semideviation(get_excess_returns(example_returns, example_target))
# 0.277037903544
# ```

# In[8]:

def get_downside_semideviation(a):
    for item in a:
        if item < 0:
            item = 0
    return get_stddev(a)

print get_downside_semideviation(get_excess_returns(example_returns, example_target))


# ### Part B4: Sortino ratio

# Modify your `get ratio` function to include a new option `ratio`, as in `get_ratio(a, baseline, downside_semi_stddev)`. Your function should do the following:
# 
# ```
# Compute the returns on the input a
# 
# Compute the difference between the returns above and baseline
# 
# If downsize_semi_stddev is False:
#     
#     Output the ratio of the mean and standard deviation of the difference
# 
# Else:
# 
#     Output the ratio of the mean and downside standard semideviation of the difference
# 
# ```
#     
# 
# Moreover, the `downside_semi_stddev` argument should have the boolean value `False` as default.
# 
# Explain how you would get the sharpe, sortino and information ratios using your new function.

# Example
# 
# ```python
# print get_ratio(example_prices, example_riskfree, True)
# -0.469676155183
# 
# print get_ratio(example_prices, example_riskfree, False)
# -0.427974678811
# ```

# In[9]:

def get_ratio(a, baseline, downside_semi_stddev = False):
    pass

#print get_ratio(example_prices, example_riskfree, True)
#print get_ratio(example_prices, example_riskfree, False)


# ## Part C

# Another commonly used measure of the downside risk of a portfolio is the largest drop in value experienced since assuming the investment position. In other words, for a given period in time, the investor looks back at the value of her portfolio and considers the highest historical value of the portfolio. The investor then computes the percent loss (if any) between the current value of the portfolio and its peak value.
# 
# Another way of putting it is to interpret the drawdown as the size of the regret. The investor regrets not selling the portfolio in the past when it was at a higher price. The size of the hypothetical loss is the drawdown at a given point in time.
# 
# The maximum drawdown is the maximum drawdown across all the dates. It refers to the largest  loss that the investor could have experienced over the holding period of the portfolio.
# 
# Write down a function `get_max_drawdown(a)` to calculate the maximum drawdown. You do not need to output the drawdown times, just the value itself. 

# Example output 
# 
# ```python
# print "Max drawdown: ", get_max_drawdown(a = example_prices)
# Max drawdown: 0.466666666667
# ```

# In[10]:

def get_max_drawdown(a):
    a = get_returns(a)
    a = [value for value in a if not np.isnan(value)]
    return np.abs(np.min(a))
        
print "Max drawdown: ", get_max_drawdown(a = example_prices)


# ## Part D: Event Detection

# Write a function `detect_three_negative(a)` that scans the input a for the event "three negative values in a row", and outputs the third day in which the event was detected. Importantly after each time the event is detected, we restart counting. So four or five consecutive negative numbers only count as one event, on the third day.

# Example:
# ```python
# 
# print example_events
# [ 1. -1. -2. -3. -1.  1.  2. -3.  4. -1. -1. -1.]
# print detect_three_negative(a = example_events)
# [3, 11]
# ```

# In[11]:

def detect_three_negative(a):
    event_array = []
    event_alarm = "on"
    d1 = 0
    d2 = 0
    d3 = 0
    for i in range(len(a)):
        d1 = d2
        d2 = d3
        d3 = a[i]
        if (d1<0)&(d2<0)&(d3<0)&(event_alarm == "on"):
            event_array.append(i)
            event_alarm = "off"
        if d3 > -1:
            event_alarm = "on"
    return event_array
    

print example_events
print detect_three_negative(a = example_events)


# In[ ]:



