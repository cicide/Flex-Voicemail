#!/usr/local/bin/python

from twisted.application import internet
from twisted.internet import reactor, defer
from starpy import fastagi
import utils, call
from twisted.internet.defer import setDebugging
from twisted.internet.threads import deferToThread 
import time
import datetime
import os

setDebugging(True)
testMode = True

log = utils.get_logger("AGIService")

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
            result = self.runTest
        
    def runTest(self):
        test = [3,14,22,41,74,89,90,107,666,12872,123675,2636849,871934999,21734653461]
        log.debug('Testing sayNumber')
        for x in test:
            log.debug('Saying %s' % x)
            testSay = self.sayNumber(x)
            log.debug(x)
        
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
            result = self.call.startCall(self.script)
            if result:
                #log.debug('Terminating call.')
                #result.addCallbacks(self.onError,self.onError)
                return result
            else:
                return self.onError('nothing')

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
                log.debug('saying %s') % speakNum
                speakList.append('digits/%s' % speakNum)
                speakNum = speakNum - speakNum
            elif speakNum > 999999999:
                # we have a BILLION of something
                # I wonder how many billion we have?
                numBillions = speakNum/1000000000
                numBillList = self.sayNumber(numBillions)
                speakList = speakList + numBillList
                speakList.append('digits/billion')
                speakNum = speakNum - (numBillions * 1000000000)
            elif speakNum > 999999:
                # we have a MILLION of something
                # Lets find out how many millions we have
                numMillions = speakNum/1000000
                numMillList = self.sayNumber(numMillions)
                speakList = speakList + numMillList
                speakList.append('digits/million')
                speakNum = speakNum - (numMillions * 1000000)
            elif speakNum > 999:
                # we have a THOUSAND of something
                # how many thousands are there?
                numThousands = speakNum/1000
                numThouList = self.sayNumber(numThousands)
                speakList = speakList + numThousList
                speakList.append('digits/thousand')
                speakNum = speakNum - (numThousands * 1000)
            elif speakNum > 99:
                # we've got ourselves some hundreds of something
                # how many hundreds?
                numHundreds = speakNum/100
                numHundList = self.sayNumber(numHundreds)
                speakList = speakList + numHundList
                speakList.append('digits/hundred')
                speakNum = speakNum - (numHundreds * 100)
            elif speakNum > 89:
                speakList.append('digits/90')
                speakNum = speakNum - 90
            elif speakNum > 79:
                speakList.append('digits/80')
                speakNum = speakNum - 80
            elif speakNum > 69:
                speakList.append('digits/70')
                speakNum = speakNum - 70
            elif speakNum > 59:
                speakList.append('digits/60')
                speakNum = speakNum - 60
            elif speakNum > 49:
                speakList.append('digits/50')
                speakNum = speakNum - 50
            elif speakNum > 39:
                speakList.append('digits/40')
                speakNum = speakNum - 40
            elif speakNum > 29:
                speakList.append('digits/30')
                speakNum = speakNum - 30
            elif speakNum > 20:
                speakList.append('digits/20')
                speakNum = speakNum - 20
            else:
                log.debug('we should never ever ever arrive here')
        return numList
    

    
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
        elif 'uri' in currPrompt:
            promptKeys.remove('uri')
            promptUri = currPrompt['uri']
            promptType, promptLoc = promptUri.split(':')
            # format the file location for asterisk by removing the extra / at the beginning 
            # and any file type from the end
            if promptLoc[:2] == '//':
                promptLoc = promptLoc[1:].split('.')[0]
            log.debug(promptLoc)
            if promptType == 'file':
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
                #return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys).addErrback(onError, promptList=promptList, interrupKeys=interrupKeys)
                # don't capture this error
                log.debug('playing prompt.')
                return sequence().addCallback(self.playPromptList, promptList=promptList, interrupKeys=interrupKeys)
            elif 'sayNum' in currPrompt:
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
            
            def onSuccess(msgFile):
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
            tmpFolder = folder.split(':/')[0]
            log.debug('Entering in deferToThread with method "getMsgNum"')
            beep = False # Because it was giving me this error : 
            '''[Jul 26 11:25:34] WARNING[8732]: file.c:663 ast_openstream_full: File beep does not exist in any format
               [Jul 26 11:25:34] WARNING[8732]: file.c:958 ast_streamfile: Unable to open beep (format 0x4 (ulaw)): No such file or directory
            '''
            result = deferToThread(getMsgNum,tmpFolder) #this needs to be done in a defer to thread
            result.addCallbacks(onSuccess)
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
        log.debug('agi:actionPlay called')
        log.debug(prompt)
        if len(prompt):
            log.debug('calling play prompt')
            result = self.playPromptList(result=None, promptList=prompt, interrupKeys=dtmf)
            log.debug('got play prompt result')
            log.debug(result)
            return result
        else:
            return False
        
    def actionHangup(self):
        log.debug('agi:actionHangup called')
        return self.hangup()
    
#routing for called agi scripts
def onFailure(reason):
    log.error(reason)
    return False

def route(agi):
    agiObj = astCall(agi)
    return agiObj.start()


def getMsgNum(directory):
    """ get the next message number. """
    log.debug('entering get message number for: %s' % directory)
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
    return 'msg%s' % str(newMsgNum).zfill(4)

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

def test():
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