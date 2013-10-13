#!/usr/local/bin/python

from twisted.application import internet
from twisted.internet import reactor, defer, task
from starpy import fastagi
import utils, call, ami
from twisted.internet.defer import setDebugging
from twisted.internet.threads import deferToThread 
import time
import datetime
import os

setDebugging(True)
testMode = True

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
        self.agi = agi
        self.intType = 'asterisk'
        self.mediaType = 'wav'
        if testMode:
            result = self.runTest()
        
    def runTest(self):
        test = [3,14,22,41,74,89,90,107,666,12872,123675,2636849,871934999,21734653461]
        log.debug('Testing sayNumber')
        for x in test:
            log.debug('Testing Say %s' % x)
            testSay = self.sayNumber(x)
            log.debug(testSay)
        
    def onError(self, reason):
        log.debug('entering agi:onError')
        log.error(reason)
        log.debug('terminating call due to error.')
        sequence = fastagi.InSequence()
        sequence.append(self.agi.hangup)
        sequence.append(self.agi.finish)
        return sequence()

    def start(self):
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
        if 'agi_arg1' in self.agi.variables:
            self.args[1] = self.agi.variables['agi_arg1']
        if 'agi_arg2' in self.agi.variables:
            self.args[2] = self.agi.variables['agi_arg2']
        if 'agi_arg3' in self.agi.variables:
            self.args[3] = self.agi.variables['agi_arg3']
        if 'agi_arg4' in self.agi.variables:
            self.args[4] = self.agi.variables['agi_arg4']
        if 'agi_arg5' in self.agi.variables:
            self.args[5] = self.agi.variables['agi_arg5']
        if 'agi_arg6' in self.agi.variables:
            self.args[6] = self.agi.variables['agi_arg6']
        if 'agi_arg7' in self.agi.variables:
            self.args[7] = self.agi.variables['agi_arg7']
        if 'agi_arg8' in self.agi.variables:
            self.args[8] = self.agi.variables['agi_arg8']
        newCall = call.newCall(self, self.uid)
        if newCall:
            self.call = newCall
            if testMode:
                #add any tests here
                #log.debug('running TESTS, normal calls will fail')
                #return self.runTests()
                result = self.call.startCall(self.script)
            else:
                result = self.call.startCall(self.script)
            if result:
                log.debug('stopping call........................ not really')
                #self.agi.finish()
                #log.debug('Terminating call.')
                #result.addCallbacks(self.onError,self.onError)
                return result
            else:
                return self.onError('nothing')

    def runTests(self):
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
        d = self.agi.hangup()
        d.addCallbacks(self.onHangup,self.onError)
        return d
    
    def onHangup(self, result=None):
        d = self.agi.finish()
        if d:
            d.addCallbacks(self.onFinish,self.onError)
            return d
        else:
            return False
    
    def onFinish(self, result=None):
        return result
        
    def getUid(self):
        return self.uid
    
    def getCidNum(self):
        return self.cidNum
    
    def sayNumber(self, number):
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
        log.debug(result)
        log.debug('agi:playPromptList called')
        def onError(reason, promptList, interruptKeys):
            log.debug('entering: agi:playPromptList:onError')
            log.error(reason)
            if not result:
                result = False
            return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
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
            if len(ttsString) < 1:
                log.warning('got zero length tts prompt')
                return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
            else:
                ttsLocSeq = []
                for ttsValue in ttsString:
                    if str(ttsValue) in ['0','1','2','3','4','5','6','7','8','9']:
                        log.debug('found a digit: %s' % ttsValue)
                        ttsLoc = '/var/lib/asterisk/sounds/en/digits/%s' % str(ttsValue)
                    elif ttsValue in ['a','b','c','d','e','f','g','h','i','j','l',
                                      'm','n','o','p','q','r','s','t','u','v','w',
                                      'x','y','z','#',"*"]:
                        log.debug('found a letter: %s' % ttsValue)
                        ttsLoc = '/var/lib/asterisk/sounds/en/letters/%s' % str(ttsValue)
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
                    intKeys = str("".join(interrupKeys))
                    while len(ttsLocSeq):
                        promptLoc = ttsLocSeq.pop(0)
                        sequence.append(self.agi.streamFile,str(promptLoc),escapeDigits=intKeys,offset=0)
                        if delayafter:
                            delay = float(delayafter)/1000
                            log.debug('adding delay after of %s' % delay)
                            sequence.append(self.agi.wait,delay)
                    log.debug('playing tts prompt.')
                    return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
        elif 'datetime' in currPrompt:
            """ read back date/time """
            log.debug('found a datetime prompt')
            dateTimeString = currPrompt('datetime')
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
                intKeys = str("".join(interrupKeys))
                dtVal = int(dateTimeString)
                sequence.append(self.agi.sayDateTime,dt,escapeDigits='',format='Q')
                sequence.append(self.agi.streamFile, 'digits/at')
                sequence.append(self.agi.sayDateTime,dt,escapeDigits='',format='IMp')
                if delayafter:
                    delay = float(delayafter)/1000
                    log.debug('adding delay after of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                log.debug('playing tts prompt.')
                return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
        elif 'uri' in currPrompt:
            log.debug('found uri in prompt list')
            promptKeys.remove('uri')
            promptUri = currPrompt['uri']
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
                intKeys = str("".join(interrupKeys))
                log.debug(promptLoc)
                log.debug(intKeys)
                sequence.append(self.agi.streamFile,str(promptLoc),escapeDigits=intKeys,offset=0)
                if delayafter:
                    delay = float(delayafter)/1000
                    log.debug('adding delay after of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                log.debug('playing prompt.')
                return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
            elif 'sayNum' in currPrompt:
                log.debug('found a number to speak')
                promptKeys.remove('sayNum')
                promptNum = currPrompt['sayNum']
                numPromptList = self.sayNumber(promptNum)
                sequence = fastagi.InSequence()
                if delaybefore:
                    delay = float(delaybefore)/1000
                    log.debug('adding delay before of %s' % delay)
                    sequence.append(self.agi.wait,delay)
                intKeys = str("".join(interrupKeys))                
                while numPromptList:
                    prompt = numPromptList.pop(0)
                    log.debug(prompt)
                    sequence.append(self.agi.streamFile,str(prompt),escapeDigits=intKeys,offset=0)
                if delayafter:
                    delay = float(delayafter)/1000
                    log.debug('adding delay after of %s' % delay)
                    sequence.append(self.agi.wait,delay) 
                log.debug('playing number')
                return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
            else:
                log.error('Unknown prompt type: %s' % promptType)
                return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
        else:
            log.warning('No prompt uri provided in prompt.')
            return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
    
    def actionRecord(self, prompt, folder, dtmf, retries, beep=True):
        log.debug('agi:actionRecord called')
        log.debug(prompt)
        def onError(reason):
            log.debug('got error in agi:actionRecord')
            log.error(reason)
            return self.onError(reason)
        def onRecordSuccess(result, file_loc, folder, dtmf, retries, beep):
            log.debug('entering: agi:actionRecord:onRecordSuccess')
            log.debug(result)
            if len(result) == 3:
                duration = (int(result[2])/10000)+1
            else:
                duration = 0
            response = {}
            response['result'] = result
            response['vmfile'] = """%s.%s""" % (file_loc, self.mediaType)
            response['vmfolder'] = folder
            response['type'] = 'record'
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
                result = self.agi.recordFile(tmp_file_loc, self.mediaType, dtmf, 300, beep=beep)
                result.addCallback(onRecordSuccess, tmp_file_loc, folder, dtmf, retries, beep).addErrback(onError)
                log.debug(result)
                return result            
             
            log.debug('entered agi:actionRecord:onPromptSuccess')
            log.debug(result)
            #fix this - figure out the correct file number
            #figure out the actual location for the record folder
            tmpFolder = folder.split(':/')[1]
            log.debug('Entering in deferToThread with method "getMsgNum"')
            beep = True # Because it was giving me this error : 
            log.debug(tmpFolder)
            result = deferToThread(getMsgNum,tmpFolder) #this needs to be done in a defer to thread
            result.addCallback(onSuccess,tmpFolder).addErrback(onError)
            return result
        
        if len(prompt):
            log.debug('calling play prompt')
            result = self.playPromptList(result=None, promptList=prompt, interrupKeys=dtmf)
            result.addCallback(onPromptSuccess, folder, dtmf, retries, beep).addErrback(onError)
            log.debug('returned from play prompt')
            log.debug(result)
            return result
        return True

    def actionPlay(self, prompt, dtmf, retries):
        def onKeyBuffCheck():
            log.debug('checking keyBuffer')
            keyBuff = ami.fetchDtmfBuffer(self.uid)
            log.debug(keyBuff)
            last = keyBuff['last']
            buff = keyBuff['buffer']
            if (time.time() - last) > interKeyDelay:
                return (True, buff)
            else:
                return (False, keyBuff)

        def onKeyBuffWait(result, dtmfList, maxKeyLen):
            log.debug('keyBuff check completed')
            if result[0]:
                log.debug('we have a result')
                buff = result[1]
                keyVal = ''.join(buff)
                if keyVal in dtmfList:
                    log.debug('and it is valid')
                    return {'type': 'response', 'value': keyVal}
                else:
                    log.debug('but it is not valid')
                    return {'type': 'response', 'value': False}
            else:
                log.debug('it looks like we did not wait long enough, or another key has been entered')
                keyBuff = result[1]
                last = keyBuff['last']
                buff = keyBuff['buffer']
                keyVal = ''.join(buff)
                if keyVal in dtmfList:
                    log.debug('however, we have a valid match, return it')
                    # we have an exact match, return it!
                    return {'type': 'response', 'value': keyVal}
                elif len(buff) >= maxKeyLen:
                    log.debug('we have reached the max possible response length and do not have a match')
                    # we have reached max length and don't have a match 
                    return {'type': 'response', 'value': False}
                else:
                    log.debug('we have to wait some more')
                    # we don't match, but we haven't reached max length
                    waitDelay = interKeyDelay - (time.time() - last) + 0.1
                    d = task.deferLater(reactor, waitDelay, onKeyBuffCheck)
                    d.addCallback(onKeyBuffWait, dtmfList, maxKeyLen).addErrback(self.onError)
                    return d                    

        def onPlayed(result, prompt, dtmf, retries):
            log.debug('got play prompt result')
            log.debug(result)
            log.debug(dtmf)
            dtmfList = dtmf
            asciCode = result[0][0]
            if not asciCode:
                log.debug('no key pressed')
                if retries:
                    log.debug('retrying')
                    retries -= 1
                    # TODO: We need to add some delays in here before retrying
                    d = self.playPromptList(result=None, promptList=prompt[:], interrupKeys=dtmf)
                    d.addCallback(onPlayed, prompt, dtmf, retries).addErrback(onError)
                    return d
                else:
                    return {'type': 'response', 'value': False}
            else:
                # check to see if we match any valid single keys
                keyVal = chr(asciCode)
                maxKeyLen = max(len(dtmfKeys) for dtmfKeys in dtmfList)
                log.debug('Got Result: %s' % keyVal)
                if keyVal in dtmfList:
                    log.debug('Result is Valid')
                    # we have a valid single dtmf entry, run with it
                    return {'type': 'response', 'value': keyVal}
                elif maxKeyLen > 1:
                    log.debug('result not YET valid')
                    keyBuff = ami.fetchDtmfBuffer(self.uid)
                    last = keyBuff['last']
                    buff = keyBuff['buffer']
                    keyBuffLen = len(buff)
                    if keyBuffLen >= maxKeyLen:
                        log.debug('No more keys available, returning what we have')
                        # do we already have the max number of allowed characters?
                        # TODO: Confirm validity before returning 
                        return {'type': 'response', 'value': ''.join(buff)}
                    elif (time.time() - last) > interKeyDelay:
                        log.debug('We have waited long enough, no more keys are coming')
                        # TODO: verify validity of current keys before returning
                        # have we waited long enough to return what we have?
                        return {'type': 'response', 'value': ''.join(buff)}
                    else:
                        log.debug('We need to wait a little longer to see if any more keys are entered')
                        # we need to wait to see if the user is going to enter more keys
                        waitDelay = interKeyDelay - (time.time() - last) + 0.1
                        d = task.deferLater(reactor, waitDelay, onKeyBuffCheck)
                        d.addCallback(onKeyBuffWait, dtmfList, maxKeyLen).addErrback(self.onError)
                        return d
                else:
                    # We have an invalid key combination
                    return {'type': 'response', 'value': False}

        def onError(reason):
            log.error(reason)
            return {'type': 'response', 'value': False}
        
        log.debug('agi:actionPlay called')
        log.debug(prompt)
        log.debug(dtmf)
        tmp = ami.purgeDtmfBuffer(self.uid)
        log.debug(tmp)
        if len(prompt):
            log.debug('calling play prompt')
            d = self.playPromptList(result=None, promptList=prompt[:], interrupKeys=dtmf)
            d.addCallback(onPlayed, prompt[:], dtmf, retries).addErrback(onError)
            return d
        else:
            return {'type': 'response', 'value': False}
        
    def actionHangup(self):
        log.debug('agi:actionHangup called')
        return self.hangup()
    
#routing for called agi scripts
def onFailure(reason):
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