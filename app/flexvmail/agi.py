#!/usr/local/bin/python

from twisted.application import internet
from twisted.internet import reactor, task, error as tierror
from starpy import fastagi
from starpy import error as starpyError
import utils, call, ami
from twisted.internet.defer import setDebugging
from twisted.internet.threads import deferToThread 
import time
import os

setDebugging(True)
testMode = False

log = utils.get_logger("AGIService")

interKeyDelay = 2

# get sounds directories
system_sounds_dir = utils.config.get("sounds", "system_dir")
group_sounds_dir = utils.config.get("sounds", "group_dir")
vm_files_dir = utils.config.get("sounds", "vm_dir")

system_sounds_exist_cache = {}  # cache file for system sounds to prevent continuously checking - {'file_loc': timestamp}
system_sounds_exist_cache_time = 3600 # cache system sound file checks for 1 hour


class astCall:

    def __init__(self, agi, testMode=False):
        """

        @param agi:
        @param testMode:
        """
        self.agi = agi
        self.ami = ami
        self.intType = 'asterisk'
        self.mediaType = 'wav'
        if testMode:
            result = self.runTest()
        
    def runTest(self):
        """


        """
        test = [3,14,22,41,74,89,90,107,666,12872,123675,2636849,871934999,21734653461]
        log.debug('Testing sayNumber')
        for x in test:
            log.debug('Testing Say %s' % x)
            testSay = self.sayNumber(x)
            log.debug(testSay)
        
    def onError(self, reason):
        """

        @param reason:
        @return:
        """
        #error = reason.trap(tierror.ConnectionDone)
        #if error:
        #    log.debug('trapped an error: %s' % error)
        #    return False
        #else:
        log.debug('entering agi:astCall:onError')
        log.error(reason)
        log.debug('terminating call due to error.')
        sequence = fastagi.InSequence()
        log.debug('------------- Finishing agi call --------------')
        sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence()

    def start(self):
        """


        @return:
        """
        args = self.agi.variables.keys()
        self.script = self.agi.variables['agi_network_script']
        log.debug('agi variables: %s' % self.agi.variables)
        log.debug("in route with agi %s" % self.agi)
        self.cidName = self.agi.variables['agi_calleridname']
        self.cidNum = self.agi.variables['agi_callerid']
        self.callerid = '"%s" <%s>' % (self.cidName, self.cidNum)
        #this is a major hack
        self.user = self.cidNum
        #fix this - should come from the agi call
        self.uid = self.agi.variables['agi_uniqueid']
        self.channel = self.agi.variables['agi_channel']
        self.rdnis = self.agi.variables['agi_rdnis']
        self.context = self.agi.variables['agi_context']
        self.language = self.agi.variables['agi_language']
        self.accountcode = self.agi.variables['agi_accountcode']
        self.dnid = self.agi.variables['agi_dnid']
        self.extension = self.agi.variables['agi_extension']
        self.threadid = self.agi.variables['agi_threadid']
        self.priority = self.agi.variables['agi_priority']
        self.origtime = str(time.time())
        self.msg_id = '%s-%s' % (self.uid,self.threadid)
        self.args = {}
        if 'agi_arg_1' in self.agi.variables:
            self.args[1] = self.agi.variables['agi_arg_1']
        if 'agi_arg_2' in self.agi.variables:
            self.args[2] = self.agi.variables['agi_arg_2']
        if 'agi_arg_3' in self.agi.variables:
            self.args[3] = self.agi.variables['agi_arg_3']
        if 'agi_arg_4' in self.agi.variables:
            self.args[4] = self.agi.variables['agi_arg_4']
        if 'agi_arg_5' in self.agi.variables:
            self.args[5] = self.agi.variables['agi_arg_5']
        if 'agi_arg_6' in self.agi.variables:
            self.args[6] = self.agi.variables['agi_arg_6']
        if 'agi_arg_7' in self.agi.variables:
            self.args[7] = self.agi.variables['agi_arg_7']
        if 'agi_arg_8' in self.agi.variables:
            self.args[8] = self.agi.variables['agi_arg_8']
        log.debug('args: %s' % self.args)
        newCall = call.newCall(self, self.uid)
        if newCall:
            self.call = newCall
            if testMode:
                #add any tests here
                #log.debug('running TESTS, normal calls will fail')
                #return self.runTests()
                result = self.call.startCall(self.script, self.args)
            else:
                result = self.call.startCall(self.script, self.args)
            if result:
                return result
            else:
                return self.onError('nothing')

    def runTests(self):
        """


        @return:
        """
        sequence = fastagi.InSequence()
        dtNow = int(time.time())
        dtEarlier = dtNow-3600
        dtYesterday = dtNow-86400
        dtSeveralDays = dtNow-320000
        dtWayBack = dtNow-3200000
        dtTests = [dtNow, dtEarlier, dtYesterday, dtSeveralDays,dtWayBack]
        dtFormat = "QIMp"
        for dt in dtTests:
            log.debug('adding test for %s' % dt)
            sequence.append(self.agi.sayDateTime,dt,escapeDigits='',format='Q')
            sequence.append(self.agi.streamFile, 'digits/at')
            sequence.append(self.agi.sayDateTime,dt,escapeDigits='',format='IMp')
        log.debug('sequencing tests.')
        sequence.append(self.agi.finish)
        return sequence()  #.addCallback(self.playPromptList)
    
    def hangup(self):
        """


        @return:
        """
        d = self.agi.hangup()
        d.addCallbacks(self.onHangup,self.onError)
        return d
    
    def onHangup(self, result=None):
        """

        @param result:
        @return:
        """
        log.debug('------------- Finishing agi call --------------')
        d = self.agi.finish()
        if d:
            d.addCallbacks(self.onFinish,self.onError)
        else:
            d = False
        # drop the reference to the call object
        self.call = None
        return d

    def onFinish(self, result=None):
        """

        @param result:
        @return:
        """
        return result
        
    def getUid(self):
        """


        @return:
        """
        return self.uid
    
    def getCidNum(self):
        """


        @return:
        """
        return self.cidNum
    
    def sayNumber(self, number):
        """

        @param number:
        @return:
        """
        speakNum = int(number)
        speakList = []
        while speakNum > 0:
            if speakNum <= 20:
                # we have a recoding, just speak the number
                log.debug('Saying %s' % speakNum)
                speakList.append('digits/%s' % speakNum)
                speakNum = speakNum - speakNum
            elif speakNum > 999999999:
                # we have a BILLION of something
                # I wonder how many billion we have?
                numBillions = speakNum/1000000000
                numBillList = self.sayNumber(numBillions)
                speakList = speakList + numBillList
                log.debug('Saying billion')
                speakList.append('digits/billion')
                speakNum = speakNum - (numBillions * 1000000000)
            elif speakNum > 999999:
                # we have a MILLION of something
                # Lets find out how many millions we have
                numMillions = speakNum/1000000
                numMillList = self.sayNumber(numMillions)
                speakList = speakList + numMillList
                log.debug('Saying million')
                speakList.append('digits/million')
                speakNum = speakNum - (numMillions * 1000000)
            elif speakNum > 999:
                # we have a THOUSAND of something
                # how many thousands are there?
                numThousands = speakNum/1000
                numThouList = self.sayNumber(numThousands)
                speakList = speakList + numThouList
                log.debug('Saying thousand')
                speakList.append('digits/thousand')
                speakNum = speakNum - (numThousands * 1000)
            elif speakNum > 99:
                # we've got ourselves some hundreds of something
                # how many hundreds?
                numHundreds = speakNum/100
                numHundList = self.sayNumber(numHundreds)
                speakList = speakList + numHundList
                log.debug('Saying hundred')
                speakList.append('digits/hundred')
                speakNum = speakNum - (numHundreds * 100)
            elif speakNum > 89:
                log.debug('Saying ninety')
                speakList.append('digits/90')
                speakNum = speakNum - 90
            elif speakNum > 79:
                log.debug('Saying eighty')
                speakList.append('digits/80')
                speakNum = speakNum - 80
            elif speakNum > 69:
                log.debug('Saying seventy')
                speakList.append('digits/70')
                speakNum = speakNum - 70
            elif speakNum > 59:
                log.debug('Saying sixty')
                speakList.append('digits/60')
                speakNum = speakNum - 60
            elif speakNum > 49:
                log.debug('Saying fifty')
                speakList.append('digits/50')
                speakNum = speakNum - 50
            elif speakNum > 39:
                log.debug('Saying fourty')
                speakList.append('digits/40')
                speakNum = speakNum - 40
            elif speakNum > 29:
                log.debug('Saying thirty')
                speakList.append('digits/30')
                speakNum = speakNum - 30
            elif speakNum > 20:
                log.debug('Saying twenty')
                speakList.append('digits/20')
                speakNum = speakNum - 20
            else:
                log.debug('we should never ever ever arrive here')
        return speakList
    
    def playPromptList(self, result=None, promptList=[], interrupKeys=[]):
        """

        @param result:
        @param promptList:
        @param interrupKeys:
        @return:
        """
        log.debug(interrupKeys)
        log.debug('agi:playPromptList called')
        #def onError(reason, promptList, interruptKeys):
        #    log.debug('entering: agi:playPromptList:onError')
        #    log.error(reason)
        #    if not result:
        #        result = False
        #    return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
        # Check for valid dtmf during prompt sequences
        log.debug('Checking for DTMF responses')
        firstIntKeys =[]
        if interrupKeys:
            for ikey in interrupKeys:
                firstIntKeys.append(ikey[0])
        intKeys = str("".join(firstIntKeys))
        log.debug('escape Digits: %s ' % intKeys)
        if self.call.isPaused():
            interkeydelay = 2
        else:
            interkeydelay = False
        res, val = self.call.getDtmfResults(interKeyDelay=interkeydelay)
        if not res:
            if val:
                 #we need to wait a little longer for the dtmf to finish
                log.debug("waiting %s for the the dtmf wait period" % self.call.pauseLen)
                d = task.deferLater(reactor, self.call.pauseLen, self.call.pauser, result)
                d.addCallback(self.playPromptList, promptList, interrupKeys).addErrback(self.onError)
                return d
            else:
                # we got no dtmf, continue on
                pass
        else:
            return {'type': 'response', 'value': val}
        if self.call.isPaused():
            log.debug("pausing for %s in astCall.playPromptList" % self.call.pauseLen)
            d = task.deferLater(reactor, self.call.pauseLen, self.call.pauser, result)
            d.addCallback(self.playPromptList, promptList, interrupKeys).addErrback(self.onError)
            return d
        if not len(promptList):
            log.debug('prompt list is empty, returning')
            return result
        currPrompt = promptList.pop(0)
        promptKeys = currPrompt.keys()
        # prompt object must have uri
        # may have delaybefore and delayafter
        if not 'delaybefore' in currPrompt:
            delaybefore = 0
        else:
            promptKeys.remove('delaybefore')
            delaybefore = currPrompt['delaybefore']
        if not 'delayafter' in currPrompt:
            delayafter = 0
        else:
            promptKeys.remove('delayafter')
            delayafter = currPrompt['delayafter']
        if 'tts' in currPrompt:
            log.debug('found a tts prompt')
            ttsString = currPrompt['tts']
            log.debug(ttsString)
            # TODO - handle this in the web service level - always contain tts values with a list, even for just one.
            if type(ttsString) != list:
                ttsString = [ttsString]
            if len(ttsString) < 1:
                log.warning('got zero length tts prompt')
                return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
            else:
                ttsLocSeq = []
                for ttsValue in ttsString:
                    if str(ttsValue) in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                        log.debug('found a digit: %s' % ttsValue)
                        ttsLoc = '/var/lib/asterisk/sounds/en/digits/%s' % str(ttsValue)
                    elif ttsValue in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'l', 'm', 'n', 'o', 'p', 'q',
                                      'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '#', "*"]:
                        log.debug('found a letter: %s' % ttsValue)
                        ttsLoc = '/var/lib/asterisk/sounds/en/letters/%s' % str(ttsValue)
                    elif str(int(ttsValue)) == ttsValue:
                        log.debug('Found a number: %s' % ttsValue)
                        # sayNumber returns a list, so just fill it directly with the response.
                        ttsLoc = None
                        ttsLocSeq = self.sayNumber(ttsValue)
                    else:
                        ttsLoc = None
                        log.error('Unknown tts string %s' % ttsValue)
                    if ttsLoc:
                        ttsLocSeq.append(ttsLoc)
                if len(ttsLocSeq):
                    sequence = fastagi.InSequence()
                    if delaybefore:
                        delay = float(delaybefore)/1000
                        log.debug('adding delay before of %s' % delay)
                        sequence.append(self.agi.wait,delay)
                    while len(ttsLocSeq):
                        promptLoc = ttsLocSeq.pop(0)
                        sequence.append(self.agi.streamFile, str(promptLoc), escapeDigits=intKeys, offset=0)
                        if delayafter:
                            delay = float(delayafter)/1000
                            log.debug('adding delay after of %s' % delay)
                            sequence.append(self.agi.wait,delay)
                    log.debug('playing tts prompt.')
                    return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
        elif 'datetime' in currPrompt:
            """ read back date/time """
            log.debug('found a datetime prompt')
            dateTimeString = currPrompt['datetime']
            log.debug(dateTimeString)
            if len(dateTimeString) < 1:
                log.warning('got zero length datetime prompt')
                return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
            else:
                sequence = fastagi.InSequence()
                if delaybefore:
                    delay = float(delaybefore)/1000
                    log.debug('adding delay before of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                dtVal = int(dateTimeString)
                sequence.append(self.agi.sayDateTime, dtVal, escapeDigits=intKeys, format='Q')
                sequence.append(self.agi.streamFile, 'digits/at', escapeDigits=intKeys)
                sequence.append(self.agi.sayDateTime, dtVal, escapeDigits=intKeys, format='IMp')
                if delayafter:
                    delay = float(delayafter)/1000
                    log.debug('adding delay after of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                log.debug('playing date time prompt.')
                return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
        elif 'uri' in currPrompt:
            log.debug('found uri in prompt list')
            promptKeys.remove('uri')
            promptUri = currPrompt['uri']
            if not promptUri:
                return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
            promptType, promptLoc = promptUri.split(':')
            # format the file location for asterisk by removing the extra / at the beginning 
            # and any file type from the end
            if promptLoc[:2] == '//':
                promptLoc = promptLoc[1:].split('.')[0]
            log.debug(promptLoc)
            if promptType == 'file':
                log.debug('found a file')
                sequence = fastagi.InSequence()
                if delaybefore:
                    delay = float(delaybefore)/1000
                    log.debug('adding delay before of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                log.debug(promptLoc)
                log.debug(intKeys)
                sequence.append(self.agi.streamFile, str(promptLoc), escapeDigits=intKeys, offset=0)
                if delayafter:
                    delay = float(delayafter)/1000
                    log.debug('adding delay after of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                log.debug('playing prompt.')
                return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
            else:
                log.warning('No prompt uri provided in prompt.')
                return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)            
        elif 'sayNum' in currPrompt:
            log.debug('found a number to speak')
            promptKeys.remove('sayNum')
            promptNum = currPrompt['sayNum']
            numPromptList = self.sayNumber(promptNum)
            sequence = fastagi.InSequence()
            if delaybefore:
                delay = float(delaybefore)/1000
                log.debug('adding delay before of %s' % delay)
                sequence.append(self.agi.wait, delay)
            while numPromptList:
                prompt = numPromptList.pop(0)
                log.debug(prompt)
                sequence.append(self.agi.streamFile, str(prompt), escapeDigits=intKeys, offset=0)
            if delayafter:
                delay = float(delayafter)/1000
                log.debug('adding delay after of %s' % delay)
                sequence.append(self.agi.wait, delay)
            log.debug('playing number')
            return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
        else:
            log.error('Unknown prompt type')
            return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)

    def actionRecord(self, result=None, prompt=None, folder=None, dtmf=None, retries=None, maxlen=None, beep=True):
        """

        @param prompt:
        @param folder:
        @param dtmf:
        @param retries:
        @param beep:
        @return:
        """
        if self.call.isPaused():
            log.debug("pausing for %s in astCall.actionRecord" % self.call.pauseLen)
            d = task.deferLater(reactor, self.call.pauseLen, self.call.pauser, result)
            d.addCallback(self.actionRecord, prompt, folder, dtmf, retries, maxlen, beep).addErrback(self.onError)
            return d
        log.debug('agi:actionRecord called')
        log.debug(prompt)

        firstIntKeys =[]
        if dtmf:
            for ikey in dtmf:
                firstIntKeys.append(ikey[0])
        intKeys = str("".join(firstIntKeys))
        log.debug('escape Digits: %s ' % intKeys)

        def onError(reason):
            log.debug('got error in agi:actionRecord')
            t = self.onError(reason)
            return False

        def onRecordSuccess(result, file_loc, folder, dtmf, retries, beep):
            log.debug('entering: agi:actionRecord:onRecordSuccess')
            log.debug(result)
            self.ami.purgeDtmfBuffer(self.uid)
            if len(result) == 3:
                duration = (int(result[2])/10000)+1
                keyval = result[0]
                reason = result[1]
            else:
                keyval = False
                reason = 'timeout'
                duration = 0
            log.debug(keyval)
            log.debug(reason)
            response = {}
            response['result'] = result
            response['vmfile'] = """file:/%s.%s""" % (file_loc, self.mediaType)
            response['vmfolder'] = folder
            response['type'] = 'record'
            response['duration'] = duration
            response['keyval'] = keyval
            response['reason'] = reason
            vmFile = '%s.txt' % file_loc
            log.debug('calling message write for %s' % vmFile)
            #write out the msgxxxx.txt file here
            d = genMsgFile(vmFile, 
                       self.user, 
                       self.context, 
                       '', 
                       self.extension, 
                       self.rdnis, 
                       self.priority, 
                       self.channel, 
                       self.callerid, 
                       'date time hack for now', 
                       self.origtime, 
                       '', 
                       self.msg_id, 
                       '', 
                       str(duration))
            return response

        def onPromptSuccess(result, folder, dtmf, retries, beep):
            
            def onSuccess(msgFile, folder):
                log.debug('entered in success callback of deferToThread...')
                tmp_file_loc = '%s/%s' % (str(folder),str(msgFile))
                log.debug('recording to location %s' % tmp_file_loc)
                log.debug(self.mediaType)
                log.debug(tmp_file_loc)
                interruptKeys = []
                # TODO - only allow the first digit of each key value in the interrupt list
                for intkey in dtmf:
                    interruptKeys.append(str(intkey))
                result = self.agi.recordFile(tmp_file_loc, self.mediaType, firstIntKeys, 300, beep=beep)
                result.addCallback(onRecordSuccess, tmp_file_loc, folder, dtmf, retries, beep).addErrback(onError)
                log.debug(result)
                return result            
             
            log.debug('entered agi:actionRecord:onPromptSuccess')
            log.debug(result)
            #fix this - figure out the correct file number
            #figure out the actual location for the record folder
            tmpFolder = folder.split(':/')[1]
            log.debug('Entering in deferToThread with method "getMsgNum"')
            beep = True
            log.debug(tmpFolder)
            result = deferToThread(getMsgNum,tmpFolder)
            result.addCallback(onSuccess,tmpFolder).addErrback(onError)
            return result
        
        if len(prompt):
            log.debug('calling play prompt')
            log.debug('allowed dtmf:')
            log.debug(dtmf)
            result = self.playPromptList(result=None, promptList=prompt, interrupKeys=dtmf)
            result.addCallback(onPromptSuccess, folder, dtmf, retries, beep).addErrback(onError)
            log.debug('returned from play prompt')
            log.debug(result)
            return result
        return True

    def actionPlay(self, result=None, prompt = None, dtmf = None, retries = None, maxlen = None):
        """

        @param prompt:
        @param dtmf:
        @param retries:
        @return:
        """
        if self.call.isPaused():
            log.debug("pausing for %s in astCall.actionPlay" % self.call.pauseLen)
            d = task.deferLater(reactor, self.call.pauseLen, self.call.pauser, result)
            d.addCallback(self.actionPlay, prompt, dtmf, retries, maxlen).addErrback(self.onError)
            return d

        def onKeyBuffCheck(result=None, interKeyDelay=1):
            """

            @param interKeyDelay:
            @return:
            """
            x = self.call.getDtmfResults(interKeyDelay=2)
            log.debug(x)
            res, val = x
            if res:
                # We got a valid dtmf response, handle it
                return {'type': 'response', 'value': val}
            elif val:
                # if res is false, but val has something other that None, we have to wait for the delay
                #  which is stored in val
                d = task.deferLater(reactor, val, onKeyBuffCheck, interKeyDelay)
                d.addCallback(onKeyBuffCheck, interKeyDelay).addErrback(self.onError)
                return d
            else:
                # we have a failed dtmf entry
                 return {'type': 'response', 'value': False}

        def onPlayed(result, prompt, dtmf, retries, maxlen):
            """

            @param result:
            @param prompt:
            @param dtmf:
            @param retries:
            @param maxlen:
            @return:
            """
            log.debug('got play prompt result')
            log.debug(result)
            log.debug(dtmf)
            if 'type' in result:
                return result
            else:
                return onKeyBuffCheck(result=None, interKeyDelay=2)


        def onError(reason):
            log.debug('entering: actionPlay:onError')
            log.debug(reason.value)
            if reason.value[0] == 511:
                log.debug('caller hung up the call - finish agi')
                self.agi.finish()
                self.hangup()
            else:
                log.debug('Unknown error type: %s' % reason.value)
                log.debug(reason)
            return {'type': 'response', 'value': False}
        
        log.debug('agi:actionPlay called')
        self.call.registerForDtmf(dtmf, maxlen)
        log.debug("completed dtmf registration")
        if len(prompt):
            log.debug('calling play prompt')
            d = self.playPromptList(result=None, promptList=prompt[:], interrupKeys=dtmf)
            d.addCallback(onPlayed, prompt[:], dtmf, retries, maxlen).addErrback(onError)
            return d
        else:
            return {'type': 'response', 'value': False}

    def cancelDtmfRegistration(self):
        self.ami.cancelDtmfRegistration(self.uid)

    def startDtmfRegistration(self, keylist, maxkeylen, handleKeys, pauser, purgeonfail=True, purgeonsuccess=True):
        log.debug('requesting dtmf registration.')
        self.ami.startDtmfRegistration(self.uid, keylist, maxkeylen, handleKeys, pauser,
                                        purgeonfail=purgeonfail,
                                        purgeonsuccess=purgeonsuccess)
        log.debug('dtmf registration request completed')

    def requestDtmf(self, interKeyDelay):
        return self.ami.requestDtmfResult(self.uid, interKeyDelay)

    def actionHangup(self):
        """


        @return:
        """
        log.debug('agi:actionHangup called')
        return self.hangup()
    
#routing for called agi scripts
def onFailure(reason):
    log.debug('entering: agi:onFailure')
    log.error(reason)
    return False

def route(agi):
    log.debug('New AGI call!')
    agiObj = astCall(agi)
    return agiObj.start()


def getMsgNum(directory):
    """ get the next message number. """
    log.debug('entering get message number for: %s' % directory)
    msgCount = []
    for dname,dnames,fnames in os.walk(directory):
        for filename in fnames:
            log.debug(filename)
            fname,ftype = filename.split('.')
            if ftype == 'txt':
                if fname[:3] == 'msg' and len(fname) == 7:
                    msgCount.append(int(fname[3:]))
                    log.debug(msgCount)
    if not len(msgCount):
        newMsgNum = 0
    else:
        newMsgNum = max(msgCount) + 1
    result = 'msg%s' % str(newMsgNum).zfill(4)
    log.debug(result)
    return result

def genMsgFile(filepath,
               acct, 
               context, 
               macrocontext, 
               exten, 
               rdnis, 
               priority,
               callerchan,
               callerid,
               origdate,
               origtime,
               category,
               msg_id,
               flag,
               duration):
    
    def _getMsgNum(directory):
        """ get the next message number. """
        msgCount = []
        for dname,dnames,fnames in os.walk(directory):
            for filename in fnames:
                fname,ftype = filename.split('.')
                if ftype == 'txt':
                    if fname[:3] == 'msg' and len(fname) == 7:
                        msgCount.append(int(fname[3:]))
        if not len(msgCount):
            newMsgNum = 0
        else:
            newMsgNum = max(msgCount) + 1
        return 'msg%s.txt' % str(newMsgNum).zfill(4)

    def _writeMsgFile(filepath,
                     acct, 
                     context, 
                     macrocontext, 
                     exten, 
                     rdnis, 
                     priority,
                     callerchan,
                     callerid,
                     origdate,
                     origtime,
                     category,
                     msg_id,
                     flag,
                     duration):
        log.debug('entering: _writeMsgFile')
        fileLines = []
        fileLines.append(';\n')
        fileLines.append('; Message Information file\n')
        fileLines.append(';\n')
        fileLines.append('[message]\n')
        fileLines.append('origmailbox=%s\n' % acct)
        fileLines.append('context=%s\n' % context)
        fileLines.append('macrocontext=%s\n' % macrocontext)
        fileLines.append('exten=%s\n' % exten)
        fileLines.append('rdnis=%s\n' % rdnis)
        fileLines.append('priority=%s\n' % priority)
        fileLines.append('callerchan=%s\n' % callerchan)
        fileLines.append('callerid=%s\n' % callerid)
        fileLines.append('origdate=%s\n' % origdate)
        fileLines.append('origtime=%s\n' % origtime)
        fileLines.append('category=%s\n' % category)
        fileLines.append('msg_id=%s\n' % msg_id)
        fileLines.append('flag=%s\n' % flag)
        fileLines.append('duration=%s\n' % duration)
        log.debug('writing out %s' % filepath)
        newFile = open(filepath, 'w')
        for row in fileLines:
            newFile.write(row)
        newFile.close()
        log.debug('leaving _writeMsgFile')
        return filepath
    
    log.debug('entering generate message file')
    # figure out the next sequential message file
    #directory = '/var/spool/asterisk/voicemail/default/%s/INBOX' % acct
    #directory = filepath
    #msgFileName = _getMsgNum(directory)
    #log.debug('new message file: %s' % msgFileName)
    #filepath = '%s/%s' % (directory,msgFileName)
    log.debug('creating message file: %s' % filepath)
    e = _writeMsgFile(filepath, acct, context, macrocontext, exten, rdnis, 
                    priority, callerchan, callerid, 
                    origdate, origtime, category, msg_id, 
                    flag, duration)
    return e

def runTests():
    if testMode:
        a = astCall(None, True)
        a.runTest()
        
#setup agi service when application is started
def getService():
    f = fastagi.FastAGIFactory(route)
    agiport = utils.config.getint("general", "agiport")
    service = internet.TCPServer(agiport, f)
    service.setName("AGIService")
    return service