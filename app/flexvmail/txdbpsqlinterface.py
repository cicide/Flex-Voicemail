#!/usr/local/bin/python

from twisted.enterprise import adbapi
from twisted.internet import threads
from twisted.internet.defer import Deferred
import psycopg2
import psycopg2.extras, psycopg2.extensions
import threading
import Queue
import utils

log = utils.get_logger("txDB")

ranconnect = 0
dbpool = None
query_q=Queue.Queue()

class txDBPool:
    def __init__(self, dbname=None, username=None, password = None,  host = None):
        global ranconnect 
        if not ranconnect:
            log.debug("Running connect")
            self.connect(dbname, username, password, host)
        else:
            log.debug("Connect already ran")
            
    def connect(self, dbname, username, password, host):
        global ranconnect, dbpool
        ranconnect = 1
        dbpool = self.dbpool = adbapi.ConnectionPool( 'psycopg2', database=dbname, user=username, password=password, host=host, cp_min=3, cp_max=5, cp_noisy=False, cp_reconnect=1)
        
    def onDBConnect(self, arg):
        log.debug("Connected to DB")
        
    def onDBFail(self, error):
        global ranconnect
        ranconnect =0
        log.error("Failed to connect to DB")

class txDBInterface:
    def __init__(self, *query):
        self.dbpool = dbpool
        self.resultdf = Deferred()
        self.query = query
        
    def runResultQuery(self):                
        df = self.dbpool.runQuery(*self.query)
        df.addCallbacks(self.onResult, self.onFail)
        return self.resultdf
        
    def runActionQuery(self):
        df = self.dbpool.runOperation(*self.query)
        df.addCallbacks(self.onResult, self.onFail)
        return self.resultdf

    def onResult(self, result):
        self.resultdf.callback(result)
        
    def onFail(self, error):
        if isinstance(error, adbapi.ConnectionLost):
            log.info("We lost connection to db. re-running the query")
            return self.runQuery()
        self.resultdf.errback(error)    


def texecute(qlist):
    for sql in qlist:
        aexecute(*sql)
    
def execute(*query):
    txdbi = txDBInterface(*query)
    return txdbi.runResultQuery()
    
def aexecute(*query):
    txdbi = txDBInterface(*query)
    return txdbi.runActionQuery()

dbname = utils.config.get("db", "dbname")
username = utils.config.get("db", "username")
password = utils.config.get("db", "password")
host = utils.config.get("db", "host")

txDBPool(dbname, username, password, host)

