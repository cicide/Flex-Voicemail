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


familyService = service.MultiService()
application = service.Application("Family_Plan_Service")
familyService.setServiceParent(application)

def addServices():

    import agi
    import ami
    import txdbinterface
    import workers
#    import web
    familyService.addService(agi.getService())
    familyService.addService(ami.getService())
#    familyService.addService(web.getService())
    familyService.addService(workers.getService())


def getData():
    import group
    group.getDocs('family')

def tryBadGroup():
    import group, time
    retval = group.registerGroup('18005551212', time.time(), time.time())
    retval.addCallback(logResult)

def logResult(result):
    log.info("Received return value %s for register of bad group" % result)

reactor.callWhenRunning(addServices)
reactor.callLater(0, getData)
#reactor.callLater(5, tryBadGroup)
