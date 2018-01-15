# encoding: UTF-8

'''
vn.okcoin的gateway接入

注意：
1. 前仅支持USD和CNY的现货交易，USD的期货合约交易暂不支持
'''


import os
import json
from datetime import datetime
from time import sleep
from copy import copy, deepcopy
from threading import Condition
from Queue import Queue
from threading import Thread
from time import sleep
from operator import itemgetter
from itertools import *

from okcoin.vnokcoin import OkCoinApi,OKCOIN_USD
from vtGateway import *
from vtFunction import getJsonPath

# 价格类型映射
priceTypeMap = {}
priceTypeMap['buy'] = (DIRECTION_LONG, PRICETYPE_LIMITPRICE)
priceTypeMap['buy_market'] = (DIRECTION_LONG, PRICETYPE_MARKETPRICE)
priceTypeMap['sell'] = (DIRECTION_SHORT, PRICETYPE_LIMITPRICE)
priceTypeMap['sell_market'] = (DIRECTION_SHORT, PRICETYPE_MARKETPRICE)
priceTypeMapReverse = {v: k for k, v in priceTypeMap.items()} 

# 方向类型映射
directionMap = {}
directionMapReverse = {v: k for k, v in directionMap.items()}

# 委托状态印射
statusMap = {}
statusMap[-1] = STATUS_CANCELLED
statusMap[0] = STATUS_NOTTRADED
statusMap[1] = STATUS_PARTTRADED
statusMap[2] = STATUS_ALLTRADED
statusMap[4] = STATUS_UNKNOWN

############################################
## 交易合约代码
############################################

SYMBOL = ['ace', 'act', 'amm', 'ark', 'ast', 'avt', 'bnt', 'btm', 'cmt', 'ctr',
          'cvc', 'dash', 'dat', 'dgb', 'dgd', 'dnt', 'dpy', 'edo', 'elf', 'eng',
          'eos', 'etc', 'evx', 'fun', 'gas', 'gnt', 'gnx', 'hsr', 'icn', 'icx',
          'iota', 'itc', 'kcash', 'knc', 'link', 'lrc', 'ltc', 'mana', 'mco',
          'mda', 'mdt', 'mth', 'nas', 'neo', 'nuls', 'oax', 'omg', 'pay',
          'ppt', 'pro', 'qtum', 'qvt', 'rcn', 'rdn', 'read', 'req', 'rnt', 'salt',
          'san', 'sngls', 'snm', 'snt', 'ssc', 'storj', 'sub', 'swftc',
          'tnb', 'trx', 'ugc', 'ukg', 'vee', 'wrc', 'wtc', 'xem', 'xlm', 'xmr',
          'xrp', 'xuc', 'yoyo', 'zec', 'zrx', '1st']



############################################


