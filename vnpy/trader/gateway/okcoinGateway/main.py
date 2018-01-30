#!/usr/bin/python2
# encoding: UTF-8
from PyQt4 import QtCore
import sys
import threading
from okcoinGateway import *

SYMBOL = ['ace', 'act', 'amm', 'ark', 'ast', 'avt', 'bnt', 'btm', 'cmt', 'ctr',
          'cvc', 'dash', 'dat', 'dgb', 'dgd', 'dnt', 'dpy', 'edo', 'elf', 'eng',
          'eos', 'etc', 'evx', 'fun', 'gas', 'gnt', 'gnx', 'hsr', 'icn', 'icx',
          'iota', 'itc', 'kcash', 'knc', 'link', 'lrc', 'ltc', 'mana', 'mco',
          'mda', 'mdt', 'mth', 'nas', 'neo', 'nuls', 'oax', 'omg', 'pay',
          'ppt', 'pra', 'qtum', 'qvt', 'rcn', 'rdn', 'read', 'req', 'rnt', 'salt',
          'san', 'sngls', 'snm', 'snt', 'ssc', 'storj', 'sub', 'swftc',
          'tnb', 'trx', 'ugc', 'ukg', 'vee', 'wrc', 'wtc', 'xem', 'xlm', 'xmr',
          'xrp', 'xuc', 'yoyo', 'zec', 'zrx', '1st']



def pp(coins):
    eventEngine = EventEngine()
    eventEngine.start()

    # 连接登录
    gateway = OkcoinGateway(eventEngine, coins)
    gateway.connect()

def test():

    app = QtCore.QCoreApplication(sys.argv)
    ts = coin2tradeSymbols(SYMBOL)
    print len(ts)
    threads = []
    threads.append(threading.Thread(target=pp, args=(SYMBOL,)))
    for i in range(9):
        threads.append(threading.Thread(target=policy, args=(ts[i*600:(i+1)*600],)))
    threads.append(threading.Thread(target=policy, args=(ts[6000:],)))
        # print(time())
    for t in threads:
        sleep(5)
        t.start()
    t.join()

    sys.exit(app.exec_())



if __name__ == '__main__':
    test()
