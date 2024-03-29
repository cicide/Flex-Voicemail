import uuid
from twisted.application import internet
from twisted.protocols import sip
from twisted.internet import defer
from twisted.cred._digest import calcHA1, calcHA2, calcResponse
from UserDict import UserDict
import utils
import ami

testMode = True

log = utils.get_logger("SIPService")

sipport = 5065


mwiQueue = {}

states = {'idle': 0,
          'waiting': 1,
          'incall': 2,
          'scheduled': 3,
          'finished': 4,
          'failed': 5
          }


class SIPAccount(sip.URL):
    def __init__(self, host, username=None, password=None, proxy=None, port=None, ip=None, tag=None, display=''):
        sip.URL.__init__(self, host, username, password, port, tag=tag)
        self.ip = ip
        self.display = '"{0}"'.format(display)
        
        if proxy:
            self.proxy = proxy
        else:
            self.proxy = host

    def __str__(self):
        return self.toString()
    

class SIPClient(sip.Base):
    
    sessions = {}
    
    def __init__(self):
        sip.Base.__init__(self)
        self.debug = True
        
    def handle_response(self, message, addr):
        self.sessions[message.headers['call-id'][0]](message, addr)
        
    def sendMessage(self, destURL, message):
        if destURL.transport not in ("udp", None):
            raise RuntimeError, "only UDP currently supported"
        if self.debug:
            log.debug("Sending %r to %r" % (message.toString(), destURL))
        log.debug(self.transport)
        self.transport.write(message.toString(), (destURL.proxy, destURL.port or self.PORT))
        
        
class SIPSession():
    
    method = None
    deferred = None
    branch = uuid.uuid4().hex
    
    def __init__(self, account, protocol):
        self.protocol = protocol
        self.state = states['idle']
        self.account = account
        self.callid = uuid.uuid4().hex
        self.via = SIPVia(self.account.ip, branch=self.branch, rport=True)
        self.seq = 0
        
    def requestMessage(self, msg=None):
        if msg is None:
            msg = SIPRequest(self.method, 'sip:{0}'.format(self.account.host))
        msg.addHeader('cseq', '{0} {1}'.format(self.seq, self.method))
        msg.addHeader('Via', str(self.via))
        msg.addHeader('from', str(self.account))
        msg.addHeader('call-id', self.callid)
        #msg.addHeader('Allow', 'INVITE,ACK,OPTIONS,BYE,CANCEL,SUBSCRIBE,NOTIFY,REFER,MESSAGE,INFO,PING')
        return msg
        
    def authResponse(self, wwwauth):
        if wwwauth.startswith('Digest '):
            wwwauth = wwwauth.replace('Digest ', '', 1)
            
        fields = {}
        for field in wwwauth.split(','):
            k, v = field.split('=')
            fields[k] = v.strip('"')
        
        auth = {}
        auth['Username'] = self.account.username
        auth['realm'] = fields['realm']
        auth['nonce'] = fields['nonce']
        auth['uri'] = 'sip:{0}'.format(self.account.host)
        auth['algorithm'] = fields['algorithm']
        ha1 = calcHA1(fields['algorithm'].lower(), self.account.username, fields['realm'], self.account.password,
                      fields['nonce'], None)
        ha2 = calcHA2(fields['algorithm'].lower(), 'REGISTER', 'sip:{0}'.format(self.account.host), None, None)
        r = calcResponse(ha1, ha2, fields['algorithm'].lower(), fields['nonce'], None, None, None)
        auth['response'] = r
        auth['opaque'] = fields['opaque']
        header = []
        for k,v in zip(auth.keys(), auth.values()):
            header.append('{0}="{1}"'.format(k, v))
        header = ', '.join(header)
        
        return 'Digest {0}'.format(header)
    
    def notifyMWI(self, user, host, port, newCount=0, oldCount=0, newUrgent=0, oldUrgent=0, newFax=0, oldFax=0):
        if int(newCount) > 0:
            msgWait = "yes"
        else:
            msgWait = "no"
        n = Mwi(self.account, self.protocol, msgWait, user, host, port, newCount, oldCount, newUrgent, oldUrgent,
                newFax, oldFax)
        return n.deferred
    