########################################################################
class OkcoinGateway(VtGateway):
    """OkCoin接口"""

    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName='OKCOIN'):
        """Constructor"""
        super(OkcoinGateway, self).__init__(eventEngine, gatewayName)
        
        self.api = Api(self)     
        
        self.leverage = 0
        self.connected = False

        self.qryEnabled = True
        self.fileName = self.gatewayName + '_connect.json'
        self.filePath = getJsonPath(self.fileName, __file__)
        self.registeHandle()
        self.tradeSymbols = []
        self.tradeTest = True

        self.coin2tradeSymbols()

    #----------------------------------------------------------------------
    def connect(self):
        """连接"""
        # 载入json文件
        try:
            f = file(self.filePath)
        except IOError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'读取连接配置出错，请检查'
            self.onLog(log)
            return
        
        # 解析json文件
        setting = json.load(f)
        try:
            host = str(setting['host'])
            apiKey = str(setting['apiKey'])
            secretKey = str(setting['secretKey'])
            trace = setting['trace']
            leverage = setting['leverage']
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return            
        
        # 初始化接口
        self.leverage = leverage
        
        # if host == 'CNY':
        #     host = vnokcoin.OKCOIN_CNY
        # else:
        #     host = vnokcoin.OKCOIN_USD
        host = OKCOIN_USD
        self.api.active = True
        self.api.connect(host, apiKey, secretKey, trace)
        
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = u'接口初始化成功'
        self.onLog(log)
        
        # 启动查询
        self.initQuery()
        self.startQuery()

    #----------------------------------------------------------------------
    def coin2tradeSymbols(self):
        """币种转换成合约代码"""
        coinList = []
        for k in SYMBOL:
            coinList.append(['btc', k, 'eth'])

        for c in coinList:
            s = ['_'.join((c[1], c[0])),
                 '_'.join((c[1], c[2])),
                 'eth_btc']
            self.tradeSymbols.append(s)


    #----------------------------------------------------------------------
    def login(self):
        """订阅订单回报"""
        return self.api.login()


    #----------------------------------------------------------------------
    def subscribe(self):
        """订阅行情"""
        for coin in SYMBOL[:10]:
            bs = coin + '_btc'
            es = coin + '_eth'
            self.api.subscribeSpotDepth(bs, '5')
            self.api.subscribeSpotDepth(es, '5')
        
    #----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        return self.api.spotSendOrder(orderReq)
        
    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.api.spotCancel(cancelOrderReq)
        
    #----------------------------------------------------------------------
    def qryAccount(self):
        """查询账户资金"""
        self.api.spotUserInfo()
        
    #----------------------------------------------------------------------
    def qryPosition(self):
        """查询持仓"""
        pass
        
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.api.active = False
        self.api.close()
        
    #----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            # 需要循环的查询函数列表
            # self.qryFunctionList = [self.qryAccount]
            self.qryFunctionList = [self.tradePolicy]
            
            self.qryCount = 0           # 查询触发倒计时
            self.qryTrigger = 1         # 查询触发点
            self.qryNextFunction = 0    # 上次运行的查询函数索引
            
            self.startQuery()  
    
    #----------------------------------------------------------------------
    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        self.qryCount += 1
        
        if self.qryCount > self.qryTrigger:
            # 清空倒计时
            self.qryCount = 0
            
            # 执行查询函数
            function = self.qryFunctionList[self.qryNextFunction]
            function()
            
            # 计算下次查询函数的索引，如果超过了列表长度，则重新设为0
            self.qryNextFunction += 1
            if self.qryNextFunction == len(self.qryFunctionList):
                self.qryNextFunction = 0
                
    #----------------------------------------------------------------------
    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)
    
    #----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled

    # ----------------------------------------------------------------------
    def pTick(self, event):
        tick = event.dict_['data']
        # print '========tick============='
        # print tick.symbol
        # print tick.askPrice1
        # print tick.askVolume1
        # print tick.bidPrice1
        # print tick.bidVolume1
        # if self.tradeTest:
        #     req = VtOrderReq()
        #     req.symbol = tick.symbol
        #     req.priceType = 'sell'
        #     req.price = tick.bidPrice1
        #     req.volume = 0.09
        #     self.sendOrder(req)
        #     print 'send order!'
        #     self.tradeTest = False

    # ----------------------------------------------------------------------
    def pAccount(self, event):
        account = event.dict_['data']
        # print '=======account========'
        # print self.api.account

    # ----------------------------------------------------------------------
    def pOrder(self, event):
        order = event.dict_['data']
        # print '=======order========'
        # print order.symbol
        # print order.orderID
        # print order.status

    # ----------------------------------------------------------------------
    def pBalance(self, event):
        balance = event.dict_['data']
        # print '=======balance========'
        # print self.api.account

    # ----------------------------------------------------------------------
    def pLog(self, event):
        log = event.dict_['data']
        loginfo = ':'.join([log.logTime, log.logContent])
        # send_msg(loginfo)
        self.today = datetime.now().date().strftime('%Y-%m-%d')
        filename = config.basePath + 'myctp/vn.trader/ctpGateway/log/%s' % ('tradeLog' + '-' + self.today + '.txt')
        if os.path.exists(filename):
            fp = file(filename, 'a+')
            try:
                fp.write(loginfo.encode('utf-8') + '\n')
            finally:
                fp.close()
        else:
            fp = file(filename, 'wb')
            try:
                fp.write(loginfo.encode('utf-8') + '\n')
            finally:
                fp.close()

    # ----------------------------------------------------------------------
    def prepare(self, symbols):
        '''获取盈利空间和转换后的btc交易量'''
        # print 'in prepare'
        # print self.api.depth
        depth = deepcopy(self.api.depth)
        for s in symbols:
            if s not in depth.keys():
                return depth, 0, 0
        profit = (float(depth[symbols[1]].bidPrice1) * float(depth[symbols[2]].bidPrice1)) / \
                float(depth[symbols[0]].askPrice1)
        if profit > 1.01:   #设置最小盈利空间为1.5%
            amount = []
            amount.append(float(depth[symbols[0]].askPrice1) * min(float(depth[symbols[0]].askVolume1),
                                                                     float(depth[symbols[1]].bidVolume1)))
            amount.append(float(depth[symbols[2]].bidPrice1) * float(depth[symbols[2]].bidVolume1))
            amount.sort()
            return depth, profit, amount[0]
        else:
            return depth, 0, 0

    # ----------------------------------------------------------------------
    def getAmount(self):
        '''获取盈利最大的合约组合，并计算每个合约的交易量'''
        for ts in self.tradeSymbols:
            depth, profit, amount = self.prepare(ts)
            if amount > 0.002:     #设置最小btc交易量为0.002
                tradeSymbol = {}
                tradeSymbol['symbol'] = ts
                tradeSymbol['profit'] = profit
                tradeSymbol['amount'] = amount
                tradeSymbol['total'] = profit * amount
                print '=======in getAmount======='
                print 'symbol:', tradeSymbol['symbol']
                print 'profit:', tradeSymbol['profit']
                print 'amount:', tradeSymbol['amount']
                print 'depth1:', depth[tradeSymbol['symbol'][0]].askPrice1, depth[tradeSymbol['symbol'][0]].askVolume1
                print 'depth2:', depth[tradeSymbol['symbol'][1]].bidPrice1, depth[tradeSymbol['symbol'][1]].bidVolume1
                print 'depth3:', depth[tradeSymbol['symbol'][2]].bidPrice1, depth[tradeSymbol['symbol'][2]].bidVolume1

                if self.api.account['free']['btc'] <= tradeSymbol['amount']:
                    initAmount = self.api.account['free']['btc']
                else:
                    initAmount = tradeSymbol['amount']
                amountDict = {}
                amountDict[tradeSymbol['symbol'][0]] = round(initAmount * 0.998 / float(depth[tradeSymbol['symbol'][0]].askPrice1), 8)
                amountDict[tradeSymbol['symbol'][1]] = round(amountDict[tradeSymbol['symbol'][0]] * 0.99898, 8)
                amountDict[tradeSymbol['symbol'][2]] = round(((amountDict[tradeSymbol['symbol'][1]]*\
                                                                     float(depth[tradeSymbol['symbol'][1]].bidPrice1) * 0.9989)), 8)
                return depth, tradeSymbol['symbol'], amountDict
        else:
            return depth, [], {}

    # ----------------------------------------------------------------------
    def tradePolicy(self):
        tradeList = []
        depth, symbols, amount = self.getAmount()
        if symbols == []:
            return False
        self.api.writeLog('[Start Polocy]')
        # if True:
        #     return
        for i in range(20):
            if symbols[0] not in tradeList and self.api.account['free']['btc'] >= amount[symbols[0]] * float(depth[symbols[0]].askPrice1):
                # print 'step1'
                req = VtOrderReq()
                req.symbol = symbols[0]
                req.priceType = 'buy_market'
                # print 'step2'
                req.price = round(float(depth[symbols[0]].askPrice1) * amount[symbols[0]] * 0.9, 8)
                # print 'step3'
                req.volume = ''
                # print 'step4'
                self.sendOrder(req)
                tradeList.append(symbols[0])
            if symbols[1] not in tradeList and self.api.account['free'][symbols[1].split('_')[0]] >= amount[symbols[1]] * 0.8:
                req = VtOrderReq()
                req.symbol = symbols[1]
                req.priceType = 'sell_market'
                req.price = ''
                req.volume = self.api.account['free'][symbols[1].split('_')[0]] * 0.999
                self.sendOrder(req)
                tradeList.append(symbols[1])
            if symbols[2] not in tradeList and self.api.account['free']['eth'] >= amount[symbols[2]] * 0.8:
                req = VtOrderReq()
                req.symbol = symbols[2]
                req.priceType = 'sell_market'
                req.price = ''
                req.volume = self.api.account['free']['eth'] * 0.999
                self.sendOrder(req)
                tradeList.append(symbols[2])
            if len(tradeList) >= 3 and len(self.api.orderDict) == 0:
                self.api.writeLog('[End Policy]succssed complete all trade!')
                return
            sleep(0.5)
        orders = deepcopy(self.api.orderDict)
        for id in orders.keys():
            req = VtCancelOrderReq
            req.symbol = orders[id].symbol
            req.orderID = orders[id].orderID
            self.cancelOrder(req)
            self.api.orderDict.pop(id)
        self.api.writeLog('[End Policy]Failed complete all trade!')

    # ----------------------------------------------------------------------
    def registeHandle(self):
        '''注册处理机'''
        self.eventEngine.register(EVENT_TICK, self.pTick)
        self.eventEngine.register(EVENT_ACCOUNT, self.pAccount)
        self.eventEngine.register(EVENT_ORDER, self.pOrder)
        self.eventEngine.register(EVENT_POSITION, self.pBalance)

