#!/usr/local/bin/python
"""
Interactive Voice Response (IVR) module.

implements IVR methods
"""

import dbapi
import time
import utils
from datetime import datetime

class Ivr:
    
    """
    IVR method
    """
    
    def __init__(self, ivrDef):
        self.definition = ivrDef
        self.rules = self.inflateRules(self.definition)

    def inflateRules(self, definition):
        # Inflate rule set from self.definition
        pass
    
    def start(self, call, callerId, ivrArgs, agi):
        self.call = call
        self.callerId = callerId
        self.ivrArgs = ivrArgs
        self.agi = agi
        
        
    def playBlockingMessageFile(self, 
                                filePath, 
                                preDelay=0, 
                                postDelay=0):
        pass
    
    def playNonBlockingMessageFile(self, 
                                   filePath, 
                                   preDelay=0, 
                                   postDelay=0, 
                                   allowResponse=False,
                                   allowResponseLength=1,
                                   allowedResponse=['0','1','2','3','4','5','6','7','8','9']):
        pass
        
    def recordMessage(self,
                      filePath,
                      controls=False):
        pass
    
    