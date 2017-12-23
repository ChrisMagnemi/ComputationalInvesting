import numpy as np
example_stock_prices = np.array([[10, 12, 15, 10, 12, 10.0],[20, 24, 30, 20, 24, 20.0]])
example_holdings = np.array([[1, 1, 1, 2, 2, 2.0],[2, 2, 2, 1, 1, 1.0]])
example_riskfree = np.array([.1, .2, .1, 0.5, .1, .1])
example_target = np.array([.3, 0.0, .3, -0.2, .25, .5])
example_events = np.array([1,-1,-2,-3,-1, 1.0, 2.0, -3.0, 4, -1, -1, -1]) 
