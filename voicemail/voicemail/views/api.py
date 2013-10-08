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
    UserSession,
    State,
    )

from pyramid.httpexceptions import (
    HTTPFound,
    HTTPNotFound,
    )

import datetime
import deform
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
        prompt = DBSession.query(Prompt). \
            filter_by(name=Prompt.userNotExist).first()
        return False, dict(
            action="play",
            prompt=prompt.getFullPrompt(),
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
        log.debug("Missing parameters entension %s, callid %s, callerid %s \
            tree %s" % (extension, callid, callerid, tree))
        return returnPrompt(name=Prompt.invalidRequest)
    # lets get the user
    user = DBSession.query(User).filter_by(extension=extension).first()

    success, retdict = userCheck(user)
    if not success:
        return retdict

    user_session = None
    if tree == "leaveMessage":
        if user.vm_prefs.vm_greeting:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.userGreeting).first()
        elif user.vm_prefs.vm_name_recording is not None:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.userNameRecording).first()
        else:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.userLeaveMessage).first()
        return dict(
            action="record",
            prompt=prompt.getFullPrompt(user=user),
            nextaction=request.route_url(
                'savemessage',
                _query={'user':extension, 'uid':callid,
                        'callerid':callerid}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['#', ],
                folder=user.vm_prefs.folder,
        )
    elif tree == "accessMenu":
        try:
            user_session = DBSession.query(UserSession).filter_by(uid=callid).first()
            log.debug("looking for a user Session %s" % user_session)
        except:
            pass

        if user_session is None:
            log.debug("Creating a user Session")
            user_session = UserSession()
            user_session.uid = callid
            state = State()
            state.unread = []
            state.read = []
            state.first = 1
            for i in user.voicemails:
                if i.is_read:
                    state.read.append(i.id)
                else:
                    state.unread.append(i.id)
            user_session.saveState(state=state)
            DBSession.add(user_session)
            DBSession.flush()
        log.debug("UserSession created for a user Session %s" % user_session)
            
        # TODO add temporary greeting stuff
        # so first is get the prompt for Voicemail Summary
        prompt = DBSession.query(Prompt). \
            filter_by(name=Prompt.vmSummary).first()
        retprompt = prompt.getFullPrompt(user=user)
        prompt = DBSession.query(Prompt). \
            filter_by(name=Prompt.userVmAccess).first()
        retprompt.extend(prompt.getFullPrompt(user=user))
        return dict(
            action="play",
            prompt=retprompt,
            nextaction=request.route_url(
                'handlekey',
                _query={'user':extension, 'menu':'main', 'uid':callid}),
            invalidaction=request.route_url('invalidmessage'),
            dtmf=['1', '2', '3', '5', '7', '*4']
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

    if(not extension or not callid or not callerid or not vmfile):
        log.debug(
            "Invalid parameters extension %s callid %s callerid %s vmfile %s",
            extension, callid, callerid, vmfile)
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug(
            "User Not Found extension %s callid %s callerid %s \
            vmfile %s duraiton %s",
            extension, callid, callerid, vmfile, duration)
        return retdict

    # time to create a voicemail for this user
    v = Voicemail()
    v.cid_number = callerid
    # Altered because vmfile already have filepath and
    # hence getting vm listed in our web app.
    v.path = vmfile
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
    vmid = request.GET.get('vmid', None)
    menu = request.GET.get('menu', None)
    callid = request.GET.get('uid', None)
    log.debug(
        "HandleKey called with extension %s key %s vmid %s menu %s",
        extension, key, vmid, menu)
    if extension is None or (key is None and vmid is None) or menu is None \
            or callid is None:
        log.debug(
            "Invalid parameters extension %s key %s menu %s",
            extension, key, menu)
        return returnPrompt(name=Prompt.invalidRequest)

    user_session = DBSession.query(UserSession).filter_by(uid=callid).first()
    state = user_session.getState()
    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug("User Not Found extension %s", extension)
        return retdict
    if menu == "main":
        if key == "1":
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.main1RecordMessage).first()
            return dict(
                action="record",
                prompt=prompt.getFullPrompt(user=user),
                nextaction=request.route_url(
                    'idontknow',
                    _query={'user': extension, 'uid': callid,
                            'callerid': callerid}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['#', '*7'],
                folder=user.vm_prefs.folder,
                )
        elif key == "2":
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state)
        elif key == "3":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "*4":
            return returnHelpMenu(request=request, user=user)
        elif key == "5":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == "help":
        if key == "1":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "2":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "3":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "5":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "*7":
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.userVmAccess).first()
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(user=user),
                nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'main'}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['1', '2', '3', '5', '7', '*4'],
            )
        elif key == "7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == "vmaccess":
        log.debug(
            "HandleKey called with extension %s key %s vmid %s menu %s",
            extension, key, vmid, menu)
        if key == "0":
            return returnPrompt(name=Prompt.invalidRequest)
        if key == "1":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "*3":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "#":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "23":
            return returnPrompt(name=Prompt.invalidRequest)
        else:
            log.debug(
                "Invalid Input with extension %s key %s vmid %s menu %s",
                extension, key, vmid, menu)
            return returnPrompt(name=Prompt.invalidRequest)
    return returnPrompt(name=Prompt.invalidRequest)


def getMessage(request, menu, user, state=None):
    # Lets check if unread vms are there
    # if not then old messages
    # else no message
    v = None
    prompt = None
    log.debug(
        "Called getMessage with state %s %s %s %s" % \
            (state.unread, state.read, state.first, state.curmessage))
    if state.first == 1:
        prompt = DBSession.query(Prompt). \
            filter_by(name=Prompt.firstMessage).first()
        log.debug("First prompt %s" % prompt)
    else:
        # TODO put the last message logic
        prompt = DBSession.query(Prompt). \
            filter_by(name=Prompt.nextMessage).first()
        log.debug("next prompt %s" % prompt)

    if len(state.unread) != 0:
        v = DBSession.query(Voicemail).filter_by(id=state.unread[0]).first()
        log.debug("Voicemail %s" % v)
    elif len(state.read) != 0:
        v = DBSession.query(Voicemail).filter_by(id=state.read[0]).first()

    retPrompt = []
    retPrompt.extend(prompt.getFullPrompt(user=user, number=state.curmessage))
    #lets get the first message and return it as message to place
    prompt = DBSession.query(Prompt).filter_by(name=Prompt.vmMessage).first()
    p = prompt.getFullPrompt(user=user, vm=v)
    for i in p:
        retPrompt.append(i)
    return dict(
        action="play",
        prompt=retPrompt,
        nextaction=request.route_url(
            'handlekey',
            _query={
                'user': user.extension, 'menu': 'vmaccess', 'vmid': v.id}),
        invalidaction=request.route_url('invalidmessage'),
        dtmf=['0', '1', '*3', '#', '23'],
    )


def returnHelpMenu(request=None, user=None):
    prompt = DBSession.query(Prompt).filter_by(name=Prompt.helpMenu).first()
    return dict(
        action="play",
        prompt=prompt.getFullPrompt(user=user),
        nextaction=request.route_url(
            'handlekey',
            _query={'user': user.extension, 'menu': 'help'}),
        invalidaction=request.route_url('invalidmessage'),
        dtmf=['1', '2', '3', '5', '7', '*7'],
    )


@view_config(route_name='invalidmessage', renderer='json')
def invalidMessage(request):
    return returnPrompt(name=Prompt.invalidMessage)
