#!/usr/local/bin/python

from twisted.application import internet, service
from twisted.internet import reactor, defer
from starpy.manager import AMIFactory, AMIProtocol
import time
import utils
import sipsend

log = utils.get_logger("AMIService")

amiuser = utils.config.get("general", "amiuser")
amipassword = utils.config.get("general", "amipassword")
amiport = utils.config.getint("general", "amiport")
amiaddr = utils.config.get("general", "amiaddr")
aminame = utils.config.get("general", "aminame")
amidomain = utils.config.get("general", "amidomain")

serverList=[]
chan_map = {} # cuid: {chan: channel, ami: ami_obj}

dtmfBuffer = {}  # uid: {last: timestamp, buffer: [list of dtmf events]}
dtmfReg = {}  # { uid: dtmf registration object }
peerList = {}  # {1234: {'peer': 'SIP/1234', 'address': '1.2.3.4:1223', 'time': '128379872.1232', 'status': 'Registered'}}


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
        log.debug('registering User Events')
        ami.registerEvent('UserEvent', self.onUserEvent)
        log.debug('registering Hangups')
        ami.registerEvent('Hangup', self.onHangup)
        log.debug('registering DTMF')
        ami.registerEvent('DTMF', self.onDtmf)
        log.debug('registering Peer Status Events')
        ami.registerEvent('PeerStatus', self.onPeerStatus)
        log.debug('Event Registration Completed')
        self.initServer()
        
    def initServer():
        # doesnt work
        log.debug('requesting sip Peer list')
        d = self.ami.sipPeers()
        d.addCallback(self.onPeerList).addErrback(self.onFailure, 'sipPeers')
        return d
    
    def onPeerList(self, result):
        peer = result['peer']
        address = result['address']
        timestamp = int(result['timestamp'])
        status = result['peerstatus']
        ct = result['channeltype']
        if ct == 'SIP':
            peername = peer.split('/')[1]
            if status == "Registered":
                if peername not in peerList:
                    # notify peer of any queue message waiting
                    sipsend.newRegistration(peername)
                peerList[peername] = {'peer': peer,
                                  'address': address,
                                  'time': timestamp,
                                  'status': status}
            elif status == 'Unregistered':
                tmp = peerList.pop(peername, None)
            else:
                log.debug('got unknown peer status: %s' % status)
        else:
            log.debug('We can only register SIP devices')
        log.debug(peerList)

    def onPeerStatus(self, ami, event):
        self.onPeerList(event)
        log.debug(event)
        
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
        if dtmf_begin in ('Yes', 'yes'):
            if str(uid) in dtmfBuffer:
                dtmfBuffer[str(uid)]['last'] = time.time()
                dtmfBuffer[str(uid)]['buffer'].append(str(digit))
            else:
                dtmfBuffer[str(uid)] = {'last': time.time(), 'buffer': [str(digit)]}
            if str(uid) in dtmfReg:
                dtmfReg[str(uid)].receiveDtmf(str(digit))
            log.debug(dtmfBuffer[str(uid)])
                
    def onUserEvent(self, ami, event):
        log.info("Got user event of type: %s" % event['userevent'])
        hostid = event['hostid']
        uid = event['unique_id']
        exten = event['exten']
        etype = event['userevent']
        cuid = '%s-%s' % (hostid, uid)

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

class DtmfRegistration(object):

    def __init__(self, uid, keylist, maxkeylen, handlekeys, purgeonfail=True, purgeonsuccess=True):
        self.uid = uid
        self.keylist = keylist
        self.maxkeylen = maxkeylen
        self.handler = handlekeys
        self.dtmfbuffer = []
        self.purgeonfail = purgeonfail
        self.purgeonsuccess = purgeonsuccess
        self.lasttime = time.time()
        log.debug('completed dtmf registration for %s' % uid)

    def purgeBuffer(self):
        self.dtmfbuffer = []
        log.debug('dtmf buffer purged')

    def receiveDtmf(self, dtmfVal=None):
        log.debug('dtmf registration for %s received value %s' % (self.uid, dtmfVal))
        if dtmfVal:
            self.dtmfbuffer.append(str(dtmfVal))
            self.lasttime = time.time()
        else:
            pass
        self.checkForMatch()

    def checkForMatch(self):
        log.debug('Checking DTMF buffer to see if we have a match')
        log.debug(self.dtmfbuffer)
        dbuff = ''.join(self.dtmfbuffer)
        if dbuff in self.keylist:
            log.debug('found a dtmf match between buffer and keylist')
            self.onSuccess()
        elif len(self.dtmfbuffer) >= self.maxkeylen:
            self.onFail()
        else:
            log.debug('no valid match for buffer in keylist, max length not reached')
            log.debug('buffer: %s' % dbuff)
            log.debug(self.keylist)
            # we don't yet have a valid match or have collected all the keys yet
            pass

    def onSuccess(self):
        dtmfresult = ''.join(self.dtmfbuffer)
        if self.purgeonsuccess:
            log.debug('dtmf buffer purged!')
            self.purgeBuffer()
        log.debug('calling success method %s with dtmf result %s' % (self.handler, dtmfresult))
        self.handler(dtmfresult)

    def onFail(self):
        log.debug('failed to get valid dtmf')
        if self.purgeonfail:
            log.debug('purging dtmf buffer')
            self.purgeBuffer()


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
        return True
    else:
        log.debug('requested purge on unknown dtmf buffer for %s' % uid)
        dtmfBuffer[str(uid)] = {'last': time.time(), 'buffer' : []}
        return False
        
def fetchDtmfBuffer(uid):
    if str(uid) in dtmfBuffer:
        return dtmfBuffer[str(uid)]
    else:
        log.debug('no dtmf buffer available for %s' % uid)
        return None

def cancelDtmfRegistration(uid):
    log.debug("Cancelleing DTMF registration for %s" % uid)
    tmp = dtmfReg.pop(uid, None)

def startDtmfRegistration(uid, keylist, maxkeylen, handlekeys, purgeonfail=True, purgeonsuccess=True):
    log.debug("Starting DTMF registration for %s" % uid)
    dtmfReg[uid] = DtmfRegistration(uid, keylist, maxkeylen, handlekeys,
                                    purgeonfail=purgeonfail,
                                    purgeonsuccess=purgeonsuccess)
    log.debug("Completed DTMF registration for %s" % uid)

def getPeerData(peer):
    if peer in peerList:
        return peerList[peer]
    else:
        return {}

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

