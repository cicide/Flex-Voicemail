#!/usr/local/bin/python

from twisted.application import internet
from twisted.internet import reactor, defer
from starpy import fastagi
import utils, call
from twisted.internet.defer import setDebugging
setDebugging(True)

log = utils.get_logger("AGIService")

# get sounds directories
system_sounds_dir = utils.config.get("sounds", "system_dir")
group_sounds_dir = utils.config.get("sounds", "group_dir")
vm_files_dir = utils.config.get("sounds", "vm_dir")

system_sounds_exist_cache = {}  # cache file for system sounds to prevent continuously checking - {'file_loc': timestamp}
system_sounds_exist_cache_time = 3600 # cache system sound file checks for 1 hour


class astCall:

    def __init__(self, agi):
        self.agi = agi
        self.intType = 'asterisk'
        
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
        self.uid = self.agi.variables['agi_uniqueid']
        self.channel = self.agi.variables['agi_channel']
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
    
    def playPromptList(self, result=None, promptList=[], interrupKeys=[]):
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
        if not 'uri' in currPrompt:
            log.warning('No prompt uri provided in prompt.')
            return self.playPromptList(result, promptList=promptList, interrupKeys=interrupKeys)
        else:
            promptKeys.remove('uri')
            promptUri = currPrompt['uri']
            promptType, promptLoc = promptUri.split(':')
            # Normalize the file location by removing the extra / at the beginning and any file type from the end
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
            else:
                log.error('Unknown prompt type: %s' % promptType)
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
            return result
        def onPromptSuccess(result, folder, dtmf, retries, beep):
            log.debug('entered agi:actionRecord:onPromptSuccess')
            log.debug(result)
            #fix this - figure out the correct file number
            file_loc = '%/msg0000.wav'
            result = self.agi.recordFile(file_loc, 'wav', dtmf, 300, beep=beep)
            result.addCallback(onRecordSuccess, file_loc, folder, dtmf, retries, beep).addErrback(onError)
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

#setup agi service when application is started
def getService():
    f = fastagi.FastAGIFactory(route)
    agiport = utils.config.getint("general", "agiport")
    service = internet.TCPServer(agiport, f)
    service.setName("AGIService")
    return service