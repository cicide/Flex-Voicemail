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
    Voicemail,
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
        log.debug("Missing parameters entension %s, callid %s, callerid %s tree %s" % (extension, callid, callerid, tree))
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
            nextaction=request.route_url('savemessage', _query={'user': extension, 'uid':callid, 'callerid' : callerid}),
            invalidaction=request.route_url('invalidmessage'),
            dtmf=['#',],
            folder=user.vm_prefs.folder,
        )
    elif tree == "accessMenu":
        prompt = DBSession.query(Prompt).filter_by(name=Prompt.userVmAccess).first()
        return dict (
            action="play",
            prompt= prompt.getFullPrompt(user=user),
            nextaction=request.route_url('handlekey', _query={'user': extension, 'menu': 'main'}),
            invalidaction=request.route_url('invalidmessage'),
            dtmf=['1','2','3','5', '7', '*4'],
            )
    
    log.debug("Invalid Request")
    return returnPrompt(name=Prompt.invalidRequest)

@view_config(route_name='savemessage', renderer='json')
def saveMessage(request):
    extension = request.GET.get('user', None)
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    vmfile = request.GET.get('vmfile', None)
    duration = request.GET.get('duration', '0')

    if extension is None or callid is None or callerid is None or vmfile is None:
        log.debug("Invalid parameters extension %s callid %s callerid %s vmfile %s duraiton %s", extension, callid, callerid, vmfile, duration)
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug("User Not Found extension %s callid %s callerid %s vmfile %s duraiton %s", extension, callid, callerid, vmfile, duration)
        return retdict

    # time to create a voicemail for this user
    v = Voicemail()
    v.cid_number = callerid
    v.path =  vmfile # Altered because vmfile already have filepath and hence getting vm listed in our web app.
    v.create_date = datetime.datetime.utcnow()
    v.is_read = False
    v.status = 0
    v.duration = duration
    v.user = user
    
    DBSession.add(v)

    return returnPrompt(name=Prompt.messageSaved)

@view_config(route_name='handlekey', renderer='json')
def handleKey(request):
    extension = request.GET.get('user', None)
    key = request.GET.get('key', None)
    menu = request.GET.get('menu', None)
    if extension is None or key is None or menu is None:
        log.debug("Invalid parameters extension %s key %s menu %s", extension, key, menu)
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug("User Not Found extension %s", extension)
        return retdict
    if menu == "main":
        if key == "1":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="2":
            prompt = DBSession.query(Prompt).filter_by(name=Prompt.vmSummary).first()
            return dict (
                action="play",
                prompt= prompt.getFullPrompt(user=user),
                nextaction=request.route_url('handlekey', _query={'user': extension, 'menu': 'vmaccess'}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['0','*3','#','23'],
                )
        elif key =="3":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="*4":
            return returnHelpMenu(request=request, user=user)
        elif key =="5":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == "help":
        if key == "1":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="2":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="3":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="5":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key =="*7":
            prompt = DBSession.query(Prompt).filter_by(name=Prompt.userVmAccess).first()
            return dict (
                action="play",
                prompt= prompt.getFullPrompt(user=user),
                nextaction=request.route_url('handlekey', _query={'user': extension, 'menu': 'main'}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['1','2','3','5', '7', '*4'],
                )
        elif key =="7":
            return returnPrompt(name=Prompt.invalidRequest)
    return returnPrompt(name=Prompt.invalidRequest)

def returnHelpMenu(request=None, user=None):
    prompt = DBSession.query(Prompt).filter_by(name=Prompt.helpMenu).first()
    return dict(
            action="play",
            prompt= prompt.getFullPrompt(user=user),
            nextaction=request.route_url('handlekey', _query={'user': user.extension, 'menu': 'help'}),
            invalidaction=request.route_url('invalidmessage'),
            dtmf=['1','2','3','5', '7', '*7'],
            )

@view_config(route_name='invalidmessage', renderer='json')
def invalidMessage(request):
    return returnPrompt(name=Prompt.invalidMessage)
