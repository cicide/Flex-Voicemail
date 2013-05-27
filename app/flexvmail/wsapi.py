from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from random import choice
import urllib
import utils
import json

wsApiServers = [('127.0.0.1',6543)]
wsApiList = [] #TODO - build this list from the list of wsApiServer in the config file?

log = utils.get_logger("WSAPI")

class BeginningPrinter(Protocol):
    def __init__(self, finished):
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
        self.finished.callback(self.display)

class wsApiServer:
    
    def __init__(self, hostname, port):
        self.apiHostName = hostname
        self.apiHostPort = port
        
    def onError(self, reason):
        log.debug(reason)
        return False
        
    def onResponse(self, resp):
        finished = Deferred()
        resp.deliverBody(BeginningPrinter(finished))
        finished.addCallbacks(self.getJsonResult,self.onError)
        return finished
    
    def getJsonResult(self, result):
        log.debug('json decoding response')
        log.debug(result)
        jsonResponse = json.loads(result)
        return jsonResponse
    
    def genParameters(self, apiMethod, callUniqueId, **kwargs):
        uParams = {'cuid': callUniqueId}
        for key in kwargs:
            uParams[key] = kwargs[key]
        encParams = urllib.urlencode(uParams)
        log.debug(encParams)
        req = """%s?%s""" % (apiMethod, encParams)
        return req
    
    def wsapiCall(self, apiMethod, callUniqueId, **kwargs):
        agent = Agent(reactor)
        req = self.genParameters(apiMethod, callUniqueId, **kwargs)
        uri = "http://%s:%s/%s" % (self.apiHostName, self.apiHostPort, req)
        log.debug('requesting: %s' % uri)
        d = agent.request("GET", uri)
        d.addCallbacks(self.onResponse, self.onError)
        return d
        
def getHost():
    return choice(wsApiList)

for server in wsApiServers:
    log.debug(server)
    wsApiList.append(wsApiServer(server[0],server[1]))