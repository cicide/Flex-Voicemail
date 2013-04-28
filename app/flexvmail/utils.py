#!/usr/local/bin/python
"""
Utils module for servers

"""
import logging
import logging.handlers
import ConfigParser

import os 
import sys

_config = None

def set_log_level(log):
    """
    log - target logger object on which log level needs to be set
    """
    config = get_config()
    #log_level should be any one of the following - DEBUG , INFO, ERROR, CRITICAL , FATAL
    log_level = config.get("general", "loglevel")
    log.setLevel(getattr(logging, log_level))
    
def get_logger(name):
    """
    Creates and sets log level on a python logger object 
    Returns the created logger object
    
    name - name of the logger to be created
    """
    log = logging.getLogger(name)
    set_log_level(log)
    return log

def get_post_vars(req):
    vars = {}
    for k, v in req.args.items():
        vars[k] = v[0]
    return vars
    
    
def get_config():
    # Singleton
    global _config
    
    if _config is None:        
        _config = ConfigParser.ConfigParser()
        _config.optionxform = str
        
        filepath = 'etc/family.conf'
        f=open(filepath)
        _config.readfp(f)
        config_log()
    
    return _config
    

def config_log():
    logpath = _config.get("general", "logpath")
    logfile = _config.get("general", "logfile")
    rootlogger = logging.getLogger('')
    fmt = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s : %(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    rootlogger.addHandler(sh)
    rfh = logging.handlers.RotatingFileHandler(logpath+"/"+logfile, maxBytes=900000, backupCount=10)
    rfh.setFormatter(fmt)
    rootlogger.addHandler(rfh)


config = get_config()   
log=get_logger("utils")