########################################################################
class Api(OkCoinApi):
    """OkCoin的API实现"""

    #----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super(Api, self).__init__()
        
        self.gateway = gateway                  # gateway对象
        self.gatewayName = gateway.gatewayName  # gateway对象名称
        
        self.active = True             # 若为True则会在断线后自动重连

        self.cbDict = {}
        self.tickDict = {}
        self.orderDict = {}
        self.account = {}
        self.account['free'] = {}
        self.account['freezed'] = {}
        self.balance = {}
        self.depth = {}
        self.tickCount = 0
        
        self.localNo = 0                # 本地委托号
        self.localNoQueue = Queue()     # 未收到系统委托号的本地委托号队列
        self.localNoDict = {}           # key为本地委托号，value为系统委托号
        self.orderIdDict = {}           # key为系统委托号，value为本地委托号
        self.cancelDict = {}            # key为本地委托号，value为撤单请求

        
    #----------------------------------------------------------------------
    def onMessage(self, ws, evt):
        """信息推送"""
        data = self.readData(evt)[0]
        # print data
        channel = data['channel']
        callback = self.getCallback(channel)
        callback(data)
        
    #----------------------------------------------------------------------
    def onError(self, ws, evt):
        """错误推送"""
        error = VtErrorData()
        error.gatewayName = self.gatewayName
        error.errorMsg = str(evt)
        self.gateway.onError(error)
        
    #----------------------------------------------------------------------
    def onClose(self, ws):
        """接口断开"""
        # 如果尚未连上，则忽略该次断开提示
        if not self.gateway.connected:
            return
        
        self.gateway.connected = False
        self.writeLog(u'服务器连接断开')
        
        # 重新连接
        if self.active:
            
            def reconnect():
                while not self.gateway.connected:            
                    self.writeLog(u'等待10秒后重新连接')
                    sleep(5)
                    if not self.gateway.connected:
                        self.reconnect()
            
            t = Thread(target=reconnect)
            t.start()
        
    #----------------------------------------------------------------------
    def onOpen(self, ws):       
        """连接成功"""
        self.gateway.connected = True
        self.writeLog(u'服务器连接成功')
        
        # 连接后查询账户和委托数据
        self.writeLog(u'登陆')
        self.login()
        self.writeLog(u'查询账户信息')
        self.spotUserInfo()
        #
        # self.spotOrderInfo(vnokcoin.TRADING_SYMBOL_LTC, '-1')
        # self.spotOrderInfo(vnokcoin.TRADING_SYMBOL_BTC, '-1')
        # self.spotOrderInfo(vnokcoin.TRADING_SYMBOL_ETH, '-1')

        # 连接后订阅现货的成交和账户数据
        # self.subscribeSpotTrades('mco_btc')
        # self.subscribeSpotUserInfo()
        #
        # self.subscribeSpotTicker(vnokcoin.SYMBOL_BTC)
        # self.subscribeSpotTicker(vnokcoin.SYMBOL_LTC)
        # self.subscribeSpotTicker(vnokcoin.SYMBOL_ETH)
        a = ['bch']
        for coin in SYMBOL:
            bs = coin + '_btc'
            es = coin + '_eth'
            self.subscribeSpotDepth(bs, '5')
            self.subscribeSpotDepth(es, '5')
        self.subscribeSpotDepth('eth_btc', '5')
        # self.subscribeSpotDepth('cmt_btc', '5')
        # self.subscribeSpotDepth('ltc_btc', '5')
        # self.subscribeSpotDepth(vnokcoin.SYMBOL_LTC, vnokcoin.DEPTH_20)
        # self.subscribeSpotDepth(vnokcoin.SYMBOL_ETH, vnokcoin.DEPTH_20)

        # 如果连接的是USD网站则订阅期货相关回报数据
        # if self.currency == vnokcoin.CURRENCY_USD:
        #     self.subscribeFutureTrades()
        #     self.subscribeFutureUserInfo()
        #     self.subscribeFuturePositions()
        
        # 返回合约信息
        # if self.currency == vnokcoin.CURRENCY_CNY:
        #     l = self.generateCnyContract()
        # else:
        #     l = self.generateUsdContract()
        #
        # for contract in l:
        #     contract.gatewayName = self.gatewayName
        #     self.gateway.onContract(contract)
            
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """快速记录日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        print log.logTime,log.logContent
        self.gateway.onLog(log)

    # ----------------------------------------------------------------------
    def getCallback(self, channel):
        """初始化回调函数"""
        if channel.endswith('_ticker'):
            return self.onTicker
        elif channel.endswith('_depth_5'):
            return self.onDepth
        elif channel.endswith('_userinfo'):
            return self.onSpotUserInfo
        elif channel.endswith('_orderinfo'):
            return self.onSpotOrderInfo
        elif channel == 'ok_spot_order':
            return self.onSpotTrade
        elif channel == 'ok_spot_cancel_order':
            return self.onSpotCancelOrder
        elif channel.endswith('_order'):
            return self.onSpotSubTrades
        elif channel.endswith('_balance'):
            return self.onSpotSubUserInfo


    #----------------------------------------------------------------------
    def onTicker(self, data):
        """"""
        if 'data' not in data:
            return
        
        channel = data['channel']
        symbol = channelSymbolMap[channel]
        
        if symbol not in self.tickDict:
            tick = VtTickData()
            tick.symbol = symbol
            tick.vtSymbol = symbol
            tick.gatewayName = self.gatewayName
            self.tickDict[symbol] = tick
        else:
            tick = self.tickDict[symbol]
        
        rawData = data['data']
        tick.highPrice = float(rawData['high'])
        tick.lowPrice = float(rawData['low'])
        tick.lastPrice = float(rawData['last'])
        tick.volume = float(rawData['vol'])
        #tick.date, tick.time = generateDateTime(rawData['timestamp'])
        newtick = copy(tick)
        self.gateway.onTick(newtick)
    
    #----------------------------------------------------------------------
    def onDepth(self, data):
        """"""
        if 'data' not in data:
            return
        channel = data['channel']
        a = channel.split('_')
        symbol = str('_'.join((a[3], a[4])))
        # symbol = channelSymbolMap[channel]
        if symbol not in self.tickDict:
            tick = VtTickData()
            tick.symbol = symbol
            tick.vtSymbol = symbol
            tick.gatewayName = self.gatewayName
            self.tickDict[symbol] = tick
        else:
            tick = self.tickDict[symbol]
        
        if 'data' not in data:
            return
        rawData = data['data']
        
        tick.bidPrice1, tick.bidVolume1 = rawData['bids'][0]
        tick.bidPrice2, tick.bidVolume2 = rawData['bids'][1]
        tick.bidPrice3, tick.bidVolume3 = rawData['bids'][2]
        tick.bidPrice4, tick.bidVolume4 = rawData['bids'][3]
        tick.bidPrice5, tick.bidVolume5 = rawData['bids'][4]
        
        tick.askPrice1, tick.askVolume1 = rawData['asks'][-1]
        tick.askPrice2, tick.askVolume2 = rawData['asks'][-2]
        tick.askPrice3, tick.askVolume3 = rawData['asks'][-3]
        tick.askPrice4, tick.askVolume4 = rawData['asks'][-4]
        tick.askPrice5, tick.askVolume5 = rawData['asks'][-5]     
        
        tick.date, tick.time = generateDateTime(rawData['timestamp'])
        newtick = copy(tick)
        # self.tickCount += 1
        self.depth[symbol] = newtick
        # print self.tickCount
        # print self.depth
        # print self.depth
        self.gateway.onTick(newtick)
    
    #----------------------------------------------------------------------
    def onSpotUserInfo(self, data):
        """现货账户资金推送"""
        rawData = data['data']
        # print rawData
        info = rawData['info']
        funds = rawData['info']['funds']
        for coin in funds['freezed']:
            self.account['freezed'][coin] = float(funds['freezed'][coin])
            self.account['free'][coin] = float(funds['free'][coin])
        # print self.account
        # # 持仓信息
        # for symbol in ['btc', 'ltc','eth', self.currency]:
        #     if symbol in funds['free']:
        #         pos = VtPositionData()
        #         pos.gatewayName = self.gatewayName
        #
        #         pos.symbol = symbol
        #         pos.vtSymbol = symbol
        #         pos.vtPositionName = symbol
        #         # pos.direction = DIRECTION_NET
        #
        #         pos.frozen = float(funds['freezed'][symbol])
        #         pos.position = pos.frozen + float(funds['free'][symbol])
        #
        #         self.gateway.onPosition(pos)

        # 账户资金
        account = VtAccountData()
        account.gatewayName = self.gatewayName
        account.accountID = self.gatewayName
        account.vtAccountID = account.accountID
        account.balance = float(funds['free']['btc'])
        self.gateway.onAccount(account)    
        
    #----------------------------------------------------------------------

    def onSpotSubUserInfo(self, data):
        """现货账户资金推送"""
        rawData = data['data']
        funds = rawData['info']
        self.writeLog(funds)
        for coin in funds['free']:
            self.account['freezed'][coin] = float(funds['freezed'][coin])
            self.account['free'][coin] = float(funds['free'][coin])
        # 持仓信息
        for symbol in funds['free']:
            pos = VtPositionData()
            pos.gatewayName = self.gatewayName

            pos.symbol = symbol
            pos.vtSymbol = symbol
            pos.vtPositionName = symbol
            # pos.direction = DIRECTION_NET

            pos.frozen = float(funds['freezed'][symbol])
            pos.position = pos.frozen + float(funds['free'][symbol])
            self.gateway.onPosition(pos)

        # # 账户资金
        # account = VtAccountData()
        # account.gatewayName = self.gatewayName
        # account.accountID = self.gatewayName
        # account.vtAccountID = account.accountID
        # account.balance = float(funds['free']['btc'])
        # self.gateway.onAccount(account)
                
    #----------------------------------------------------------------------

    def onSpotSubTrades(self, data):
        """成交和委托推送"""
        if 'data' not in data:
            return
        rawData = data['data']
        self.writeLog(rawData)
        # 本地和系统委托号
        orderId = str(rawData['orderId'])

        # 委托信息
        if orderId not in self.orderDict.keys():
            order = VtOrderData()
            order.gatewayName = self.gatewayName
            order.symbol = rawData['symbol']
            order.vtSymbol = order.symbol
            order.orderID = str(rawData['orderId'])
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
            order.price = float(rawData['tradeUnitPrice'])
            order.totalVolume = float(rawData['tradeAmount'])
            order.direction = rawData['tradeType']
            self.orderDict[orderId] = order
        else:
            order = self.orderDict[orderId]

        order.tradedVolume = float(rawData['completedTradeAmount'])
        order.status = rawData['status']
        self.orderDict[orderId] = order
        if str(order.status) == '2':
            self.orderDict.pop(order.orderID)
        self.gateway.onOrder(copy(order))

        # 成交信息
        if 'sigTradeAmount' in rawData and float(rawData['sigTradeAmount'])>0:
            trade = VtTradeData()
            trade.gatewayName = self.gatewayName

            trade.symbol = rawData['symbol']
            trade.vtSymbol = order.symbol

            trade.tradeID = str(rawData['orderId'])
            trade.vtTradeID = '.'.join([self.gatewayName, trade.tradeID])

            trade.orderID = str(rawData['orderId'])
            trade.vtOrderID = '.'.join([self.gatewayName, trade.orderID])

            trade.price = float(rawData['sigTradePrice'])
            trade.volume = float(rawData['sigTradeAmount'])

            trade.direction = rawData['tradeType']

            trade.tradeTime = datetime.now().strftime('%H:%M:%S')

            self.gateway.onTrade(trade)

        
    #----------------------------------------------------------------------
    def onSpotOrderInfo(self, data):
        """委托信息查询回调"""
        rawData = data['data']
        
        for d in rawData['orders']:
            self.localNo += 1
            localNo = str(self.localNo)
            orderId = str(d['order_id'])
            
            self.localNoDict[localNo] = orderId
            self.orderIdDict[orderId] = localNo
            
            if orderId not in self.orderDict:
                order = VtOrderData()
                order.gatewayName = self.gatewayName
                
                order.symbol = d['symbol']
                order.vtSymbol = order.symbol
    
                order.orderID = localNo
                order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
                
                order.price = d['price']
                order.totalVolume = d['amount']
                order.direction = d['type']
                
                self.orderDict[orderId] = order
            else:
                order = self.orderDict[orderId]
                
            order.tradedVolume = d['deal_amount']
            order.status = d['status']
            self.orderDict[orderId] = order
            # print '==========order============'
            # print order.symbol
            # print order.orderId
            # print order.status
            self.gateway.onOrder(copy(order))
    
    #----------------------------------------------------------------------
    def generateSpecificContract(self, contract, symbol):
        """生成合约"""
        new = copy(contract)
        new.symbol = symbol
        new.vtSymbol = symbol
        new.name = symbol
        return new

    #----------------------------------------------------------------------
    def generateCnyContract(self):
        """生成CNY合约信息"""
        contractList = []
        
        contract = VtContractData()
        contract.exchange = EXCHANGE_OKCOIN
        contract.productClass = PRODUCT_SPOT
        contract.size = 1
        contract.priceTick = 0.01
        
        contractList.append(self.generateSpecificContract(contract, BTC_CNY_SPOT))
        contractList.append(self.generateSpecificContract(contract, LTC_CNY_SPOT))
        contractList.append(self.generateSpecificContract(contract, ETH_CNY_SPOT))

        return contractList
    
    #----------------------------------------------------------------------
    def generateUsdContract(self):
        """生成USD合约信息"""
        contractList = []
        
        # 现货
        contract = VtContractData()
        contract.exchange = EXCHANGE_OKCOIN
        contract.productClass = PRODUCT_SPOT
        contract.size = 1
        contract.priceTick = 0.01
        
        contractList.append(self.generateSpecificContract(contract, BTC_USD_SPOT))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_SPOT))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_SPOT))

        # 期货
        contract.productClass = PRODUCT_FUTURES
        
        contractList.append(self.generateSpecificContract(contract, BTC_USD_THISWEEK))
        contractList.append(self.generateSpecificContract(contract, BTC_USD_NEXTWEEK))
        contractList.append(self.generateSpecificContract(contract, BTC_USD_QUARTER))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_THISWEEK))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_NEXTWEEK))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_QUARTER))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_THISWEEK))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_NEXTWEEK))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_QUARTER))
        
        return contractList        
    
    #----------------------------------------------------------------------
    def onSpotTrade(self, data):
        """委托回报"""
        print 'onSpotTrade', data
        rawData = data['data']
        if 'order_id' not in rawData:
            self.writeLog('[order]error_code:%s' % str(rawData['error_code']))
        orderId = rawData['order_id']
        # print orderId
        # 尽管websocket接口的委托号返回是异步的，但经过测试是
        # 符合先发现回的规律，因此这里通过queue获取之前发送的
        # 本地委托号，并把它和推送的系统委托号进行映射
        # localNo = self.localNoQueue.get_nowait()
        
        # self.localNoDict[localNo] = orderId
        # self.orderIdDict[orderId] = localNo
        
        # 检查是否有系统委托号返回前就发出的撤单请求，若有则进
        # 行撤单操作
        # if localNo in self.cancelDict:
        #     req = self.cancelDict[localNo]
        #     self.spotCancel(req)
        #     del self.cancelDict[localNo]
    
    #----------------------------------------------------------------------
    def onSpotCancelOrder(self, data):
        """撤单回报"""
        pass
    
    #----------------------------------------------------------------------
    def spotSendOrder(self, req):
        """发单"""
        self.spotTrade(req.symbol, req.priceType, str(req.price), str(req.volume))
        self.writeLog('[SendOrder]%s|%s|%s|%s' % (req.symbol, req.priceType, str(req.price), str(req.volume)))
        # 本地委托号加1，并将对应字符串保存到队列中，返回基于本地委托号的vtOrderID
        self.localNo += 1
        self.localNoQueue.put(str(self.localNo))
        vtOrderID = '.'.join([self.gatewayName, str(self.localNo)])
        return vtOrderID
    
    #----------------------------------------------------------------------
    def spotCancel(self, req):
        """撤单"""
        symbol = req.symbol
        self.spotCancelOrder(req.symbol, req.orderID)
        self.writeLog('[CancelOrder]%s|%s' % (req.symbol, req.orderID))
    
#----------------------------------------------------------------------
def generateDateTime(s):
    """生成时间"""
    dt = datetime.fromtimestamp(float(s)/1e3)
    time = dt.strftime("%H:%M:%S.%f")
    date = dt.strftime("%Y%m%d")
    return date, time
