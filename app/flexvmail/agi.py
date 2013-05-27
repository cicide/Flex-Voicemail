#!/usr/local/bin/python

from twisted.application import internet
from twisted.internet import reactor, defer
from starpy import fastagi
import utils, call

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
        
    def start(self):
        args = agi.variables.keys()
        script = agi.variables['agi_network_script']
        log.debug('agi variables: %s' % agi.variables)
        log.debug("in route with agi %s" % agi)        
        
    #def processScript(result):
        #if result:
            #cidname = result[0]
            #cidnum = result[1]
        #else:
            #cidname = 'Unknown'
            #cidnum = None
        #log.debug("cidname: %s, cidnum: %s" % (cidname, cidnum))
        
    #def start(scriptName):
        #cid = getCidInfo()
        #callObj = call.Call(agi, scriptName, cid, channelData)
        #callObj.start()
        
#routing for called agi scripts
def route(agi):
    def getCidInfo():
        d = agi.getVariable('CALLERID(name)')
        return d.addCallback(GotCidName).addErrback(onFailure)

    def GotCidName(result):
        if not result:
            cidname = 'Unknown'
        else:
            cidname = result
        d = agi.getVariable('CALLERID(num)')
        return d.addCallback(GotCidNum, cidname).addErrback(onFailure)

    def GotCidNum(result, cidname):
        if not result:
            cidnum = 'Unknown'
        else:
            cidnum = result
        return (cidname, cidnum)
    
    agiObj = astCall(agi)
    cidinfo = getCidInfo()
    cidinfo.addCallbacks(agiObj.start,onError)

#setup agi service when application is started
def getService():
    f = fastagi.FastAGIFactory(route)
    agiport = utils.config.getint("general", "agiport")
    service = internet.TCPServer(agiport, f)
    service.setName("AGIService")
    return service