class SIPVia(sip.Via):
    
    def __init__(self, host, port=sip.PORT, transport="UDP",  branch=None, rport=False, ttl=None):
        self.host = host
        self.port = port
        self.transport = transport
        self.ttl = ttl
        self.branch = branch
        self.rport = rport
    
    def __str__(self):
        s = 'SIP/2.0/{transport} {host}'.format(transport=self.transport, host=self.host)
        if self.port is not None:
            s += ':{0}'.format(self.port)
        if self.branch is not None:
            s += ';branch={0}'.format(self.branch)
        if self.rport:
            s += ';rport'
        return s
    
class SIPRequest(sip.Request):
        
    def addHeader(self, name, value, order=None):
        if order is None or order > len(self.headers._order):
            sip.Request.addHeader(self, name, value)
        else:
            if self.headers.has_key(name):
                del self.headers._order[name]
            self.headers._order.insert(order, name)
            UserDict.__setitem__(self.headers, name, [value])
    
    def orderHeader(self, name, order=None):
        if self.headers.has_key(name):
            self.addHeader(name, self.headers[name], len(self.headers._order))
        
class Mwi(SIPSession):
    
    method = 'NOTIFY'
    
    def __init__(self, account, protocol, msgWait, user, host, port, newCount=0, oldCount=0, newUrgent=0, oldUrgent=0,
                 newFax=0, oldFax=0):
        SIPSession.__init__(self, account, protocol)
        self.msgWaiting = msgWait
        self.newCount = newCount
        self.oldCount = oldCount
        self.newUrgent = newUrgent
        self.oldUrgent = oldUrgent
        self.newFax = newFax
        self.oldFax = oldFax
        self.notifyUser = user
        self.notifyHost = host
        self.notifyPort = int(port)
        self.msgContent,self.msgLength = self.genMwiContent()
        self.deferred = defer.Deferred()
        self.start()
        
    def start(self):
        notify = self.requestMessage()
        log.debug('Sending %s' % str(notify))
        self.protocol.sessions[self.callid] = self.handle_response
        destAccount = SIPAccount(self.notifyHost, username=self.notifyUser, ip=self.notifyHost, port=self.notifyPort,
                                 tag=uuid.uuid4().hex, display='Flex Voicemail')
        self.protocol.sendMessage(destAccount, notify)
        self.state = states['waiting']
        
    def genMwiContent(self):
        uri = 'sip:{0}@{1}'.format(self.notifyUser, self.account.ip)
        msg = """Messages-Waiting: %s\nMessage-Account: %s\nVoice-Message: %s/%s (%s/%s)\nFax-Messages: %s/%s""" % (
            self.msgWaiting, 
            uri, 
            self.newCount,
            self.oldCount,
            self.newUrgent,
            self.oldUrgent,
            self.newFax,
            self.oldFax
        )
        return msg, len(msg)
    
    def requestMessage(self):
        self.seq +=1
        msg = SIPRequest(self.method, 'sip:{0}@{1}'.format(self.notifyUser, self.notifyHost))
        sub = SIPSession.requestMessage(self, msg)
        sub.addHeader('Route','<sip:{0}@{1}:{2};lr>'.format(self.notifyUser, self.notifyHost, self.notifyPort), 0)
        #sub.addHeader('to', '<sip:{0}@{1};tag={2}>'.format(self.account.username, self.account.ip, self.account.tag))
        sub.addHeader('to', '<sip:{0}@{1};tag={2}>'.format(self.notifyUser, self.account.ip, self.account.tag))
        sub.addHeader('contact', '<sip:{0}@{1}:{2}>'.format(self.account.username, self.account.ip, self.account.port))
        #sub.addHeader('Accept','application/simple-message-summary')
        #sub.addHeader('Allow', 'INVITE,ACK,OPTIONS,BYE,CANCEL,SUBSCRIBE,NOTIFY,REFER,MESSAGE,INFO,PING')
        sub.addHeader('Event',"message-summary")
        sub.addHeader('Content-Type','application/simple-message-summary')
        sub.addHeader('Content-Length', self.msgLength)
        sub.addHeader('Max-Forwards', 70)
        sub.bodyDataReceived(self.msgContent)
        #sub.addHeader('Allow-Events','talk, hold, conference, LocalModeStatus')
        # presence RFC3856, dialog RFC4235
        return sub
        
    def handle_response(self,message,addr):
        log.debug('Received %s' % str(message))
        if message.code ==  401:
            wwwauth = message.headers['www-authenticate'][0]
            authheader = self.authResponse(wwwauth)
            
            reg = self.requestMessage()
            reg.addHeader('Authorization', authheader)
            
            self.protocol.sessions[self.callid] = self.handle_response
            self.protocol.sendMessage(self.account, reg)
            self.state = states['waiting']
            
        elif message.code == 200:
            self.state = states['scheduled']
            log.debug('Notified!')
            self.deferred.callback(self)
        else:
            self.deferred.callback(self)    
        
    
