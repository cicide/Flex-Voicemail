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
            user_session.create_date = datetime.datetime.utcnow()
            state = State()
            state.unread = []
            state.read = []
            state.curmessage = 1
            state.uid = callid
            for i in user.voicemails:
                if i.status == 1:
                    continue
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
                    _query={'user': extension, 'menu': 'main', 'uid':callid}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['1', '2', '3', '5', '7', '*4'],
            )
        elif key == "7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == "vmaccess":
        log.debug(
            "HandleKey called with extension %s key %s vmid %s menu %s",
            extension, key, vmid, menu)
        if key != "False":
            state.retryCount = 0
            user_session.saveState(state=state)
            DBSession.add(user_session)
        if key == "0":
            # listen to the message
            # I have no idea when this happens and what to do
            return returnPrompt(name=Prompt.invalidRequest)
        if key == "1":
            # forward / reply to the message
            # chris is implementing this
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "*3":
            # delete the message
            v = DBSession.query(Voicemail).filter_by(id = vmid).first()
            v.status = 1
            v.deleted_on = datetime.datetime.utcnow()
            DBSession.add(v)
            state.nextMessage()
            user_session.saveState(state=state)
            DBSession.add(user_session)
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state)
        elif key == "#":
            # skip message
            v = DBSession.query(Voicemail).filter_by(id = vmid).first()
            v.is_read = 1
            v.read_on = datetime.datetime.utcnow()
            DBSession.add(v)
            state.nextMessage()
            user_session.saveState(state=state)
            DBSession.add(user_session)
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state)
        elif key == "23":
            # play header
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "4":
            # rewind
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "5":
            # toggle pause/play
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "6":
            # advance 
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "44":
            # previous Message
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "4":
            # play header
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "False":
            curposition = getMessage(
                request=request, menu="vmaccess", user=user, state=state)
            return stillThereLoop(
                request=request, user=user, user_session=user_session,
                dtmf=curposition['dtmf'],
                nextaction=curposition['nextaction'],
                extraPrompt=Prompt.stillThereGetMessage
            )
        else:
            log.debug(
                "Invalid Input with extension %s key %s vmid %s menu %s",
                extension, key, vmid, menu)
            return returnPrompt(name=Prompt.invalidRequest)
    return returnPrompt(name=Prompt.invalidRequest)


def getMessage(request, menu, user, state=None, vmid=None):
    # Lets check if unread vms are there
    # if not then old messages
    # else no message
    v = None
    prompt = None
    log.debug(
        "Called getMessage with state %s %s %s %s" % \
            (state.unread, state.read, state.message_type, state.curmessage))

    if state.message_type == "Unread" and state.curmessage <= len(state.unread): #unread messages
        if state.curmessage == 1:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.firstMessage).first()
        elif state.curmessage == len(state.unread):
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.lastMessage).first()
        else:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.nextMessage).first()
        v = DBSession.query(Voicemail).filter_by(id=state.unread[state.curmessage - 1]).first()
    elif state.curmessage <= len(state.read):
        if state.curmessage == 1:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.firstMessage).first()
        elif state.curmessage == len(state.read):
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.lastMessage).first()
        else:
            prompt = DBSession.query(Prompt). \
                filter_by(name=Prompt.nextMessage).first()
        v = DBSession.query(Voicemail).filter_by(id=state.read[state.curmessage - 1]).first()
    else:
        prompt = DBSession.query(Prompt). \
            filter_by(name=Prompt.noMoreMessage).first()

    retPrompt = []
    retPrompt.extend(prompt.getFullPrompt(user=user, number=state.curmessage))
    prompt = DBSession.query(Prompt).filter_by(name=Prompt.vmMessage).first()
    p = prompt.getFullPrompt(user=user, vm=v)
    for i in p:
        retPrompt.append(i)
    prompt = DBSession.query(Prompt).filter_by(name=Prompt.postMessage).first()
    p = prompt.getFullPrompt(user=user)
    for i in p:
        retPrompt.append(i)
    return dict(
        action="play",
        prompt=retPrompt,
        nextaction=request.route_url(
            'handlekey',
            _query={
                'user':user.extension, 'menu': 'vmaccess', 'vmid': v.id, 'uid':state.uid}),
        invalidaction=request.route_url('invalidmessage'),
        dtmf=['0', '1', '*3', '#', '23', '4', '5', '6', '44'],
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


def stillThereLoop(request=None, user=None, nextaction=None, dtmf=None, user_session=None, extraPrompt=None ):
    state = None
    if user_session:
        state = user_session.getState()
    if state and state.retryCount < 3:
        log.debug("StillThereloop called with state %d", state.retryCount)
        state.retryCount = state.retryCount + 1
        user_session.saveState(state=state)
        DBSession.add(user_session)
    else:
        return returnPrompt(name=Prompt.goodbye)
    prompt = DBSession.query(Prompt).filter_by(name=Prompt.stillThere).first()
    retPrompt = prompt.getFullPrompt()
    prompt = DBSession.query(Prompt).filter_by(name=extraPrompt).first()
    for i in prompt.getFullPrompt():
        retPrompt.append(i)
    return dict(
        action="play",
        prompt=retPrompt,
        nextaction=nextaction,
        invalidaction=request.route_url('invalidmessage'),
        dtmf=dtmf,
        )

@view_config(route_name='invalidmessage', renderer='json')
def invalidMessage(request):
    return returnPrompt(name=Prompt.invalidMessage)
