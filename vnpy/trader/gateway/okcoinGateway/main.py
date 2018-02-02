#!/usr/bin/python2
# encoding: UTF-8
from PyQt4 import QtCore
import sys
import threading
from okcoinGateway import *

SYMBOL = ['symbol', 'ace', 'act', 'amm', 'ark', 'ast', 'avt', 'bnt', 'btm', 'cmt', 'ctr',
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
    c = ['mco', 'eos']
    threads = []
    for ss in SYMBOL:
        s = ss
        threads.append(threading.Thread(target=pp, args=(s,)))
        # print(time())
    for t in threads:
        t.start()
        t.join()

    sys.exit(app.exec_())



if __name__ == '__main__':
    test()
