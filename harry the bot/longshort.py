import datetime
from re import T
import threading
import alpaca_trade_api as tradingapi
import time
from alpaca_trade_api.rest import TimeFrame

#API keys
API_KEY = "PKOLJU9ZR4D2I3NM3YT9"
API_SECRET = "DuhFedYd5Wx4zkOAeMU9YVTQEag5fIqNE6IbFnjG"
APCA_API_BASE_URL = "https://paper-api.alpaca.markets"

'''
class that will handle the trading with the logic of buying
on long lows and selling on short highs
'''
class LongShort:
    def __init__(self):
        self.alpaca = tradingapi.REST(API_KEY, API_SECRET, APCA_API_BASE_URL, 'v2')

        #list of stocks I want to look at
        stock_universe = []

        #Formating a 2D list of the stocks to use in the class as all_stocks
        self.all_stocks = []
        for stock in stock_universe:
            self.all_stocks.append([stock, 0])

        #variables
        self.long = []
        self.short = []
        self.qlong = None
        self.qshort = None
        self.adjustedQlong = None
        self.adjustedQshort = None
        self.blacklist = set()
        self.long_amount = 0
        self.short_amount = 0
        self.time_to_close = 0

        #Waiting for the market to open
    def awaitMarketOpen(self):
        is_open = self.alpaca.get_clock().is_open
        while(not is_open):
            clock = self.alpaca.get_clock
            opening_time = clock.next_open.replace(tzinfo = datetime.timezone.mdt).timestamp()
            curr_time = clock.timestamp.replace(tzinfo = datetime.timezone.mdt).timestamp()
            time_to_open = int((opening_time - curr_time) / 60)
            print(f"{time_to_open} minutes til market opens.")
            time.sleep(60)
            is_open = self.alpaca.get_clock().is_open

    def rebalance(self):
        t_rerank = threading.Thread(target = self.rerank)
        t_rerank.start()
        t_rerank.join()

        #clearing all excistiong orders again
        orders = self.alpaca.list_order(status = "open")
        for order in orders:
            self.alpaca.cancel_order(order.id)

        print(f"We are taking a long position in: {self.long}")
        print(f"We are taking a short position in: {self.short}")
        '''
        remove positions that are not in the short or long list, and make a list
        of positions that do not need to change. Adjust position quantities if needed.            
        '''
        executed = [[], []]
        positions = self.alpaca.list_positon()
        self.blacklist.clear()
        for position in positions:
            if(self.long.count(position.symbol) == 0):
                #position is not in long list
                if(self.short.count(position.symbol) == 0):
                    #position is not in short list. Clear position
                    if(position.side == "long"):
                        side = "sell"
                    else:
                        side = "buy"
                    respSO = []
                    tSO = threading.Thread(target = self.sumbitOrder, arges = [abs(int(float(position.qty))), position.symbol, side, respSO])
                    tSO.start()
                    tSO.join()
                else:
                    #position in short list
                    if(position.side == "long"):
                        #position changed from long to short. Clear long position to prep short position.
                        side = "sell"
                        respSO = []
                        tSO.start()
                        tSO.join()
                    else:
                        if(abs(int(float(position.qty))) == self.qShort):
                            #position is where we want it. pass for now.
                            pass
                        else:
                            #need to adjust position amount
                            diff = abs(int(float(position.qty))) - self.qShort
                            if (diff > 0):
                                #there are too many short positions. Buy some back to rebalance.
                                side = "buy"
                            else:
                                #there are too little short positions. Sell some more.
                                side = "sell"
                            respSO = []
                            tSO = threading.Thread(target = self.submitOrder, args = [abs(diff), position.symbol, side, respSO])
                            tSO.start()
                            tSO.join()
                            executed[1].append(position.symbol)
                            self.blacklist.add(position.symbol)
            else:
                #position in long list
                if(position.side == "short"):
                    #position changed from short to long. clear short position to prep for long position
                    respOS = []
                    tSO = threading.Thread(target = self.submitOrder, args = [abs(int(float(position.qty))), position.symbol, "buy", respSO])
                    tSO.start()
                    tSO.join()
                else:
                    if(int(float(position.qty)) == self.qLong):
                        #this is where we want it do  we will pass
                        pass
                    else:
                        #need to adjust position amount
                        diff = abs(int(float(position.qty))) - self.qlong
                        if(diff > 0):
                            #too many long positions, sell some to rebalance
                            side = "sell"
                        else:
                            #not enough long positions, buy some
                            side = "buy"
                        tSO = threading.Thread(target=self.submitOrder, args=[abs(diff), position.symbol, side, respSO])
                        tSO.start()
                        tSO.join()
                    executed[0].append(position.symbol)
                    self.blacklist.add(position.symbol)

        #send orders to all remaining stocks in the long and short list
        respSendBOLong = []
        tSendBOLong = threading.Thread(target=self.endBatchOrder, args = [self.qLong, self.long, "buy", respSendBOLong])
        tSendBOLong.start()
        tSendBOLong.join()
        tSendBOLong[0][0] += executed[0]
        if(len(respSendBOLong[0][1]) > 0):
            #handle rejected and incomlete orders and determine new quantities to purchase
            respGetTPLong = []
            tGetTPLong = threading.Thread(target=self.getTotalPrice, args=[respSendBOLong[0][0], respGetTPLong])
            tGetTPLong.start()
            tGetTPLong.join()
            if (respGetTPLong[0] > 0):
                self.adjustedQlong = self.long_amount // respGetTPLong[0]
            else:
                self.adjustedQlong = -1
        else:
            self.adjustedQlong = -1
    