from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web import server, resource
from twisted.web.client import Agent, HTTPConnectionPool
from twisted.web.http_headers import Headers
from twisted.application import internet
from urlparse import urlparse
from random import choice
import urllib
import utils
import json

wsApiServers = [('127.0.0.1',6543)]
wsApiList = [] #TODO - build this list from the list of wsApiServer in the config file?

log = utils.get_logger("WSAPI")


class mwiApi(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        log.debug(request)
        request.setResponseCode(200)
        return "<html> Sorry, not here. </html>"

    def render_POST(self, request):
        log.debug(request)
        request.setResponseCode(200)
        return "<html> Sorry, not here. </html>"


class wsapiResponse(Protocol):
    def __init__(self, finished):
        log.debug('wsapi:wsapiResponse initialized')
        self.finished = finished
        self.remaining = 1024 * 10
        self.display = None

    def dataReceived(self, bytes):
        if self.remaining:
            self.display = bytes[:self.remaining]
            log.debug('Some data received: %s' % self.display)
            self.remaining -= len(self.display)

    def connectionLost(self, reason):
        log.debug('Finished receiving body: %s, %s' % (reason.type, reason.value))
        log.debug('Response received: %s' % self.display)
        self.finished.callback(self.display)

class wsApiServer:
    
    def __init__(self, hostname, port):
        self.apiHostName = hostname
        self.apiHostPort = port
        self.pool = HTTPConnectionPool(reactor, persistent=False)
        #self.pool.retryAutomatically = False
        #self.pool.maxPersistentPerHost = 100
        #self.pool.cachedConnectionTimeout = 2
        
    def onError(self, reason):
        log.debug(reason)
        return False
        
    def onResponse(self, resp):
        log.debug('entered wsapi:wsApiServer: onResponse')
        log.debug(resp)
        headers = list(resp.headers.getAllRawHeaders())
        log.debug(headers)
        finished = Deferred()
        resp.deliverBody(wsapiResponse(finished))
        finished.addCallbacks(self.getJsonResult,self.onError)
        return finished
    
    def getJsonResult(self, result):
        log.debug('json decoding response')
        log.debug(result)
        jsonResponse = json.loads(result)
        return jsonResponse
    
    def genParameters(self, formedUri, apiMethod, callUniqueId, **kwargs):
        def encodeArgs(uParams, kwargs):
            for key in kwargs:
                uParams[key] = kwargs[key]
            encParams = urllib.urlencode(uParams)
            log.debug(encParams)
            return encParams
        if formedUri:
            log.debug('got a formedUI')
            #formedUri received for formatting
            if kwargs:
                encParams = encodeArgs({}, kwargs)
                req = """%s&%s""" % (formedUri, encParams)
            else:
                req = """%s""" % formedUri
            return req
        elif apiMethod:
            log.debug('got an apiMethod')
            #forumedUri and apiMethod cannot both be non null at the same time
            uParams = {'uid': callUniqueId}
            if kwargs:
                encParams = encodeArgs(uParams, kwargs)
            else:
                encParams = encodeArgs(uParams, {})
            req = """%s?%s""" % (apiMethod, encParams)
            return req
        else:
            log.error('Got neither a formedUri or apiMethod for encoding.')
            return False
    
    def wsapiCall(self, formedUri, apiMethod, callUniqueId, **kwargs):
        log.debug('entered: wsapi:wsapiCall')
        req = self.genParameters(formedUri, apiMethod, callUniqueId, **kwargs)
        if formedUri:
            uri = req
        else:
            uri = "http://%s:%s/%s" % (self.apiHostName, self.apiHostPort, req)
        return self.wsapiRequest(uri)
    
    def wsapiRequest(self, uri):
        log.debug('entered: wsapi:wsapiRequest')
        if uri:
            agent = Agent(reactor, pool=self.pool)
            log.debug(agent)
            log.debug('requesting: %s' % uri)
            headers = {'User-Agent': ['Flex Voicemail PBX Client']}
            d = agent.request("GET", uri, Headers(headers), None)
            log.debug('request sent')
            d.addCallbacks(self.onResponse, self.onError)
            return d
        else:
            return False

def getHost():
    return choice(wsApiList)

def runTests():
    pass

for svr in wsApiServers:
    log.debug(svr)
    wsApiList.append(wsApiServer(svr[0],svr[1]))

def getService():
    root = resource.Resource()
    mwi = mwiApi()
    root.putChild("", mwi)
    root.putChild("mwi", mwi)
    site = server.Site(root)
    service = internet.TCPServer(8012, site)
    service.setName("mwiAPI")
    return service


