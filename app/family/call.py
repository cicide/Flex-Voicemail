#!/usr/local/bin/python
"""
Call state module.

implements call methods and keeps state for extensions
"""

from twisted.internet.task import LoopingCall
from twisted.application import internet, service
from twisted.internet import reactor, defer
import time
import utils, group, ami
import agi as agi_mod
from datetime import datetime
from txdbinterface import texecute, aexecute, execute
import txdbinterface as txdb

log = utils.get_logger("Call")
group_sounds_dir = utils.config.get("sounds", "group_dir")
calls = {}
master_call = {} #dictionary of lists of channels belonging to a master call

class Channel:
    
    """
    Channel tracking class for tracking of active channels - not yet implemented
    """
    
    def __init__(self, channel, uid, hostid, ami_obj):
        self.ami = ami_obj
        self.uid = uid
        self.hostid = hostid
        self.channel = channel
        self.gid = None
        self.call = None
        
    def setGid(self, gid):
        self.gid = gid
        
    def setCall(self, call):
        self.call = call
        
    
class Call:

    def __init__(self, dialed, cidnum, cidname, hostid, uid, call_type, gid, gext, huddle):
        self.cdr = {}
        self.threeWayList = []
        self.create_time = self.cdr['create_time'] = int(time.time())
        self.dialed = self.cdr['dialed'] = dialed
        self.cidnum = self.cdr['from_cidnum'] = cidnum
        self.cidname = self.cdr['from_cidname'] = cidname
        self.hostid = self.cdr['host'] = hostid
        self.uid = self.cdr['unique_id'] = uid
        self.call_type = self.cdr['call_type'] = call_type
        self.gid = self.cdr['gid'] = gid
        self.gext = self.cdr['gext'] = gext
        self.oext = self.dext = None
        self.cuid = self.cdr['cuid'] = '%s-%s' % (hostid, uid)
        self.conf_escape_state = 0 # this is set to one, when the call is in conference escape mode
        self.bridged_cuid = None
        self.bridged_channel = None
        self.auth = 0
        self.auth_ext = 0
        self.inConf = 0
        self.findMe = []
        self.cdr['connect_start_time'] = 0
        self.cdr['connect_end_time'] = 0
        self.call_status = self.cdr['status'] = 'registered'
        self.events = [] # events are stored as (timestamp, event) tuples
        self.dtmf_events = [] # dtmf events are stored as (timestamp, dtmf event) tuples
        self.ami = None
        self.redirect = None
        self.name_file_loc = None
        self.announce_worker = None
        self.worker_chan = None
        self.worker_agi = None
        self.has_confirmed = None
        self.huddle_invite = huddle
        self.children = []
        if self.huddle_invite:
            log.debug("HUDDLE CALL CREATE for %s" % self.cuid)
            self.confirm_override = '99_invite'
        else:
            self.confirm_override = '98_confirm'
        log.debug("Instancing call %s for group %s" % (self.cuid, self.gid))
        if self.gid not in group.groups:
            #group isn't instanced yet, so we are safe to assume we are only call for the group right now
            #group will be instanced shortly, postpone setting of ami objects
            reactor.callLater(1, self.mapAMI, ami.getAMI(self.cuid)['ami'])
        elif group.groups[self.gid].getAmiObj:
            ami_obj = ami.getAMI(self.cuid)['ami']
            #group exists and has a mapped ami object
            count = group.groups[self.gid].getActiveCallCount()
            log.debug("during instance of call %s, found group with %s active calls" % (self.cuid, count))
            if count:
                if ami_obj == group.groups[self.gid].getAmiObj():
                    #we are on the correct server, no action necessary
                    self.redirct = None
                    self.mapAMI(ami_obj)
                else:
                    #We are on the wrong server, redirect the caller to the correct server
                    self.ami, self.redirect = None, group.groups[self.gid].getAmiObj()
            else:
                #There are no active calls for the group now, so bind the group to this server
                self.mapAMI(ami_obj)
                group.groups[self.gid].mapAMI(self.ami)
        else:
            #group exists, but has no mapped ami object, bind group to the server this call is on
            self.mapAMI(ami_obj)
            group.groups[self.gid].mapAMI(self.ami)

    def registerWorkerChan(self, chan):
        self.worker_chan = chan
        
    def registerWorkerAGI(self, agi):
        self.worker_agi = agi
        self.announce_worker.registerAGI(agi)
        
    def captureDTMF(self, digit):
        def createMemberMessageList(confMemDict):
            msg_list = []
            for member in confMemDict:
                file_loc = confMemDict[member]['name_file']
                msg_list.append({'prompt_type': 'location','prompt_val': file_loc})
            return msg_list
        if self.call_status == 'inCall':
            log.debug("Captured in-call dtmf of %s for call %s" % (digit, self.cuid))
            return digit
        elif self.call_status == 'inConference':
            log.debug("Captured in-conference dtmf of %s" % digit)
            if digit == '*':
                log.debug("caught in-conference escape key")
                self.conf_escape_state = 1
                msg_list = []
                msg_list.append({'prompt_type': 'system', 'prompt_val': 'escape_conf_prompt'})
                #msg = agi_mod.say(None, self.gid, self.gext, self.cuid, msg_list[:], 1, 0, 0, 1, 0)
                #add message data here
                log.debug("queueing escape prompt message %s" % msg_list)
                return self.announce_worker.queueMessage(self.ami, self.cuid, None, msg_list, msg_type=1, resp_len=1, tries=1, timeout=0.1)
            elif self.conf_escape_state == 0:
                return digit
            elif digit == '1':
                #read back list of attendees to caller
                self.ami.play_dtmf(self.worker_chan, '1')
                confMemberDict = group.groups[self.gid].getConfMemberList()
                msg_list = createMemberMessageList(confMemberDict)
                self.conf_escape_state = 0
                return self.announce_worker.queueMessage(self.ami, self.cuid, None, msg_list, msg_type=1, resp_len=1, tries=1, timeout=0.1)
            elif digit == '2':
                self.ami.play_dtmf(self.worker_chan, '2')
                lock, locker = group.groups[self.gid].isConfLock()
                self.conf_escape_state = 0
                if lock:
                    #conf already locked 
                    msg_list = []
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'escape_conf_already_locked'})
                    return self.announce_worker.queueMessage(self.ami, self.cuid, None, msg_list, msg_type=1, resp_len=1, tries=1, timeout=0.1)
                else:
                    #lock the conference
                    locked = group.groups[self.gid].lockConference(self.gext)
                    if locked:
                        msg_list = []
                        msg_list.append({'prompt_type': 'system', 'prompt_val': 'escape_conf_is_locked'})
                        msg_list.append({'prompt_type': 'location', 'prompt_val': self.name_file_loc})
                        msg = agi_mod.say(None, self.gid, self.gext, self.cuid, msg_list, 0, 0, 0, 0, 0)
                        return group.groups[self.gid].confAnnounceMsg(msg)
                    else:
                        #provide message that conf only has one user here
                        return digit
            elif digit == '3':
                self.ami.play_dtmf(self.worker_chan, '3')
                lock, locker = group.groups[self.gid].isConfLock()
                self.conf_escape_state = 0
                if not lock:
                    #conf already unlocked 
                    msg_list = []
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'escape_conf_already_unlocked'})
                    return self.announce_worker.queueMessage(self.ami, self.cuid, None, msg_list, msg_type=1, resp_len=1, tries=1, timeout=0.1)
                else:
                    #unlock the conference
                    group.groups[self.gid].unlockConference()
                    msg_list = []
                    msg_list.append({'prompt_type': 'system', 'prompt_val': 'escape_conf_is_unlocked'})
                    msg_list.append({'prompt_type': 'location', 'prompt_val': self.name_file_loc})
                    msg = agi_mod.say(None, self.gid, self.gext, self.cuid, msg_list, 0, 0, 0, 0, 0)
                    return group.groups[self.gid].confAnnounceMsg(msg)
            elif digit == '4':
                #read back list of attendees to conference
                self.ami.play_dtmf(self.worker_chan, '4')
                confMemberDict = group.groups[self.gid].getConfMemberList()
                msg_list = createMemberMessageList(confMemberDict)
                self.conf_escape_state = 0
                msg = agi_mod.say(None, self.gid, self.gext, self.cuid, msg_list, 0, 0, 0, 0, 0)
                return group.groups[self.gid].confAnnounceMsg(msg)
            elif digit == '0':
                #cancel escape state & return to conference
                self.ami.play_dtmf(self.worker_chan, '0')
                self.conf_escape_state = 0
                return digit
            else:
                log.debug("invalid in-conference escape command %s" % digit)
                self.ami.play_dtmf(self.worker_chan, '0')
                self.conf_escape_state = 0
                return digit
        else:
            log.debug("dtmf captured while not in a call or conference")
            return digit

    def whisper(self, leg, msg_list, msg_type):
        # leg is 0 for local leg, 1 for bridged leg
        pass
    
    def hangup(self):
        log.debug("got hangup for call %s" % self.cuid)
        end_time = self.cdr['end_time'] = int(time.time())
        self.cdr['call_duration'] = self.cdr['end_time'] - self.cdr['create_time']
        if self.ami:
            if self.bridged_cuid:
                if self.bridged_cuid in ami.chan_map:
                    log.debug("Sending hangup for bridged channel")
                    self.ami.termCuid(self.bridged_cuid)
        if self.cdr['connect_start_time']:
            if self.cdr['connect_end_time']:
                self.cdr['connect_duration'] = self.cdr['connect_end_time'] - self.cdr['connect_start_time']
            else:
                self.cdr['connect_end_time'] = end_time
                self.cdr['connect_duration'] = self.cdr['connect_end_time'] - self.cdr['connect_start_time']
        if self.inConf:
            log.debug("Departing Conference")
            self.departConference()
        if self.announce_worker:
            log.debug("stopping call announce worker")
            self.announce_worker.stop()
            self.announce_worker = None
        if self.worker_chan:
            log.debug("terminating worker channel")
            self.ami.termChan(self.worker_chan)
            self.worker_chan = None
        log.debug("clearing call from group call list")
        self.clearGroupCall()
        #log cdr here
        logCdr(self.cdr, self.events, self.dtmf_events)
        #destroy my reference so I can be cleaned up
        log.debug("destroying my reference in calls list")
        rs = calls.pop(self.cuid, 0)
        for record in self.children:
            if record in master_call:
                x = master_call.pop(record)
        rs = None

    def getPeerChan(self):
        if self.bridged_channel:
            return self.bridged_channel
        else:
            return None
        
    def getPeerCuid(self):
        if self.bridged_cuid:
            return self.bridged_cuid
        else:
            return None
        
    def logBridgeEvent(self, dest_cuid, dest_number, dest_chan):
        if self.cdr['connect_start_time'] == 0:
            self.cdr['connect_start_time'] = int(time.time())
        self.cdr['dest_number'] = dest_number
        self.bridged_cuid = dest_cuid
        self.bridged_channel = dest_chan
        log.debug("logged bridge event to channel %s for call %s" % (dest_cuid, self.cuid))

    def setDestNumber(self, number):
            if 'dest_number' not in self.cdr:
                self.cdr['dest_number'] = number
                
    def joinConference(self):
        log.debug("got confJoin for call %s" % self.cuid)
        if not self.announce_worker.isRunning():
            log.debug("Starting up announce worker for call %s" % self.cuid)
            self.announce_worker.start(self.ami)
        self.inConf = 1
        if not self.auth_ext:
            confExt = self.gext
        else:
            confExt = self.auth_ext
        if confExt == 0:
            log.debug("conf attendee is a guest")
            self.name_file_loc = '/tmp/%s' % self.cuid
        else:
            log.debug("conf attendee is someone who we know")
            self.name_file_loc = '%s/%s/name_%s' % (group_sounds_dir, self.gid, confExt)
        group.groups[self.gid].joinConference(self.cidname, self.cidnum, self.cuid, confExt, self.name_file_loc)

    def departConference(self):
        log.debug("got confDepart for call %s" % self.cuid)
        self.inConf = 0
        group.groups[self.gid].departConference(self.cuid, self.name_file_loc)

    def getCallType(self):
        return self.call_type

    def checkAuth(self, ext, pin):
        if self.gid in group.groups:
            return group.groups[self.gid].requestAuth(ext, pin)
        else:
            log.error("caller attempted to authenticate against an unknown group")
            return 0

    def getAMI(self):
        return self.ami

    def getRedirect(self):
        log.debug("Call redirect returning %s" % self.redirect)
        return self.redirect

    def setGext(self, ext):
        self.gext = self.cdr['gext'] = ext
        log.debug("gext set to %s" % ext)

    def getGext(self):
        return self.gext

    def setDext(self, ext):
        self.dext = self.cdr['dext'] = ext

    def setOext(self, ext):
        self.oext = self.cdr['oext'] = ext

    def setHuddle(self):
        self.huddle_invite = 1
        
    def isHuddleCall(self):
        log.debug("HUDDLE CALL CHECK for %s" % self.cuid)
        return self.huddle_invite
    
    def logConfirm(self):
        log.debug("HUDDLE CALL CONFIRM for %s" % self.cuid)
        group.groups[self.gid].confirm(self.gext)
        
    def hasConfirmed(self):
        log.debug("HUDDLE CALL CONFIRM CHECK for %s" % self.cuid)
        return group.groups[self.gid].checkConfirm(self.gext)
    
    def setConfirmOverride(self, message):
        self.confirm_override = message
        
    def getConfirmMsg(self):
        log.debug("HUDDLE CALL MSG CHECK for %s" % self.cuid)
        if not self.confirm_override:
            msg = '98_confirm'
        else:
            msg = self.confirm_override
        return msg
    
    def createFindMeList(self, extern_list):
        log.debug("Storing find me list: %s" % extern_list)
        self.findMe = extern_list

    def getNextFindMeLoc(self):
        if len(self.findMe) > 0:
            return self.findMe.pop()
        else:
            return []

    def isAuthenticated(self):
        return {'auth': self.auth, 'auth_ext': self.auth_ext}

    def makeAuthenticated(self, exten):
        #this called to mark the caller as authenticated for the supplied extension
        log.debug("Marking caller for call %s as authenticated for extension %s" % (self.cuid, exten))
        self.auth =1
        self.auth_ext = exten
        self.setGext(exten)
        return 1

    def validateGroup(self, gid):
        #if gid not in group.groups:
            retval = group.registerGroup(gid, self.create_time, time.time())
            #retval.addCallback(self.returnReply)
            return retval
        #else:
            #return 1

    def returnReply(self, result):
        log.debug("returning %s" % result)
        return result

    def logGroupCall(self):
        if self.gid in group.groups:
            group.groups[self.gid].logCall(self)
        else:
            log.error("Call log request for group %s made by call %s, while group not instantiated" % (self.gid, self.cuid))

    def clearGroupCall(self):
        log.debug("Requesting clearing of call %s from group %s call list" % (self, self.gid))
        if self.gid in group.groups:
            group.groups[self.gid].clearCall(self)

    def mapAMI(self, ami_obj):
        log.debug("AMI map request for call %s" % self.cuid)
        if self.ami:
            if self.ami == ami_obj:
                log.debug("Double request to register ami obj to a call")
            else:
                log.error("Request to map second ami obj to channel when different ami obj already mapped")
        else:
            log.debug("attempting to map an AMI for call %s" % self.cuid)
            map_result = group.mapAMI([self.gid, ami_obj])
            if not map_result:
                log.debug("Group mapping attempt indicated we are on the wrong asterisk server for this call")
                self.ami, self.redirect = None, ami_obj
            else:
                log.debug("Mapped AMI")
                self.ami, self.redirect = ami_obj, None
                self.logGroupCall()
                if not self.announce_worker:
                    import workers
                    self.announce_worker = workers.createAnnounceWorker(self.gid, self.gext, self.cuid, None)
                    if self.announce_worker:
                        log.debug("Announce working for call %s created" % self.cuid)
                        self.announce_worker.start(ami=ami_obj)
                    else:
                        log.debug("Failed to create announce worker for call %s" % self.cuid)
                    
    def setCurrentStatus(self, status):
        self.call_status = self.cdr['status'] = status
    def getCurrentStatus(self):
        return self.call_status
    def logEvent(self, event):
        log.debug("logged event: %s" % event)
        self.events.append((int(time.time()), event))
    def logDtmfEvent(self, dtmf):
        log.debug("logged dtmf event: %s" % dtmf)
        dtmf_event = (int(time.time()), dtmf)
        if dtmf_event not in self.dtmf_events:
            self.dtmf_events.append(dtmf_event)
        
    def redirectCall(self, context, priority, extension):
        if self.cdr['connect_start_time'] == 0:
            log.debug("setting connect start time for redirected call to %s" % int(time.time()))
            self.cdr['connect_start_time'] = int(time.time())
        log.debug("Redirecting call %s to %s,%s,%s" % (self.cuid, context,extension,priority))
        if self.ami:
            self.ami.redirectCall(self.cuid, extension, priority, context)
        else:
            return None
    def clearBridgedData(self):
        self.bridged_cuid = None
        self.bridged_channel = None
    
    def addThreeWayParty(self, party_cuid):
        if party_cuid not in self.threeWayList:
            self.threeWayList.append(party_cuid)
            
    def addChild(self, child):
        self.children.append(child)
        
