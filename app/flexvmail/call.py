#!/usr/local/bin/python
"""
Call state module.

implements call methods and keeps state for call

"""

import time
import utils
import wsapi
from datetime import datetime
import os, sys, smtplib, mimetypes, stat

log = utils.get_logger("Call")

#get the smtp server for sending out emails
smtp_server = utils.config.get("general", "smtp_server")

retriesDefault = 3
calls = {}
callMap = {}

class Call:

    def __init__(self, agi, callerId, channelInfo, user=None):
        self.agi = agi
        self.callerId = callerId
        self.channelInfo = channelInfo
        self.wsApiHost = wsapi.getHost()
        self.tree = None
        self.user = None
        if user:
            self.user = user
        else:
            unum,uname = self.parseCallerId(callerId)
        if unum:
            self.user = unum
    
    def parseCallerId(self, callerId):
        #TODO - handle parsing of callerid
        return None
        
    def onError(self, reason):
        log.debug(reason)
        return False
    
    def onActionResponse(self, result):
        log.debug(result)
        #results contain a number of key value pairs 
        if not 'action' in result:
            log.error('missing action paramter in wsapi response')
            action = {'agi': 'hangup'}
        else:
            action = result['action']
            #TODO - figure out what the actual action is
        if not 'response' in result:
            response = ()
        else:
            response = result['response']
            #response should be a list of valid key responses (0,1,2,3,4,5,6,7,8,9,0,#,*)
        if not 'nextaction' in result:
            log.error('missing nextaction parameter in wsapi response')
            action = {'agi': 'hangup'}
            nextaction = {'agi': 'hangup'}
        else:
            nextaction = result['nextaction']
        if not 'invalidaction' in result:
            log.warning('missing invalid action in wsapi, setting invalid action as hangup')
            invalidaction = {'agi', 'hangup'}
        else:
            invalidaction = result['invalidaction']
        if not 'retries' in result:
            retries = retriesDefault
        else:
            try:
                retries = int(result['retries'])
            except:
                retries = retriesDefault
        return self.executeAction(action, response, nextaction, invalidaction, retries)
    
    def executeAction(self, action, response, nextAction, invalidAction, retries):
        pass
        
    def start(self, tree, user=None):
        if not tree:
            log.error("no valid tree supplied")
            return False
        method = 'startCall'
        actionRequest = self.wsApiHost.wsapiCall(method, self.cuid, user=self.user, tree=tree)
        actionRequest.addCallbacks(onActionResponse,onError)
        return actionRequest
        
        
        
        