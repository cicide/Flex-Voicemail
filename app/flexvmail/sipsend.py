import uuid
from twisted.application import internet
from twisted.protocols import sip
from twisted.internet import reactor, defer
from UserDict import UserDict
import utils, call

testMode = True

log = utils.get_logger("SIPService")

sipport = 5065

states = {'idle': 0,
          'waiting':1,
          'incall':2,
          'scheduled':3,
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
            
    def toString(self, includeTag=True):
        l = []; w = l.append
        w("{0} <sip:".format(self.display if includeTag else ''))
        if self.username is not None:
            w(self.username)
            w("@")
        w(self.host)
        if self.port is not None:
            w(":%d" % self.port)
        w(">")
        if self.usertype is not None:
            w(";user=%s" % self.usertype)
        for n in ("transport", "ttl", "maddr", "method", "tag"):
            v = getattr(self, n)
            if v is not None:
                if n == 'tag' and includeTag == False:
                    pass
                else:
                    w(";%s=%s" % (n, v))
        for v in self.other:
            w(";%s" % v)
        if self.headers:
            w("?")
            w("&".join([("%s=%s" % (specialCases.get(h) or dashCapitalize(h), v)) for (h, v) in self.headers.items()]))
        
        return "".join(l)
        
        
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
            wwwauth = wwwauth.replace('Digest ','',1)
            
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
        ha1 = calcHA1(fields['algorithm'].lower(), self.account.username, fields['realm'], self.account.password, fields['nonce'], None)
        ha2 = calcHA2(fields['algorithm'].lower(), 'REGISTER', 'sip:{0}'.format(self.account.host), None, None)
        r = calcResponse(ha1, ha2, fields['algorithm'].lower(), fields['nonce'], None, None, None)
        auth['response'] = r
        auth['opaque'] = fields['opaque']
        header = []
        for k,v in zip(auth.keys(), auth.values()):
            header.append('{0}="{1}"'.format(k, v))
        header = ', '.join(header)
        
        return 'Digest {0}'.format(header)
    
    def notifyMWI(self, user, host, port, newCount=0, oldCount=0):
        if int(newCount) > 0:
            msgWait = "yes"
        else:
            msgWait = "no"
        n = Mwi(self.account, self.protocol, msgWait, newCount, oldCount, user, host, port)
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
    
    def __init__(self, account, protocol, msgWait, newCount, oldCount, user, host, port):
        SIPSession.__init__(self, account, protocol)
        self.msgWaiting = msgWait
        self.newCount = newCount
        self.oldCount = oldCount
        self.notifyUser = user
        self.notifyHost = host
        self.notifyPort = port
        self.notifyURI = 'sip:%s@%s' % (user, host)
        self.msgContent,self.msgLength = self.genMwiContent(msgWait, newCount, oldCount, self.notifyURI)
        self.deferred = defer.Deferred()
        self.start()
        
    def start(self):
        reg = self.requestMessage()
        log.debug('Sending %s' % str(reg))
        self.protocol.sessions[self.callid] = self.handle_response
        self.protocol.sendMessage(self.account, reg)
        self.state = states['waiting']
        
    def genMwiContent(self, msgWait, new, old, uri):
        msg = """\n\r\n\n\rMessages-Waiting: %s\r\n
                 Message-Account: %s\r\n
                 Voice-Message: %s/%s (%s/%s)""" % (msgWait, uri, new, old, new, old)
        return msg, len(msg)
    
    def requestMessage(self):
        self.seq +=1
        msg = SIPRequest(self.method, 'sip:{0}@{1}'.format(self.notifyUser, self.notifyHost))
        sub = SIPSession.requestMessage(self)
        #sub.addHeader('Route','<sip:192.168.10.131:5060;lr>', 0)
        sub.addHeader('to', self.notifyURI)
        sub.addHeader('contact', '<sip:{0}@{1}>'.format(self.account.username, self.account.ip) )
        sub.addHeader('Accept','application/simple-message-summary')
        sub.addHeader('Allow', 'INVITE,ACK,OPTIONS,BYE,CANCEL,SUBSCRIBE,NOTIFY,REFER,MESSAGE,INFO,PING')
        sub.addHeader('Event',"message-summary")
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
account = SIPAccount('192.168.10.131','flexvmail',None,None,tag=uuid.uuid4().hex, display='Flex Voicemail')

def notifyMWI(user, host, port, new, old):
    def onNotify(result):
        log.debug('Notification came back!')
    def onErr(reason):
        log.error(reason)
        
    session = SIPSession(account, protocol)
    dmwi = session.notifyMWI(str(user), str(host), str(port), str(new), str(old))
    dmwi.addCallback(onNotify).addErrback(onErr)
        
        
def runTests():
    log.debug('Running SIP test.')
    notifyMWI('2609', '192.168.10.95', '5060', '5', '3')
    notifyMWI('2610', '192.168.10.175', '5060', '17', '21')

def getService():
    service = internet.UDPServer(sipport, protocol)
    service.setName("SIPService")
    return service