protocol = SIPClient()
account = SIPAccount('192.168.10.175', 'asterisk', None, None, ip='192.168.10.175', port=5060, tag=uuid.uuid4().hex,
                     display='Flex Voicemail')
session = SIPSession(account, protocol)

def notifyMWI(session, user, host, port, new, old, newUrgent, oldUrgent, newFax, oldFax):
    def onNotify(result):
        log.debug('Notification came back!')
    def onErr(reason):
        log.error(reason)
        
    dmwi = session.notifyMWI(str(user), str(host), str(port), str(new), str(old), str(newUrgent), str(oldUrgent),
                             str(newFax), str(oldFax))
    dmwi.addCallback(onNotify).addErrback(onErr)

def sendMwi(user, new, old, newUrgent=0, oldUrgent=0, newFax=0, oldFax=0):
    """
    Send a mwi message to a deivce

    @param user:
    @param new:
    @param old:
    @param newUrgent:
    @param oldUrgent:
    @param newFax:
    @param oldFax:
    @return:
    """

    # find the requested user in the sip registry.
    # TODO - make this call through the call object
    log.debug('getting peer data for user %s' % user)
    peerdata = ami.getPeerData(user)
    log.debug(peerdata)
    if not peerdata:
        log.debug("queueing mwi request for next device login")
        # place the mwi notification in the queue
        mwiQueue[user] = {'new': new, 'old': old, 'newUrgent': newUrgent, 'oldUrgent': oldUrgent, 'newFax': newFax,
                          'oldFax': oldFax}
    else:
        host, port = peerdata['address'].split(':')
        log.debug("sending mwi notification to %s" % user)
        notifyMWI(session, user, host, port, new, old, newUrgent, oldUrgent, newFax, oldFax)
    return True


def newRegistration(peer):
    """
    For any newly registered sip endpoints we check for any queued up mwi message and send them

    @param peer: peer name
    """
    log.debug("got a newly registered device, checking for queued up mwi indicators")
    log.debug(mwiQueue)
    qd = mwiQueue.pop(peer, None)
    if qd:
        tmp = sendMwi(peer, qd['new'], qd['old'], qd['newUrgent'], qd['oldUrgent'], qd['newFax'], qd['oldFax'])



def runTests():
    log.debug('Running SIP test.')
    notifyMWI(session, '2609', '192.168.10.95', '5060', '5', '3', '0', '0', '0', '0')
    #notifyMWI(session, '2614', '192.168.10.98', '5060', '17', '21', '2', '0', '0','3')
    #notifyMWI(session, '2613', '192.168.10.98', '5060', '3', '5', '1', '2', '0', '0')

def getService():
    service = internet.UDPServer(sipport, protocol)
    service.setName("SIPService")
    return service