#!/usr/local/bin/python

from twisted.application import internet, service
from twisted.internet import reactor, defer
from starpy.manager import AMIFactory, AMIProtocol
import os, time
import utils, call

log = utils.get_logger("AMIService")

amiuser = utils.config.get("general", "amiuser")
amipassword = utils.config.get("general", "amipassword")
amiport = utils.config.getint("general", "amiport")
amiaddr = utils.config.get("general", "amiaddr")
aminame = utils.config.get("general", "aminame")
amidomain = utils.config.get("general", "amidomain")

serverList=[]
chan_map = {} # cuid: {chan: channel, ami: ami_obj}

dtmfBuffer = {} # uid: {last: timestamp, buffer: [list of dtmf events]}


class DialerProtocol(AMIProtocol):

    def __init__(self):
        AMIProtocol.__init__(self)
    
    def onFailure(self, reason, method):
        log.debug("Got AMI failure in method %s: %s" % (method, reason))

    def connectionMade(self):
        log.debug("Connection Made")
        self.factory.protoList.append(self)
        self.factory.loginDefer.addCallback(self.onConnect) #Add a callback to be notified upon successful login
        AMIProtocol.connectionMade(self)

    def onConnect(self, ami):
        """Called when login is successful. A place to start interacting
        with the protocol
        """
        log.debug("Successfully logged into AMI at %s"%self.factory.hostname)
        self.serverChannelList = []
        self.answerMap = [] #list of unique ids to monitor for dial answer status so we can set correct cdr connect time
        self.ami = ami
        self.host_id = self.factory.hostname
        #create a list in the factory for tracking of active calls should we lose connection so we can clear the maps out
        ami.registerEvent('UserEvent', self.onUserEvent)
        ami.registerEvent('Hangup', self.onHangup)
        ami.registerEvent('Newchannel', self.onNewChannel)
        ami.registerEvent('Newstate', self.onNewState)
        ami.registerEvent('Dial', self.onDialEvent)
        ami.registerEvent('Bridge', self.onBridgeEvent)
        ami.registerEvent('DTMF', self.onDtmf)

    def onDtmf(self, ami, event):
        def onSuccess(result):
            log.debug("dtmf capture success: %s" % result)
        def onFailure(reason):
            log.debug("dtmf capture failure: %s" % reason)
        digit = event['digit']
        uid = event['uniqueid']
        dtmf_begin = event['begin']
        dtmf_end = event['end']
        log.debug('got dtmf event: %s' % event)
        if dtmf_being in ('Yes', 'yes'):
            if str(uid) in dtmfBuffer:
                dtmfBuffer[str(uid)]['last'] = time.time()
                dtmfBuffer[str(uid)].append(str(digit))
            else:
                dtmfBuffer[str(uid)] = {'last': time.time(), 'buffer': [str(digit)]}
                
    def onDialEvent(self, ami, event):
        log.debug("got dial event: %s" % event)
        uid = event['uniqueid']
        subevent = event['subevent']
        #if subevent == 'Begin':
            #dest_uid = event['destuniqueid']
            #if uid in self.answerMap:
                #cuid = '%s-%s' % (self.host_id, uid)
                #call.calls[cuid].setCurrentStatus('dialing')
                #call.calls[cuid].logEvent('dialing')
        #if subevent == 'End':
            #if uid in self.answerMap:
                #cuid = '%s-%s' % (self.host_id, uid)
                #dialstatus = event['dialstatus']
                #log.debug("got call termination notice with status: %s for uid: %s" % (dialstatus, uid))
                #call.calls[cuid].setCurrentStatus('hangup')
                #call.calls[cuid].logEvent('hangup')

    def onBridgeEvent(self, ami, event):
        uid = event['uniqueid1']
        dest_uid = event['uniqueid2']
        dest_phone = event['callerid2']
        chan1 = event['channel1']
        chan2 = event['channel2']
        cuid = '%s-%s' % (self.host_id, uid)
        dest_cuid = '%s-%s' % (self.host_id, dest_uid)
        log.debug("BRIDGE EVENT bridging %s to %s" % (cuid, dest_cuid))
        #if uid in self.answerMap:
        #if cuid in call.calls:
            #log.debug("got a bridge event for a call in the answerMap")
            #call.calls[cuid].logBridgeEvent(dest_cuid, dest_phone, chan2)
            #call.calls[cuid].logEvent('inCall')
            #call.calls[cuid].setCurrentStatus('inCall')
            #d = self.ami.getVar(chan1, 'THREE_WAY')
            #d.addCallback(self.onGotThreeWay).addErrback(self.onFailure, 'onBridgeEvent')
        #else:
            ##log.debug("didn't find uid: %s in answerMap" % uid)
            #call.registerChild(dest_cuid, cuid)
            #log.debug("didn't find %s in call.calls" % cuid)
        ##if dest_uid in self.answerMap:
        #if dest_cuid in call.calls:
            #log.debug("BRIDGE EVENT for a call in the answerMap")
            #call.calls[dest_cuid].logBridgeEvent(dest_cuid, dest_phone, chan1)
            #call.calls[dest_cuid].logEvent('inCall')
            #call.calls[dest_cuid].setCurrentStatus('inCall')
            #d = self.ami.getVar(chan2, 'THREE_WAY')
            #d.addCallback(self.onGotThreeWay).addErrback(self.onFailure, 'onBridgeEvent')
        #else:
            ##log.debug("didn't find uid: %s in answerMap" % dest_uid)
            #call.registerChild(cuid, dest_cuid)
            #log.debug("didn't find %s in call.calls" % dest_cuid)
    
    def onGotThreeWay(self, result=None):
        if result:
            log.debug("Got three way result of %s" % result)
        else:
            log.debug("This call is not a three-way call")

    def onNewChannel(self, ami, event):
        uid = event['uniqueid']
        chan = event['channel']
        state = event['channelstate']
        cuid = '%s-%s' % (self.host_id, uid)
        #if cuid not in chan_map:
            #chan_map[cuid] = {'chan': chan, 'ami': self}
        #log.debug('New channel at %s' % cuid)

    def onUserEvent(self, ami, event):
        log.info("Got user event of type: %s" % event['userevent'])
        hostid = event['hostid']
        uid = event['unique_id']
        exten = event['exten']
        etype = event['userevent']
        cuid = '%s-%s' % (hostid, uid)
        #if etype == 'confJoin':
            #if cuid in call.calls:
                #call.calls[cuid].joinConference()
            #else:
                #log.debug("got confJoin request for unregistered call leg")
        #elif etype == 'confDepart':
            #if cuid in call.calls:
                #call.calls[cuid].departConference()
            #else:
                #log.debug("got confDepart request for unregistered call leg")
        #elif etype == 'callMap':
            ##map this manager connection (asterisk instance) to this group, tying calls for this group
            ##to this asterisk manager instance
            #call.mapAMI(cuid, self)
        #elif etype == 'answerMap':
            #self.answerMap.append(uid)

    def onHangup(self, ami, event):
        log.debug("hangup called with event: %s" % event)
        uid = event['uniqueid']
        cuid = '%s-%s' % (self.host_id, uid)
        # Remove any stored dtmf buffer information for this call
        if str(uid) in dtmfBuffer:
            log.debug('clearing dtmf buffer for %s' % uid)
            tmp = dtmfBuffer.pop(str(uid))
            log.debug(tmp)
            tmp = None
        #if cuid in call.calls:
            #log.debug("hangup up call %s" % cuid)
            #call.calls[cuid].hangup()
        #else:
            #log.debug("%s is not in %s" % (cuid, call.calls))
        #if cuid in chan_map:
            #log.debug("clearing %s from chan_map" % cuid)
            #chan_map.pop(cuid)
        #if uid in self.answerMap:
            #log.debug("clearing %s from answer Map" % uid)
            #self.answerMap.remove(uid)

    def onNewState(self, ami, event):
        uid = event['uniqueid']
        channel = event['channel']
        channel_state = event['channelstate']
        channel_desc = event['channelstatedesc']
        log.info("Channel %s has new state %s" % (channel, channel_desc))

    def origCall(self, call_params):
        number = call_params['number']
        variable = call_params['variable']
        account = call_params['account']
        cid = call_params['cid']
        group = call_params['group']
        context = call_params['context']
        target = call_params['target']
        def onOrigOk(result, *args):
            log.debug("Originate to %s ok" % number)
        def onOrigErr(reason, *args):
            log.debug("Originate Error for %s: %s" % (number, reason.getTraceback()))
        log.debug("Originating call to %s" % target)
        df = self.ami.originate('%s' % target,
                                context='%s' % context,
                                exten='%s' % number,
                                priority=1,
                                callerid='%s' % cid,
                                async=True,
                                account=account,
                                variable=variable)
        df.addCallbacks(onOrigOk, onOrigErr, callbackArgs=(number), errbackArgs=(number))
        return df

    def grpConfWorker(self, room):
        def onOrigOk(result, *args):
            log.debug("conference injection ok")
        def onOrigErr(reason, *args):
            log.debug("conference injection failed")
        log.debug("initiating conference injection message for conference %s" % room)
        df = self.ami.originate('local/%s@conf-worker' % room,
                                context='conf-worker',
                                priority=1,
                                exten='s',
                                async=True,
                                variable={'room': room})
        log.debug("conf worker for group %s started" % room)
        df.addCallbacks(onOrigOk, onOrigErr)
        return df

    def callWhisperWorker(self, cuid):
        def onOrigOk(result, *args):
            log.debug("call worker injection ok")
        def onOrigErr(reason, *args):
            log.debug("call worker injection failed")
        log.debug("initiating call message injection worker for call %s" % cuid)
        chan = chan_map[cuid]['chan']
        print chan
        log.debug("call whisper worker starting for channel: %s" % chan)
        df = self.ami.originate('local/junk@call-worker',
                                context='call-worker',
                                priority=1,
                                exten='s',
                                async=True,
                                variable={'cuid': cuid, 'chan': chan})
        log.debug("call injection worker for call %s started" % cuid)
        df.addCallbacks(onOrigOk,onOrigErr)
        return df
    
    def termCuid(self, cuid):
        if cuid in self.chan_map:
            chan = chan_map[cuid]['chan']
            df = self.ami.hangup(chan)
            df.addErrback(self.onFailure, 'termCuid')
        
    def termChan(self, chan):
        df = self.ami.hangup(chan)
        df.addErrback(self.onFailure, 'termChan')
            
    def redirectCall(self, cuid, extension, priority, context):
        log.debug("redirect args: cuid: %s, ext: %s, pri: %s, context: %s" % (cuid, extension, priority, context))
        if cuid in chan_map:
            chan = chan_map[cuid]['chan']
            df = self.ami.redirect(chan, context, extension, priority)
            df.addErrback(self.onFailure, 'redirectCall')
        else:
            log.debug("unable to find channel %s in channel map %s.  Unable to redirect" % (cuid, chan_map))
        
    def play_dtmf(self, chan, dtmf):
        log.debug("sending dtmf %s to channel %s" % (dtmf, chan))
        df = self.ami.playDTMF(chan, dtmf)
        df.addErrback(self.onFailure, 'play_dtmf')
        return df
    
