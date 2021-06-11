import alpaca_trade_api as tradeapi

api = tradeapi.REST()

# Check if the market is open now.
clock = api.get_clock()
print('The market is {}'.format('open.' if clock.is_open else 'closed.'))