def registerChild(parent, child):
    """ Registers a call that is not a parent call to the appropriate parent
    """
    if parent in calls:
        log.debug("found parent %s for child %s" % (parent, child))
        master_call[child] = parent
        calls[parent].addChild(child)
    elif parent in master_call:
        rank = 0
        ancestor = parent
        while ancestor in master_call:
            rank += 1
            ancestor = master_call[ancestor]
        master_call[child] = ancestor
        calls[ancestor].addChild(child)
        log.debug("Found rank %i ancestor %s for child %s" % (rank, ancestry, child))
    else:
        log.debug("Got a child registration request for a parent with no ancestry")
        
        
        
def logCdr(cdr, events, dtmf_events):
    def onCdrInsertId(result, events, dtmf_events):
        log.debug("logged cdr id %s" % result)
        if result:
            for event in events:
                sql = """INSERT INTO event_log (cdr_id, timestamp, event_type, event_val) VALUES (%i, %i, 'event', '%s')"""
                sql_arg = (result, event[0], event[1])
                sql_q = sql % sql_arg
                aexecute(sql_q)
            for dtmf in dtmf_events:
                sql = """INSERT INTO event_log (cdr_id, timestamp, event_type, event_val) VALUES (%i, %i, 'dtmf', '%s')"""
                sql_arg = (result, dtmf[0], dtmf[1])
                sql_q = sql % sql_arg
                aexecute(sql_q)
        else:
            log.error("no cdr id received to log events")
    log.debug("received cdr log request for: %s" % cdr)
    cdr_insert_id = txdb.addCdrRecord(cdr)
    return cdr_insert_id.addCallback(onCdrInsertId, events, dtmf_events).addErrback(onFailure)

