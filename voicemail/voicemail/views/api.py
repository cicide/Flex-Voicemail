from __future__ import (absolute_import, division, print_function,
    unicode_literals)
from pyramid.response import Response
from pyramid.view import (
    view_config,
    forbidden_view_config,
    )

from pyramid.security import (
    remember,
    forget,
    authenticated_userid,
    )

from sqlalchemy.exc import DBAPIError

from ..models.models import (
    DBSession,
    User,
    Prompt,
    )

from pyramid.httpexceptions import (
    HTTPFound,
    HTTPNotFound,
    )

import datetime
import deform
import colander
import colander
import deform
import six
from bag.web.pyramid.flash_msg import FlashMessage

import logging
log = logging.getLogger(__name__)

def returnPrompt(name):
    prompt = DBSession.query(Prompt).filter_by(name=name).first()
    return dict(
        action="play",
        prompt=prompt.getFullPrompt(),
        nextaction="agi:hangup",
        )
def userCheck(user):
    if user is None:
        prompt = DBSession.query(Prompt).filter_by(name=Prompt.userNotExist).first()
        return False, dict (
            action="play",
            prompt= prompt.getFullPrompt(),
            nextaction="agi:hangup",
        )
    return True, None 
@view_config(route_name='startcall', renderer='json')
def startCall(request):
    ''' This is the start of any call. Entry point'''

    extension = request.GET.get('user', None)
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    tree = request.GET.get('tree', None)

    if extension is None or callid is None or callerid is None or tree is None:
        return returnPrompt(name=Prompt.invalidRequest)
    # lets get the user
    user = DBSession.query(User).filter_by(extension=extension).first()

    success, retdict = userCheck(user)
    if not success:
        return retdict

    if tree == "leaveMessage":
        if user.vm_prefs.vm_greeting:
            prompt = DBSession.query(Prompt).filter_by(name=Prompt.userGreeting).first()
        elif user.vm_prefs.vm_name_recording is not None:
            prompt = DBSession.query(Prompt).filter_by(name=Prompt.userNameRecording).first()
        else: 
            prompt = DBSession.query(Prompt).filter_by(name=Prompt.userLeaveMessage).first()
        return dict (
            action="record",
            prompt= prompt.getFullPrompt(user=user),
            nextaction=request.route_url('savemessage', _query={'user': extension, 'callid':callid, 'callerid' : callerid}),
            invalidaction=request.route_url('invalidmessage'),
            dtmf=['#',],
            folder=user.vm_prefs.folder,
        )
    elif tree == "accessMessage":
        prompt = DBSession.query(Prompt).filter_by(name=Prompt.userVmAccess).first()
        return dict (
            action="play",
            prompt= prompt.getFullPrompt(),
            nextaction="agi:hangup",
            )
    
    return returnPrompt(name=Prompt.invalidRequest)

@view_config(route_name='savemessage', renderer='json')
def saveMessage(request):
    extension = request.GET.get('user', None)
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    vmfile = request.GET.get('vmfile', None)
    duration = request.GET.get('duration', None)

    if extension is None or callid is None or callerid is None or vmfile is None:
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        return retdict

    # time to create a voicemail for this user
    v = Voicemail()
    v.cid_number = callerid
    v.path = user.vm_prefs.folder+ '/' + vmfile
    v.create_date = datetime.datetime.utcnow()
    v.is_read = False
    v.status = 0
    v.duration = duration
    v.user = user
    
    DBSession.add(v)

    return returnPrompt(name=Prompt.messageSaved)

@view_config(route_name='invalidmessage', renderer='json')
def invalidMessage(request):
    return returnPrompt(name=Prompt.invalidMessage)
