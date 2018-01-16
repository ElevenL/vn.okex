#!/usr/bin/python2
# encoding: UTF-8
from PyQt4 import QtCore
import sys
from okcoinGateway import *

def test():

    app = QtCore.QCoreApplication(sys.argv)


    eventEngine = EventEngine()
    eventEngine.start()

    #连接登录
    gateway = OkcoinGateway(eventEngine)
    gateway.connect()

    # gateway.subscribe()

    sys.exit(app.exec_())



if __name__ == '__main__':
    test()
