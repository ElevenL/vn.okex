#!/usr/bin/python2
# encoding: UTF-8
from PyQt4 import QtCore
import sys
import threading
from multiprocessing import Process, Manager
from okcoinGateway import *

SYMBOL = ['symbol', 'ace', 'act', 'amm', 'ark', 'ast', 'avt', 'bnt', 'btm', 'cmt', 'ctr',
          'cvc', 'dash', 'dat', 'dgb', 'dgd', 'dnt', 'dpy', 'edo', 'elf', 'eng',
          'eos', 'etc', 'evx', 'fun', 'gas', 'gnt', 'gnx', 'hsr', 'icn', 'icx',
          'iota', 'itc', 'kcash', 'knc', 'link', 'lrc', 'ltc', 'mana', 'mco',
          'mda', 'mdt', 'mth', 'nas', 'neo', 'nuls', 'oax', 'omg', 'pay',
          'ppt', 'pro', 'qtum', 'qvt', 'rcn', 'rdn', 'read', 'req', 'rnt', 'salt',
          'san', 'sngls', 'snm', 'snt', 'ssc', 'storj', 'sub', 'swftc',
          'tnb', 'trx', 'ugc', 'ukg', 'vee', 'wrc', 'wtc', 'xem', 'xlm', 'xmr',
          'xrp', 'xuc', 'yoyo', 'zec', 'zrx', '1st']



def pp(coins, laccount, lorders, ltrading):
    app = QtCore.QCoreApplication(sys.argv)
    eventEngine = EventEngine()
    eventEngine.start()

    # 连接登录
    gateway = OkcoinGateway(eventEngine, coins, laccount, lorders, ltrading)
    gateway.connect()
    sys.exit(app.exec_())

if __name__ == '__main__':
    manager = Manager()
    laccount = manager.dict({'free':{},'freezed':{}})
    lorders = manager.dict()
    ltrading = manager.Value('b', False)

    ps = []
    for ss in SYMBOL:
        s = ss
        ps.append(Process(target=pp, args=(s, laccount, lorders, ltrading)))
    for p in ps:
        p.start()
    for p in ps:
        p.join()
