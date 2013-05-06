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
    
    def start(self, call, callerId, ivrArgs):
        self.call = call
        self.callerId = callerId
        self.ivrArgs = ivrArgs
        