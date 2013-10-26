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
    prompt = Prompt.getByName(name=name)
    return dict(
        action="play",
        prompt=prompt.getFullPrompt(),
        nextaction="agi:hangup",
        )


def userCheck(user):
    if user is None:
        prompt = Prompt.getByName(name=Prompt.userNotExist)
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


    if (extension is None and (tree == "leaveMessage" or tree == "accessMenu")) \
            or callid is None or callerid is None or tree is None:
        log.debug("Missing parameters entension %s, callid %s, callerid %s \
            tree %s" % (extension, callid, callerid, tree))
        return returnPrompt(name=Prompt.invalidRequest)
    # lets get the user
    user = None
    if extension:
        user = DBSession.query(User).filter_by(extension=extension).first()

        success, retdict = userCheck(user)
        if not success:
            return retdict

    user_session = None
    if tree == "leaveMessage":
        if user.vm_prefs.vm_greeting:
            prompt = Prompt.getByName(name=Prompt.userGreeting)
        elif user.vm_prefs.vm_name_recording is not None:
            prompt = Prompt.getByName(name=Prompt.userNameRecording)
        else:
            prompt = Prompt.getByName(name=Prompt.userLeaveMessage)
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
    elif tree == "loginMenu":
        prompt = Prompt.getByName(name=Prompt.loginWelcomeMessage)
        return dict(
            action="play",
            prompt=prompt.getFullPrompt(),
            nextaction=request.route_url(
                'handlelogin',
                _query={'menu': 'login', 'callerid':callerid, 'uid':callid}),
            invalidaction=request.route_url('invalidmessage'),
        )

    elif tree == "accessMenu":
        user_serssion = getUserSession(callid, user)
        log.debug("UserSession created for a user Session %s" % user_session)
            
        # TODO add temporary greeting stuff
        # so first is get the prompt for Voicemail Summary
        prompt = Prompt.getByName(name=Prompt.vmSummary)
        retprompt = prompt.getFullPrompt(user=user)
        prompt = Prompt.getByName(name=Prompt.userVmAccess)
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


@view_config(route_name='handlelogin', renderer='json')
def handleLogin(request):
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    key = request.GET.get('key', None)
    extension = request.GET.get('user', None)
    count = request.GET.get('cnt', 0)

    if (key is None and extension is None)  or callid is None:
        log.debug(
            "Invalid parameters key %s callid %s extension %s",
            key, callid, extension)
        return returnPrompt(name=Prompt.invalidRequest)
    user = None
    if key:
        user = DBSession.query(User).filter_by(extension=key).first()
    elif extension:
        user = DBSession.query(User).filter_by(extension=extension).first()
    
    if user is None and not extension:
        prompt = Prompt.getByName(name=Prompt.loginInvalidMailbox)
        count = int(count) + 1
        if count < 3:
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                nextaction=request.route_url(
                    'handlelogin',
                    _query={'callerid':callerid, 'uid':callid, 'cnt':count}),
                invalidaction=request.route_url('invalidmessage'),
            )
        else:
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(user=user),
                nextaction="agi:hangup",
            )
    elif extension is None: 
        prompt = Prompt.getByName(Prompt.loginInputPassword)
        return dict(
             action="play",
             prompt=prompt.getFullPrompt(),
             nextaction=request.route_url(
                 'handlelogin',
                 _query={'uid':callid, 'callerid':callerid, 'user':key}),
             invalidaction=request.route_url('invalidmessage'),
         )
    else:
        log.debug("Checking username for a user %s password %s", extension, key)
        user = DBSession.query(User).filter_by(extension=extension, pin = key).first()
        if user is None:
            count = int(count) + 1
            if count < 3:
                prompt = Prompt.getByName(Prompt.loginInvalidPassword)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    nextaction=request.route_url(
                        'handlelogin',
                        _query={'uid':callid, 'user':extension, 'callerid':callerid, 'cnt':count}),
                    invalidaction=request.route_url('invalidmessage'),
                )
            else:
                prompt = Prompt.getByName(Prompt.loginInvalidPassword)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    nextaction="agi:hangup",
                )
        else:
            prompt = Prompt.getByName(Prompt.loginLoggedIn)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(user=user),
                nextaction=request.route_url(
                    'handlekey',
                    _query={'menu': 'vmaccess', 'uid':callid, 'callerid':callerid, 'user':extension}),
                invalidaction=request.route_url('invalidmessage'),
            )
        


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
            prompt = Prompt.getByName(name=Prompt.main1RecordMessage)
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
            prompt = Prompt.getByName(name=Prompt.userVmAccess)
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

    msgToGet = None
    if state.curmessage == 1:
        prompt = Prompt.getByName(name=Prompt.firstMessage)
    elif state.curmessage == len(state.unread):
        prompt = Prompt.getByName(name=Prompt.lastMessage)
    else:
        prompt = Prompt.getByName(name=Prompt.nextMessage)

    if state.message_type == "Unread" and state.curmessage <= len(state.unread): #unread messages
        msgToGet = state.unread[state.curmessage - 1]
    elif state.curmessage <= len(state.read):
        msgToGet = state.read[state.curmessage - 1]
    else:
        prompt = Prompt.getByName(name=Prompt.noMoreMessage)

    if msgToGet:
        v = DBSession.query(Voicemail).filter_by(id=msgToGet).first()

    retPrompt = []
    retPrompt.extend(prompt.getFullPrompt(user=user, number=state.curmessage))
    prompt = Prompt.getByName(name=Prompt.vmMessage)
    p = prompt.getFullPrompt(user=user, vm=v)
    for i in p:
        retPrompt.append(i)
    prompt = Prompt.getByName(name=Prompt.postMessage)
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
    prompt = Prompt.getByName(name=Prompt.helpMenu)
    return dict(
        action="play",
        prompt=prompt.getFullPrompt(user=user),
        nextaction=request.route_url(
            'handlekey',
            _query={'user': user.extension, 'menu': 'help'}),
        invalidaction=request.route_url('invalidmessage'),
        dtmf=['1', '2', '3', '5', '7', '*7'],
    )


def getUserSession(callid, user):
    user_session = None
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
    return user_session


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

    retPrompt = combinePrompt(Prompt.stillThere, extraPrompt)

    return dict(
        action="play",
        prompt=retPrompt,
        nextaction=nextaction,
        invalidaction=request.route_url('invalidmessage'),
        dtmf=dtmf,
        )

def combinePrompts(*p):
    retPrompt = []
    for i in p:
        if i:
            prompt = Prompt.getByName(name=i)
            j = prompt.getFullPrompt()
        for k in j:
            retPrompt.append(k)
    return retPrompt


@view_config(route_name='invalidmessage', renderer='json')
def invalidMessage(request):
    return returnPrompt(name=Prompt.invalidMessage)
