#!/usr/local/bin/python
"""
Call state module.

implements call methods and keeps state for call

"""

import time
from twisted.internet import task
from twisted.internet import reactor
import utils
import wsapi
import sipsend
from datetime import datetime
import os, sys, smtplib, mimetypes, stat

log = utils.get_logger("Call")

#get the smtp server for sending out emails
smtp_server = utils.config.get("general", "smtp_server")

retriesDefault = 0
callMap = {}

class Call:

    def __init__(self, pbxCallObj):
        """

        @param pbxCallObj:
        """
        self.pbxCall = pbxCallObj
        self.wsApiHost = wsapi.getHost()
        self.tree = None
        self.user = None
        self.dtmfKeyList = []
        self.dtmfSubscriber = None
        self.maxKeyLen = 0
        self.dtmfResult = None
        self.paused = False
        self.pauseLen = 0.5
        log.debug('call object instanced for %s' % self.pbxCall.getCidNum())

    def hangup(self):
        self.pbxCall.actionHangup()
        #TODO - schedule destruction of this object

    def isPaused(self):
        if self.paused is True:
            log.debug('Caller %s is paused for dtmf collection' % self.user)
        else:
            log.debug('Caller %s is not paused' % self.user)
        return self.paused

    def pauseCall(self, value):
        log.debug('Setting call pause to %s' % value)
        self.paused = value

    def pauser(self, result):
        return result

    def registerForDtmf(self, keyList=[], maxlen=0, requestObject=None):
        """
        Register for dtmf results, passing a list of valid dtmf responses to the registration object

        @param keyList: a list of valid dtmf responses
        @param requestObject: a method to call with the result (optional)
        """
        log.debug('Entering Call.registerForDtmf')
        self.dtmfResult = None
        def _returnDtmfResult(result):
            self.handleDtmf(result)
        def _pauseCall(value):
            self.pauseCall(value)
        if not keyList:
            log.debug('missing keylist, is this a de-registration?')
            self.dmtfKeyList = []
            self.dtmfSubscriber = None
            self.pbxCall.cancelDtmfRegistration()
            #cancel registration
        else:
            log.debug('got valid keylist, starting registration')
            self.dmtfSubscriber = requestObject
            self.maxKeyLen = 0
            self.dtmfKeyList = keyList
            if not maxlen:
                for key in self.dtmfKeyList:
                    if len(key) > self.maxKeyLen:
                        self.maxKeyLen = len(key)
            else:
                self.maxKeyLen = maxlen
            log.debug(self.dtmfKeyList)
            log.debug(self.maxKeyLen)
            log.debug(self.dtmfSubscriber)
            self.pbxCall.startDtmfRegistration(self.dtmfKeyList, self.maxKeyLen, _returnDtmfResult, _pauseCall,
                                               purgeonfail=True, purgeonsuccess=True)
            log.debug('completed dtmf registration')

    def handleDtmf(self, result):
        log.debug('got a registered dtmf value: %s' % result)
        if self.dtmfSubscriber:
            self.dtmfSubscriber(result)
        else:
            log.debug('What do I do with this dtmf?')
            self.dtmfResult = result
        self.dtmfKeyList = []
        self.dtmfSubscriber = None
        self.maxKeyLen = 0

    def getDtmfResults(self, interKeyDelay=1):
        if self.dtmfResult:
            result, self.dtmfResult = self.dtmfResult, None
            log.debug('returning dtmf result %s' % result)
            return [True, result]
        elif not interKeyDelay:
            log.debug("DTMF Check called with no interKeyDelay")
            return [False, None]
        else:
            log.debug('Checking dtmf request with delay of: %s' % interKeyDelay)
            dtmfBuff = self.pbxCall.requestDtmf(interKeyDelay)
            return dtmfBuff

    def parseCallerId(self, callerId):
        #TODO - handle parsing of callerid
        """

        @param callerId:
        @return:
        """
        return None
        
    def onError(self, reason):
        """

        @param reason:
        @return:
        """
        log.debug(reason)
        return False
    
    def onActionResponse(self, result):
        """

        @param result:
        @return:
        """
        if self.paused:
            log.debug("pausing for %s in call.onActionResponse" % self.pauseLen)
            d = task.deferLater(reactor, self.pauseLen, self.pauser, result)
            d.addCallback(onActionResponse).addErrback(self.onError)
            return d
        log.debug('call object handling wsapi response')
        log.debug(result)
        if not result:
            log.error('invalid or empty wsapi result.')
            return False
        respKeys = result.keys()
        log.debug(respKeys)
        #results contain a number of key value pairs
        # verify the minimum result set is returned
        if not 'action' in result:
            log.error('missing action paramter in wsapi response')
            action = 'hangup'
        else:
            log.debug('handling action key')
            respKeys.remove('action')
            # fix broken reference to agi in action
            if result['action'].split(':')[0] == 'agi':
                action = result['action'].split(':')[1]
            else:
                action = result['action']
        if not 'nextaction' in result:
            log.error('missing nextaction parameter in wsapi response')
            action = 'hangup'
            nextaction = 'hangup'
        else:
            log.debug('handling nextaction')
            log.debug(respKeys)
            respKeys.remove('nextaction')
            # fix broken reference to agi in nextaction
            log.debug('fixing broken references')
            log.debug(result)
            if type(result['nextaction']) == list:
                naction = result['nextaction'][0]
            else:
                naction = result['nextaction']
            # TODO - Why is next action a list?  what should we do if it has more than one item?
            if naction == None:
                log.warning('Got no valid next action, assuming hangup')
                naction = 'hangup'
            if naction.split(':')[0] == 'agi':
                log.debug('splitting nextaction')
                nextaction = naction.split(':')[1]
            else:
                log.debug('no correction required')
                nextaction = naction
        log.debug('processing invalidaction')
        if not 'invalidaction' in result:
            log.warning('missing invalid action in wsapi, setting invalid action as hangup')
            invalidaction = 'hangup'
        else:
            log.debug ('handling invalidaction')
            respKeys.remove('invalidaction')
            invalidaction = result['invalidaction']
        log.debug('leaving onActionResponse')
        return self.executeAction(None, action, nextaction, invalidaction, result, respKeys)

    def executeAction(self, result, action, nextAction, invalidAction, wsapiResponse, respKeys):
        """

        @param action:
        @param nextAction:
        @param invalidAction:
        @param wsapiResponse:
        @param respKeys:
        @return:
        """
        if self.paused:
            log.debug("pausing for %s in call.executeAction" % self.pauseLen)
            d = task.deferLater(reactor, self.pauseLen, self.pauser, result)
            d.addCallback(self.executeAction, action, nextAction, invalidAction, wsapiResponse, respKeys).addErrback(self.onError)
            return d
        log.debug('got a valid action!')
        log.debug('nextaction: %s' % nextAction)
        if 'maxlength' in wsapiResponse:
            respKeys.remove('maxlength')
            maxlen = wsapiResponse['maxlength']
        else:
            maxlen = 0
            if 'dtmf' in wsapiResponse:
                dtmf =wsapiResponse['dtmf']
                for item in dtmf:
                    if len(item) > maxlen:
                        maxlen = len(item)
        if action == 'play':
            if not 'prompt' in wsapiResponse:
                log.warning('missing play prompt.  What should I do, play silence?')
                prompt = []
            else:
                respKeys.remove('prompt')
                prompt = wsapiResponse['prompt']
            if not 'dtmf' in wsapiResponse:
                log.warning('no dtmf supplied, using empty list')
                dtmf = []
            else:
                respKeys.remove('dtmf')
                dtmf = wsapiResponse['dtmf']
            if not 'retries' in wsapiResponse:
                if len(dtmf):
                    log.warning('no retries supplied using default of %s' % retriesDefault)
                    retries = retriesDefault
                else:
                    log.warning('no retries supplied, but message is not interruptable, so using 0')
                    retries = 0
            else:
                respKeys.remove('retries')
                retries = wsapiResponse['retries']
            if len(respKeys):
                log.warning('Action play: extra arguments ignored: %s' % ",".join(respKeys))
            d = self.pbxCall.actionPlay(None, prompt, dtmf, retries, maxlen)
            d.addCallback(self.onExecuteActionSuccess, nextAction) #.addErrback(self.onExecuteActionFailure, invalidAction)
            return d
        elif action == 'hangup':
            return self.pbxCall.actionHangup()
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
                return self.executeAction(None, action, nextAction, invalidAction, wsapiResponse)
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
            d = self.pbxCall.actionRecord(None, prompt, folder, dtmf, retries, maxlen)
            d.addCallback(self.onExecuteActionSuccess, nextAction).addErrback(self.onExecuteActionFailure, invalidAction)
            return d
        else:
            log.debug('Unknown action type %s' % action)

    def onExecuteActionSuccess(self, result, nextAction):
        """

        @param result:
        @param nextAction:
        @return:
        """
        if self.paused:
            log.debug("pausing for %s in call.onExecuteActionSuccess" % self.pauseLen)
            d = task.deferLater(reactor, self.pauseLen, self.pauser, result)
            d.addCallback(self.onExecuteActionSuccess, nextAction).addErrback(self.onError)
            return d
        log.debug('entered: call:onExecuteActionSuccess')
        log.debug(result)
        log.debug(nextAction)
        if 'type' in result:
            log.debug('found a valid result type of: %s' % result['type'])
            resType = result['type']
            if resType == 'record':
                log.debug('found a record result type')
                duration = str(result['duration'])
                keyVal = result['keyval']
                if keyVal:
                    returnKey = chr(keyVal)
                else:
                    returnKey = False
                reason = result['reason']
                vmFile = str(result['vmfile'])
                log.debug('vmFile set to: %s' % vmFile)
                act = str(nextAction)
                log.debug('act set to: %s' % act)
                actionRequest = self.wsApiHost.wsapiCall(act, None, None, vmfile=vmFile, key=returnKey, reason=reason, duration=duration)
                actionRequest.addCallbacks(self.onActionResponse,self.onError)
                return actionRequest
            elif resType == 'play':
                log.debug('found a play result type')
                return True
            elif resType == 'response':
                log.debug('found a response result type')
                keyVal = result['value']
                if nextAction[:4] == 'http':
                    #log.debug('executing action: ' % nextAction)
                    nact = str(nextAction)
                    #
                    actionRequest = self.wsApiHost.wsapiCall(nact, None, None, key=keyVal)
                    actionRequest.addCallbacks(self.onActionResponse,self.onError)
                    return actionRequest
                else:
                    log.debug('unknown next action')
                    return False                
            else:
                log.debug('unknown result type')
                return False
        elif result:
            log.debug('got a result with no type')
            log.debug(nextAction[:4])
            if nextAction[:4] == 'http':
                #log.debug('executing action: ' % nextAction)
                nact = str(nextAction)
                #
                actionRequest = self.wsApiHost.wsapiCall(nact, None, None, key=result)
                actionRequest.addCallbacks(self.onActionResponse,self.onError)
                return actionRequest
            else:
                log.debug('unknown next action')
                return False
        else:
            log.debug('No type found for successful action.')
            return False

    def onExecuteActionFailure(self, reason, invalidAction):
        """

        @param reason:
        @param invalidAction:
        @return:
        """
        log.error(reason)
        return False

    def startCall(self, tree):
        """

        @param tree:
        @return:
        """
        log.debug('call started')
        if not tree:
            log.error("no valid tree supplied")
            return False
        else:
            self.tree = tree
            self.cuid = self.pbxCall.getUid()
            self.user = self.callerId = self.pbxCall.getCidNum()
        method = 'startcall'
        actionRequest = self.wsApiHost.wsapiCall(None, method, self.cuid, callerid = self.callerId, user=self.user, tree=tree)
        actionRequest.addCallbacks(self.onActionResponse,self.onError)
        return actionRequest
        #return self.onActionResponse(actionRequest)


def handleMwi(request):
    log.debug(request)
    if 'user' not in request:
        return False
    if 'new' not in request:
        newmsg = '0'
    else:
        newmsg = request['new']
    if 'old' not in request:
        oldmsg = '0'
    else:
        oldmsg = request['old']
    user = request['user']
    return sipsend.sendMwi(user, newmsg, oldmsg)


def newCall(pbxCallObj, uid):
    """

    @param pbxCallObj:
    @param uid:
    @return:
    """
    if not uid in callMap:
        callMap[uid] = Call(pbxCallObj)
        return callMap[uid]
    else:
        return False
        

def runTests():
    """


    """
    pass
