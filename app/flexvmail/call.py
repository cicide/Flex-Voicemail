#!/usr/local/bin/python
"""
Call state module.

implements call methods and keeps state for extensions
"""

import time
import utils
import dbapi
from datetime import datetime

log = utils.get_logger("Call")

class Call:

    def __init__(self, agi, ivrName, callerId, channelInfo):
        self.agi =agi
        self.InitialIvrName = ivrName
        self.callerId = callerId
        self.channelInfo = channelInfo
        self.ivrFilo = []
        self.ivrLoadedNames = []
        
    def onError(self, result=None):
        return False, {}
        
    def start(self):
        userData = dbapi.checkUser(cid)
        ivrName = self.InitialIvrName
        while ivrName:
            if ivrName in self.ivrLoadedNames:
                log.error("Infinite IVR loop detected.")
                ivrName = None
                break
            else:
                self.ivrLoadedNames.append(ivrName)
                ivrData = dbapi.getIvrDefinition(scriptName)
                ivrMeta = ivrData['meta']
                ivrName = ivrMeta['prereq']
                ivrDef = ivrData['definition']
                ivrFilo.append(ivr.Ivr(ivrDef))
        log.debug('Loaded %i ivr trees' % len(ivrFilo))
        ivrResult, ivrArgs = self.runIvrTrees()
        
        
            
    def runIvrTrees(self, result=False, ivrArgs={}):
        if len(self.ivrFilo):
            ivrTree = ivrFilo.pop()
            d = ivrTree.start(self, self.callerId, result, ivrArgs)
            return d.addCallbacks(self.runIvrTrees,self.onError)
        else:
            return result, ivrArgs
        
        