def logEvents(events):
    log.debug("received event log: %s" % events)
def logDtmfEvents(dtmf_events):
    log.debug("received dtmf log: %s" % dtmf_events)
def mapAMI(cuid, ami_obj):
    if cuid not in calls:
        #postpone this mapping until the call object is created
        reactor.callLater(1, mapAMI, cuid, ami_obj)
    else:
        calls[cuid].mapAMI(ami_obj)

def onFailure(reason):
    log.debug("Failure: %s" % reason)
def register(dialed, cidnum, cidname, hostid, uid, call_type, gid, gext, huddle=None):
    cuid = '%s-%s' % (hostid, uid)
    if not cuid in calls:
        calls[cuid] = Call(dialed, cidnum, cidname, hostid, uid, call_type, gid, gext, huddle)
        log.debug("Call from %s to %s instanced" % (cidnum, dialed))
        group_valid = calls[cuid].validateGroup(gid)
        log.debug("Group validation returned %s" % group_valid)
        return group_valid
    else:
        #call has already been instanced - this could be a three-way call
        if len(calls[cuid].getThreeWayList()) == 1:
            #this is a partially completed three way call, allow continued processing
            return calls[cuid].validateGroup(gid)
        else:
            log.error("Previous call from %s to %s received for instancing" % (cidnum, dialed))
            return 0

