#!/usr/local/bin/python

import sys, os
sys.path.insert(0, os.getcwd()) #Hack to make twistd work when run as root
os.chdir(os.path.split(os.getcwd())[0])
#print os.path.dirname()

import utils
log = utils.get_logger("Twistd")

from twisted.python.log import PythonLoggingObserver
twistdlog = PythonLoggingObserver("Twistd")
twistdlog.start()

from twisted.application import service
from twisted.internet import reactor

testMode = True

flexService = service.MultiService()
application = service.Application("flexvm")
flexService.setServiceParent(application)

def addServices():
    import agi
    import ami
    flexService.addService(agi.getService())
    flexService.addService(ami.getService())

def runTests():
    import call
    call.runTests()
    
reactor.callWhenRunning(addServices)
if testMode:
    reactor.callWhenRunning(runTests)