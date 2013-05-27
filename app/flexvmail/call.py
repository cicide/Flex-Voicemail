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
callMap = {}

class Call:

    def __init__(self, pbxCallObj):
        self.pbxCall = pbxCallObj
        self.wsApiHost = wsapi.getHost()
        self.tree = None
        self.user = None
        log.debug('call object instanced for %s' % self.pbxCall.getCidNum())
    
    def parseCallerId(self, callerId):
        #TODO - handle parsing of callerid
        return None
        
    def onError(self, reason):
        log.debug(reason)
        return False
    
    def onActionResponse(self, result):
        log.debug('call object handling wsapi response')
        log.debug(result)
        respKeys = result.keys()
        log.debug(respKeys)
        #results contain a number of key value pairs
        # verify the minimum result set is returned
        if not 'action' in result:
            log.error('missing action paramter in wsapi response')
            action = 'hangup'
        else:
            respKeys.remove('action')
            action = result['action']
        if not 'nextaction' in result:
            log.error('missing nextaction parameter in wsapi response')
            action = 'hangup'
            nextaction = 'hangup'
        else:
            respKeys.remove('nextaction')
            nextaction = result['nextaction']
        if not 'invalidaction' in result:
            log.warning('missing invalid action in wsapi, setting invalid action as hangup')
            invalidaction = 'hangup'
        else:
            respKeys.remove('invalidaction')
            invalidaction = result['invalidaction']
        return self.executeAction(action, nextaction, invalidaction, result, respKeys)
            
    
    def executeAction(self, action, nextAction, invalidAction, wsapiResponse, respKeys):
        log.debug('got a valid action!')
        if action == 'play':
            return True
        elif action == 'hangup':
            return True
        elif action == 'record':
            # Record action requires:
            #    folder - where to store the recorded file
            #    nextaction - what to do after the recording is complete
            #    prompt - an ordered list of prompts to play prior to recording
            #    invalidaction - what to do if the user doesn't validly respond
            # optional arguments
            #    dtmf - list of valid dtmf responses (defaults to '#')
            #    retries - number of times to play leading prompts before executing invalid action (default to config file value)
            if not 'prompt' in wsapiResponse:
                log.warning('missing record prompts, is this a straight record?')
                prompt = []
            else:
                respKeys.remove('prompt')
                prompt = wsapiResponse['prompt']
            if not 'folder' in wsapiResponse:
                log.error('record action missing folder argument, where do I save the recording?')
                action = 'hangup'
                return self.executeAction(action, nextAction, invalidAction, wsapiResponse)
            else:
                respKeys.remove('folder')
                folder = wsapiResponse['folder']
            if not 'dtmf' in wsapiResponse:
                log.warning('no dtmf supplied, using default of #')
                dtmf = ['#']
            else:
                respKeys.remove('dtmf')
                dtmf = wsapiResponse['dtmf']
            if not 'retries' in wsapiResponse:
                log.warning('no retries supplied using default of %s' % retriesDefault)
                retries = retriesDefault
            else:
                respKeys.remove('retries')
                retries = wsapiResponse['retries']
            if len(respKeys):
                log.warning('Action record: extra arguments ignored: %s' % ",".join(respKeys))
            d = self.pbxCall.actionRecord(prompt, folder, dtmf, retries)
            d.addCallback(self.onExecuteActionSuccess, nextAction).addErrback(self.onExecuteActionFailure, invalidAction)
            return d
        
    def onExecuteActionSuccess(self, result, nextAction):
        return True
    
    def onExecuteActionFailure(self, reason, invalidAction):
        return False
    
    def startCall(self, tree):
        log.debug('call started')
        if not tree:
            log.error("no valid tree supplied")
            return False
        else:
            self.tree = tree
            self.cuid = self.pbxCall.getUid()
            self.user = self.callerId = self.pbxCall.getCidNum()
        method = 'startcall'
        actionRequest = self.wsApiHost.wsapiCall(method, self.cuid, callerId = self.callerId, user=self.user, tree=tree)
        actionRequest.addCallbacks(self.onActionResponse,self.onError)
        return actionRequest
        #return self.onActionResponse(actionRequest)
        
def newCall(pbxCallObj, uid):
    if not uid in callMap:
        callMap[uid] = Call(pbxCallObj)
        return callMap[uid]
    else:
        return False
        