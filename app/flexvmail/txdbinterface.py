#!/usr/local/bin/python

from twisted.enterprise import adbapi
from twisted.internet import threads
from twisted.internet.defer import Deferred
import MySQLdb
import threading
import Queue
import utils

log = utils.get_logger("txDBmysql")

ranconnect = 0
dbpool = None
query_q=Queue.Queue()

class txDBPool:
    def __init__(self, dbname=None, username=None, password = None,  host = None):
        global ranconnect
        if not ranconnect:
            log.debug("Running connect")
            log.debug("dbname: %s, username: %s, password: %s, host: %s" % (dbname, username, password, host))
            self.connect(dbname, username, password, host)
            #self.connect('family', 'family', 'vcarrier', 'localhost')
        else:
            log.debug("Connect already ran")

    def connect(self, dbname, username, password, host):
        global ranconnect, dbpool
        ranconnect = 1
        dbpool = self.dbpool = adbapi.ConnectionPool( 'MySQLdb', db=dbname, user=username, passwd=password, host=host, cp_min=3, cp_max=5, cp_noisy=True, cp_reconnect=1)

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
        log.debug("running query: %s" % self.query)
        return self.resultdf

    def onResult(self, result):
        self.resultdf.callback(result)

    def onFail(self, error):
        if isinstance(error, adbapi.ConnectionLost):
            log.info("We lost connection to db. re-running the query")
            return self.runQuery()
        self.resultdf.errback(error)

def _getVmMessages(txn, gid, ext):
    sql = """SELECT id, cidname, cidnum, create_time, status, duration, file
             FROM voicemail
             WHERE gid='%s'
             AND ext = '%s'
             AND status in (0,1)
             AND duration > 0"""
    sql_args = (gid, ext)
    sql_q = sql % sql_args
    log.debug("running db query: %s" % sql_q)
    txn.execute(sql_q)
    log.debug("fetching query result")
    result = txn.fetchall()
    log.debug("got query result of: %s" % result)
    if result:
        log.debug("got query result: %s" % result)
        return result[0][0]
    else:
        return []

def _getVmCount(txn, gid, ext):
    sql = """SELECT COUNT(*)
             FROM voicemail
             WHERE gid='%s'
             AND ext='%s'
             AND status IN (0,1)
             AND duration > 0"""
    sql_args = (gid, ext)
    sql_q = sql % sql_args
    log.debug("running db query: %s" % sql_q)
    txn.execute(sql_q)
    log.debug("fetching query result")
    result = txn.fetchall()
    log.debug("got query result %s" % result)
    if result:
        return result[0][0]
    else:
        return 0

def _addCdrRecord(txn, cdr):
    #runs in a thread, won't block
    arg=[]
    sql = []
    val = []
    sql1 = 'INSERT INTO call_detail_record ('
    for key in cdr:
        sql.append(key)
        arg.append(cdr[key])
        val.append("""'%s'""")
    sql2 = '%s' % ( ','.join ([str(x) for x in sql]))
    sql3 = ') VALUES ('
    sql4 = '%s' % ( ','.join ([str(x) for x in val]))
    sql5 = ')'
    sql_final = sql1+sql2+sql3+sql4+sql5
    arg_list = tuple(arg)
    sql_q = sql_final % arg_list
    txn.execute(sql_q)
    txn.execute("""SELECT LAST_INSERT_ID()""")
    result = txn.fetchall()
    if result:
        return result[0][0]
    else:
        return None

def _addVmRecord(txn, gid, exten, cidname, cidnum, create_time, status, duration, file_loc, msg_type, msg_ref):
    #runs in a thread, won't block
    sql = """INSERT INTO voicemail (gid,
                                    ext,
                                    cidname,
                                    cidnum,
                                    create_time,
                                    status,
                                    duration,
                                    file,
                                    msg_type,
                                    msg_ref)
                  VALUES ('%s',
                          '%s',
                          '%s',
                          '%s',
                          %i,
                          %i,
                          %i,
                          '%s',
                          %s,
                          %s)"""
    log.debug("query: %s" % sql)
    sql_args = (gid,
                exten,
                cidname,
                cidnum.strip(),
                create_time,
                status,
                duration,
                file_loc,
                msg_type,
                msg_ref)
    sql_query = sql % sql_args
    log.debug("running query: %s" % sql_query)
    txn.execute(sql_query)
    txn.execute("""SELECT LAST_INSERT_ID()""")
    result = txn.fetchall()
    if result:
        return result[0][0]
    else:
        return None

def _addGroupMsgRecord(txn, gid, ext, create_time, lifetime, confirm, recipients, delivery, file_loc):
    sql = """INSERT INTO grp_msg (gid,
                                  ext,
                                  create_time,
                                  lifetime,
                                  confirm,
                                  recipients,
                                  rec_confirm,
                                  delivery,
                                  file_loc)
                          VALUES ('%s',
                                  '%s',
                                  %i,
                                  %i,
                                  %s,
                                  '%s',
                                  '[]',
                                  %s,
                                  '%s')"""
    sql_args = (gid,
                ext,
                create_time,
                lifetime,
                confirm,
                recipients,
                delivery,
                file_loc)
    log.debug("sql: %s" % sql)
    sql_q = sql % sql_args
    txn.execute(sql_q)
    log.debug("running query: %s" % sql_q)
    txn.execute("""SELECT LAST_INSERT_ID()""")
    result = txn.fetchall()
    if result:
        return result[0][0]
    else:
        return None


def addGroupMsgRecord(gid, ext, create_time, lifetime, confirm, recipients, delivery, file_loc):
    log.debug("Adding group message record for %s" % gid)
    return dbpool.runInteraction(_addGroupMsgRecord, gid, ext, create_time, lifetime, confirm, recipients, delivery, file_loc)

def addCdrRecord(cdr):
    return dbpool.runInteraction(_addCdrRecord, cdr)

def addVmRecord(gid, exten, cidname, cidnum, create_time, status, duration, file_loc, msg_type, msg_ref):
    return dbpool.runInteraction(_addVmRecord, gid, exten, cidname, cidnum, create_time, status, duration, file_loc, msg_type, msg_ref)

def getVmCount(gid, exten):
    return dbpool.runInteraction(_getVmCount, gid, exten)

def getVmMessages(gid, exten):
    sql = """SELECT id, cidname, cidnum, create_time, status, duration, file, msg_type, msg_ref
             FROM voicemail
             WHERE gid='%s'
             AND ext = '%s'
             AND status in (0,1)
             AND duration > 0"""
    sql_args = (gid, exten)
    sql_q = sql % sql_args
    log.debug("running query %s" % sql_q)
    txdbi = txDBInterface(sql_q)
    return txdbi.runResultQuery()
    #return dbpool.runInteraction(_getVmMessages, gid, exten)

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

