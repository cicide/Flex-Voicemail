#!/usr/local/bin/python

from twisted.application import internet
from twisted.internet import reactor, defer
from starpy import fastagi
import utils, call, group, ami, workers
from txdbinterface import texecute, aexecute, execute
import txdbinterface as txdb
import os, sys, smtplib, mimetypes, stat, time, datetime

log = utils.get_logger("AGIService")

#get the smtp server for sending out emails
smtp_server = utils.config.get("general", "smtp_server")

# get sounds directories
system_sounds_dir = utils.config.get("sounds", "system_dir")
group_sounds_dir = utils.config.get("sounds", "group_dir")
vm_files_dir = utils.config.get("sounds", "vm_dir")

system_sounds_exist_cache = {}  # cache file for system sounds to prevent continuously checking - {'file_loc': timestamp}
system_sounds_exist_cache_time = 3600 # cache system sound file checks for 1 hour

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

            
    def start(scriptName):
        cid = getCidInfo()
        callObj = call.Call(agi, scriptName, cid, channelData)
        callObj.start()
        

#setup agi service when application is started
def getService():
    f = fastagi.FastAGIFactory(route)
    agiport = utils.config.getint("general", "agiport")
    service = internet.TCPServer(agiport, f)
    service.setName("AGIService")
    return service