class DialerFactory(AMIFactory):
    protocol = DialerProtocol

    def __init__(self, server_id, hostname, domain, ipaddress, maxcalls, enable, cps):
        AMIFactory.__init__(self,amiuser, amipassword,)
        self.loginDefer = defer.Deferred()
        self.server_id = server_id
        self.hostname = hostname
        self.ipaddress = ipaddress
        self.maxcalls = maxcalls
        self.cps = cps
        self.protoList = []

    def clientConnectionLost(self,connector,reason):
        log.debug("We lost connection trying reconnect")
        self.protoList = []
        log.debug("Proto list: %s" % self.protoList)
        protocol = DialerProtocol
        self.loginDefer = defer.Deferred()
        reactor.callLater(10,connector.connect)

    def clientConnectionFailed(self,connector,reason):
        log.debug(reason)
        self.loginDefer = defer.Deferred()
        reactor.callLater(10,connector.connect)

def placeOutCall(number, account, cid, context, target, group, variable={}):
    #find an available server
    pbx_sys = None
    for server in serverList:
        for proto in server.protoList:
            if proto.connected:
                log.info("server %s connected" % server.hostname)
                pbx_sys = proto
                break
            else:
                log.info("server %s not connected" % server.hostname)
    if not pbx_sys:
        log.debug("No connected asterisk servers available")
    else:
        call_params = {}
        call_params['number'] = number
        call_params['account'] = account
        call_params['cid'] = cid
        call_params['group'] = group
        call_params['context'] = context
        call_params['target'] = target
        call_params['variable'] = variable
        tmp = pbx_sys.origCall(call_params)
        return tmp

def getAMI(cuid):
    if cuid not in chan_map:
        return None
    else:
        return chan_map[cuid]

def purgeDtmfBuffer(uid):
    if str(uid) in dtmfBuffer:
        dtmfBuffer[str(uid)] = {'last': time.time(), 'buffer': []}
        log.debug('dtmf buffer for %s purged' % uid)
    else:
        log.debug('requested purge on unknown dtmf buffer for %s' % uid)
        
def fetchDtmfBuffer(uid):
    if str(uid) in dtmfBuffer:
        return dtmfBuffer[str(uid)]
    else:
        log.debug('no dtmf buffer available for %s' % uid)
        return None

def getService():
    from twisted.application import service
    #Return the container service actual services are added when later when get
    #result from database
    amiService = service.MultiService()
    amiService.setName("AMIService")
    df = DialerFactory(1, aminame, amidomain, amiaddr, 100, 1, 10)
    serverList.append(df)
    service = internet.TCPClient(amiaddr, amiport, df, timeout=5)
    service.setName('flexvmAMI')
    amiService.addService(service)
    return amiService

