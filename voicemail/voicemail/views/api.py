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
    ReplyTo,
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
import inspect
from bag.web.pyramid.flash_msg import FlashMessage
import json
import requests

import smtplib
import os

# Here are the email package modules we'll need
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
COMMASPACE = ', '
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


def createReturnDict(request, 
        action=None,
        prompt=None,
        nextaction=None,
        invalidaction=None,
        dtmf=None,
        maxlength=None,
        folder=None
        ):
    pkey = request.GET.get('pkey')
    retdict = {}
    if pkey:
       retdict['pkey'] = pkey
    frame = inspect.currentframe()
    args, _, _, values = inspect.getargvalues(frame)
    for i in args:
        if i == "request":
            continue
        if values[i]:
            retdict[i] = values[i]
    log.debug("Returing %s", retdict)
    return retdict

@view_config(route_name='startcall', renderer='json')
def startCall(request):
    ''' This is the start of any call. Entry point'''

    extension = request.GET.get('user', None)
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    tree = request.GET.get('tree', None)
    pkey = request.GET.get('pkey', None)
    type = request.GET.get('type', None)


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
        user_session = getUserSession(callid, None)
        state = user_session.getCurrentState()
        if user.vm_prefs.tmp_greeting and user.vm_prefs.is_tmp_greeting_on:
            prompt = Prompt.userTmpGreeting
        elif user.vm_prefs.busy_greeting and type is not None and type == "busy":
            prompt = Prompt.userBusyGreeting
        elif user.vm_prefs.unavail_greeting and type is not None and type == "unavailable":
            prompt = Prompt.userUnavailGreeting
        elif user.vm_prefs.vm_greeting:
            prompt = Prompt.userGreeting
        elif user.vm_prefs.vm_name_recording is not None:
            prompt = Prompt.userNameRecording
        else:
            prompt = Prompt.userLeaveMessage

        state.action = "record"
        state.menu="leavemessage"
        state.step="0"
        state.nextaction = request.route_url(
                'savemessage',
                _query={'user':extension, 'uid':callid, 'callerid':callerid,
                        'callerid':callerid, 'menu':state.menu, 'step':state.step})
        state.invalidaction=request.route_url('invalidmessage')
        state.dtmf=['#', ]
        state.folder=user.vm_prefs.getVmFolder()
        user_session.saveState(state)
        DBSession.add(user_session)
        return createReturnDict(request,
            action=state.action,
            dtmf=state.dtmf,
            folder=state.folder,
            nextaction=state.nextaction,
            invalidaction=state.invalidaction,
            prompt=Prompt.getByName(name=prompt).getFullPrompt(user=user, param=user.extension)
        )
    elif tree == "loginMenu":
        prompt = Prompt.getByName(name=Prompt.loginWelcomeMessage)
        return createReturnDict(request,
            action="play",
            prompt=prompt.getFullPrompt(),
            nextaction=request.route_url(
                'handlelogin',
                _query={'menu': 'login', 'callerid':callerid, 'uid':callid}),
            invalidaction=request.route_url('invalidmessage'),
            dtmf=['!', '*7', '#'],
            maxlength = 6
        )

    elif tree == "accessMenu":
        return returnLoggedIn(request, user, callid, None)

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
            return createReturnDict(request,
                action="play",
                prompt=prompt.getFullPrompt(),
                nextaction=request.route_url(
                    'handlelogin',
                    _query={'callerid':callerid, 'uid':callid, 'cnt':count}),
                invalidaction=request.route_url('invalidmessage'),
                dtmf=['!', '*7', '#'],
                maxlength = 6
            )
        else:
            return createReturnDict(request,
                action="play",
                prompt=prompt.getFullPrompt(user=user),
                nextaction="agi:hangup",
            )
    elif extension is None: 
        prompt = Prompt.getByName(Prompt.loginInputPassword)
        return createReturnDict(request,
             action="play",
             prompt=prompt.getFullPrompt(),
             nextaction=request.route_url(
                 'handlelogin',
                 _query={'uid':callid, 'callerid':callerid, 'user':key}),
             invalidaction=request.route_url('invalidmessage'),
             dtmf=['!', '*7', '#'],
             maxlength = 6
         )
    else:
        log.debug("Checking username for a user %s password %s", extension, key)
        user = DBSession.query(User).filter_by(extension=extension, pin = key).first()
        if user is None:
            count = int(count) + 1
            if count < 3:
                prompt = Prompt.getByName(Prompt.loginInvalidPassword)
                return createReturnDict(request,
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    nextaction=request.route_url(
                        'handlelogin',
                        _query={'uid':callid, 'user':extension, 'callerid':callerid, 'cnt':count}),
                    invalidaction=request.route_url('invalidmessage'),
                    dtmf=['!', '*7', '#'],
                    maxlength = 6
                )
            else:
                prompt = Prompt.getByName(Prompt.loginInvalidPassword)
                return createReturnDict(request,
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    nextaction="agi:hangup",
                )
        else:
            return returnLoggedIn(request, user, callid, Prompt.loginLoggedIn)
        


@view_config(route_name='savemessage', renderer='json')
def saveMessage(request):
    extension = request.GET.get('user', None)
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    vmfile = request.GET.get('vmfile', None)
    duration = request.GET.get('duration', 0)
    menu = request.GET.get('menu', None)
    step = request.GET.get('step', None)
    key = request.GET.get('key', None)
    reason = request.GET.get('reason', None)

    if(not extension or not callid or not callerid):
        log.debug(
            "Invalid parameters extension %s callid %s callerid %s vmfile %s uid %s",
            extension, callid, callerid, vmfile, uid)
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug(
            "User Not Found extension %s callid %s callerid %s \
            vmfile %s duraiton %s",
            extension, callid, callerid, vmfile, duration)
        return retdict

    user_session = getUserSession(callid, None)
    state = user_session.getCurrentState()
    if not key or (key == "False" and reason != 'hangup'):
        return stillThereLoop(request, None, user_session)
    else:
        state.dtmf = None
        state.nextaction = None
        state.retryCount = 0

    prompt = None
    if key == "False" and reason == "hangup" and vmfile:
        deliverMessage(request, user, user.extension, callerid, vmfile, duration)
        return returnPrompt(name=Prompt.messageSaved)

    if step == "0":
        prompt = Prompt.getByName(name=Prompt.rsfMenuRecord).getFullPrompt()
        state.menu="leavemessage"
        state.step="1"
        state.dtmf=['1', '23', '*3', '#']
        _query={'user': extension, 'menu': state.menu, 'callerid': callerid, 'uid': callid, 'step': state.step, 'vmfile': vmfile, 'duration':duration}
        state.nextaction=request.route_url('savemessage', _query=_query)
        state.action="play"
    elif step == "1":
        if key == "1":
            prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow).getFullPrompt()
            state.action = "record"
            state.menu="leavemessage"
            state.step="0"
            state.nextaction = request.route_url(
                    'savemessage',
                    _query={'user':extension, 'uid':callid, 'callerid':callerid,
                            'callerid':callerid, 'menu':state.menu, 'step':state.step})
            state.invalidaction=request.route_url('invalidmessage')
            state.dtmf=['#', ]
            state.folder=user.vm_prefs.getVmFolder()
        elif key == "23":
            promptMsg = {'uri':vmfile, 'delayafter' : 10}
            prompt = combinePrompts(None, None, None, promptMsg, Prompt.rsfRecordStillThere)
            state.menu='leavemessage'
            state.step='1'
            _query={'user': extension, 'menu': state.menu, 'uid': callid, 'callerid':callerid, 'vmfile':vmfile, 'step': state.step, 'duration':duration}
            state.nextaction=request.route_url( 'savemessage', _query=_query)
            state.dtmf=['1', '23', '*3', '*7', '#']                
            state.action="play"
        elif key == "*3":
            return returnPrompt(name=Prompt.rsfMessageDeleted)
        elif key == "#":
            deliverMessage(request, user, None, callerid, vmfile, duration)
            return returnPrompt(name=Prompt.messageSaved)

    user_session.saveState(state)
    return createReturnDict(
        request,
        action=state.action,
        nextaction=state.nextaction,
        folder=state.folder,
        prompt=prompt,
        invalidaction=state.invalidaction,
        dtmf=state.dtmf,
        maxlength=state.maxlength
    )


@view_config(route_name='handlekey', renderer='json')
def handleKey(request):
    extension = request.GET.get('user', None)
    key = request.GET.get('key', None)
    vmid = request.GET.get('vmid', None)
    menu = request.GET.get('menu', None)
    callid = request.GET.get('uid', None)
    step = request.GET.get('step', None)
    duration = request.GET.get('duration', 0)
    msgtype = request.GET.get('type', 0)
    vmfile = request.GET.get('vmfile', None)
    log.debug(
        "HandleKey called with extension %s key %s vmid %s menu %s",
        extension, key, vmid, menu)
    if extension is None or menu is None \
            or callid is None:
        log.debug(
            "Invalid parameters callid %s extension %s key %s menu %s",
            callid, extension, key, menu)
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug("User Not Found extension %s", extension)
        return retdict
    user_session = getUserSession(callid, user)
    state = user_session.getCurrentState()
    if not key or key == "False":
        return stillThereLoop(request, user, user_session)
    else:
        state.dtmf = None
        state.nextaction = None
        state.retryCount = 0
        #user_session.saveState(state)

    state.invalidaction = request.route_url('invalidmessage')
    if key and key != "#":
        key = key.strip("#")

    # Handle GLOBAL keys - *7 return to main menu, *4 help
    prompt = None

    if key == "*7":
        prompt = Prompt.getByName(name=Prompt.activityMenu).getFullPrompt()
        state.menu = 'main'
        state.nextaction=request.route_url(
            'handlekey',
            _query={'user': extension, 'menu': state.menu, 'uid':callid})
        state.dtmf = ['1', '2', '3', '5', '7', '*4']
        state.action = "play"
    elif key == "*4":
        return returnHelpMenu(request=request, user=user)    
    elif menu == "main":
        if key == "1":
            prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow).getFullPrompt(user=user)
            state.menu = 'record'
            state.step = 'record'
            state.nextaction = request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'type':'send', 'step': state.step}
                )
            state.dtmf = ['#']
            state.action = "record"
            state.folder = user.vm_prefs.getVmFolder()
        elif key == "2":
            state.curmessage = 1
            state.mode = "Full"
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state, user_session=user_session)
        elif key == "3":
            prompt = Prompt.getByName(name=Prompt.personalGreeting).getFullPrompt()
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'personal', 'step': '0', 'uid':callid})
            state.dtmf=['1', '2', '3', '4']
            state.menu = 'personal'
            state.step=None
            state.action = "play"
        elif key == "5":
            prompt = Prompt.getByName(name=Prompt.personalOptions).getFullPrompt()
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'options', 'uid':callid})
            state.dtmf=['1', '3', '4', '6', '*4', '*7']
            state.menu = 'options'
            state.step = None
            state.action = "play"
        elif key == "7":
            state.curmessage = 1
            state.mode = "Header"
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state, user_session=user_session)
    elif menu == "personal":
        if step == "0":
            if key == "1":
                onOffPrompt = None
                if user.vm_prefs.is_tmp_greeting_on:
                    user.vm_prefs.is_tmp_greeting_on = 0
                    onOffPrompt = Prompt.offPrompt
                else:
                    user.vm_prefs.is_tmp_greeting_on = 1
                    onOffPrompt = Prompt.onPrompt
                DBSession.add(user)
                
                tmpGreetingStatus = Prompt.tmpGreetingStatus
                prompt = combinePrompts(user, None, None, tmpGreetingStatus, onOffPrompt, Prompt.activityMenu)
                state.menu ='main'
                state.step = None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.action="play"
            elif key == "2":
                return doPersonalGreeting(request, callid, user, menu, key, step=step, type="unavail", state=state, user_session=user_session) 
            elif key == "3":
                return doPersonalGreeting(request, callid, user, menu, key, step=step, type="busy", state=state, user_session=user_session) 
            elif key == "4":
                return doPersonalGreeting(request, callid, user, menu, key, step=step, type="tmp", state=state, user_session=user_session) 
        else:
            return doPersonalGreeting(request, callid, user, menu, key, step=step, type=msgtype, state=state, user_session=user_session) 
    elif menu == "record":
        if step == 'record':
            prompt = Prompt.getByName(name=Prompt.rsfMenuRecord).getFullPrompt(user=user)
            state.menu='record'
            state.step='approve'
            _query={'user': extension, 'menu': state.menu, 'uid': callid, 'step': state.step, 'type': msgtype, 'vmfile': vmfile}
            if vmid:
                _query['vmid'] = vmid
            state.nextaction=request.route_url( 'handlekey', _query=_query)
            state.dtmf=['1', '23', '*3', '#']                
            state.action="play"
        elif step == 'approve':
            if key == "1":
                prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow).getFullPrompt(user=user)
                state.menu='record'
                state.step='record'
                state.action="record"
                _query={'user': extension, 'menu': state.menu, 'uid': callid, 'step': state.step, 'type': msgtype}
                if vmid:
                    _query['vmid'] = vmid
                state.nextaction=request.route_url( 'handlekey', _query=_query)
                state.dtmf=['#']
                state.folder=user.vm_prefs.getVmFolder()
            elif key == "23":
                promptMsg = {'uri':vmfile, 'delayafter' : 10}
                prompt = combinePrompts(user, None, None, promptMsg, Prompt.rsfRecordStillThere)
                state.menu='record'
                state.step='approve'
                _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile, 'step': state.step, 'type': msgtype, 'vmfile': vmfile}
                if vmid:
                    _query['vmid'] = vmid
                state.nextaction=request.route_url( 'handlekey', _query=_query)
                state.dtmf=['1', '23', '*3', '*7', '#']                
                state.action="play"
            elif key == "*3":
                # TODO suspect next action here. Check this with Chris
                # Not deleting the file 
                # TODO to create a cron to delete
                prompt = Prompt.getByName(name=Prompt.rsfMessageDeleted).getFullPrompt(user=user)
                state.menu='record'
                state.step='approve'
                state.nextaction=request.route_url( 'handlekey', 
                        _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile, 'vmid':vmid, 'step': state.step, 'type': msgtype})
                state.dtmf=['1', '23', '*3', '*7', '#']                
            elif key == "#":
                promptFirst = Prompt.rsfApprovedMessage
                if msgtype == 'fwd' or msgtype == 'send':
                    promptSecond = Prompt.sendInputList
                    if msgtype == 'fwd':
                        promptSecond = Prompt.rsfCreateForward
                    prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                    state.menu = 'send'
                    state.step = 'input'
                    state.nextaction=request.route_url(
                        'handlekey',
                        _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile, 'step': state.step}
                    )
                    state.dtmf=['!', '*7', '#']
                    state.maxlength = 6
                    state.action="play"
                elif msgtype == 'reply' or msgtype == "replyWithout":
                    curvm = DBSession.query(Voicemail).filter_by(id=vmid).first()
                    deliverMessage(request, None, curvm.cid_number, user.extension, vmfile, duration, curvm, "attached" if msgtype == "reply" else None)

                    # TODO this should go back to playing the nxt message. Check with Chris
                    prompt = combinePrompts(user, None, None, Prompt.rsfDelivered, Prompt.activityMenu)
                    state.menu='main'
                    state.step = None
                    state.action = 'play'
                    state.nextaction=request.route_url(
                        'handlekey',
                        _query={'user':extension, 'menu':state.menu, 'uid':callid})
                    state.dtmf=['1', '2', '3', '5', '7', '*4']
    elif menu == "send":
        if key == '#':
            # done entering list
            if state.destlist and len(state.destlist):
                # process list - deliver messages
                for i in state.destlist:
                    deliverMessage(request, None, i, user.extension, vmfile, duration)
                      
                listcount = len(state.destlist)
                # TODO should the next step be play next message or go to main menu
                # TODO check with Chris
                prompt = combinePrompts(user, None, listcount, Prompt.sendApprovedCount, Prompt.activityMenu)
                state.menu='main'
                state.step = None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.action = "play"
            else:
                # drop back to list entry loop
                promptFirst = Prompt.sendInvalid
                promptSecond = Prompt.sendInputList
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.menu='send'
                state.step = None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile}
                )
                state.dtmf=['!', '*7', '#']
                state.maxlength = 6
                state.action="play"
        elif key == '0':
            # Cancel list entry
            promptFirst = Prompt.rsfCancelled
            promptSecond = Prompt.activityMenu
            prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
            state.menu='main'
            state.step=None
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': state.menu, 'uid':callid})
            state.dtmf=['1', '2', '3', '5', '7', '*4']
            state.destlist = None
            state.action="play"
            
        else:
            # determine if the entry matches a list or user
            newuser = DBSession.query(User).filter_by(extension=key).first()
            if not newuser:
                # requested value doesn't match a user or list
                promptFirst = Prompt.sendInvalid
                promptSecond = Prompt.sendStillThere
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.menu='send'
                state.step=None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile}
                )
                state.dtmf=['!', '*7', '#']
                state.maxlength = 6
                state.action="play"
            else:
                # entered value matches a user or list, add to / delete fromlist of entered destinations
                if state.destlist and key in state.destlist:
                    state.destlist.remove(key)
                    promptSecond = Prompt.sendRemoved
                else:
                    if not state.destlist:
                        state.destlist = []
                    state.destlist.append(key)
                    promptSecond = Prompt.sendAdded
                    
                state.menu='send'
                state.step=None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile}
                )
                state.dtmf=['!', '*7', '#']
                state.maxlength = 6
                promptFirst = Prompt.TTS  
                promptThird = Prompt.sendStillThere
                prompt = combinePrompts(user, None, key, promptFirst, promptSecond, promptThird)
                state.action="play"
    elif menu == "help":
        # TODO finish this part
        if key == "1":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "2":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "3":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "5":
            return returnPrompt(name=Prompt.invalidRequest)
        elif key == "7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == 'options':
        # Personal Options Menu - main menu selection 5
        if key == '1':
            # Administer mailing lists
            prompt = Prompt.getByName(name=Prompt.mailListMenu).getFullPrompt()
            state.menu = 'listadmin'
            state.step = 'start'
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
            state.dtmf=['0', '1', '*7', '*4']
            state.action="play"
        elif key == '3':
            # Change Password
            prompt = Prompt.getByName(name=Prompt.passwordNew).getFullPrompt()
            state.menu='password'
            state.step='firstpass'
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
            state.maxlength = 8
            state.dtmf=['!', '*7', '*4']
            state.action="play"
        elif key == '4':
            #Record name
            promptFirst = Prompt.recordNameIs
            namefile = user.vm_prefs.vm_name_recording
            promptSecond = None
            promptThird = None
            if not namefile:
                promptSecond = Prompt.greetingsNotSet
                promptThird = Prompt.mailListRecord
            else:
                promptSecond = {'uri':namefile, 'delayafter' : 10}
                promptThird = Prompt.mailListRecord

            prompt = combinePrompts(user, None, None, promptFirst, promptSecond, promptThird)
            state.menu = 'nameadmin'
            state.step = 'recordoptions'
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
            state.dtmf=['1', '23', '*3', '#', '7', '*4']
            state.action = "play"
        elif key == '6':
            # Toggle auto-login on/off
            # TODO - No idea what this is 
            # placeholder returns to main Menu
            prompt = Prompt.getByName(name=Prompt.activityMenu).getFullPrompt(user=user)
            state.menu='main'
            state.step=None
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': state.menu, 'uid':callid})
            state.dtmf=['1', '2', '3', '5', '7', '*4']
            state.action = "play"
    elif menu == 'listadmin':
        listid = request.GET.get('list', None)
        # Administer Lists
        if step == 'start':
            if key == '1':
                prompt = Prompt.getByName(name=Prompt.mailListName).getFullPrompt(user=user)
                state.menu = 'listadmin'
                state.step='recordname'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'step': state.step}
                )
                state.dtmf=['#']
                state.action = "record"
                state.folder=user.vm_prefs.getNameFolder()
            elif key == '0':
                # TODO - Play List Names - need flow mapped
                pass
        elif step == 'recordname':
            prompt = Prompt.getByName(name=Prompt.mailListRecord).getFullPrompt()
            state.menu = 'listadmin'
            state.step='approve'
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step, 'vmfile': vmfile})
            state.dtmf=['1', '23', '#', '*3', '*7', '*4']
            state.action = "play"
        elif step == 'approve':
            if key == '1':
                # re-record
                prompt = Prompt.getByName(name=Prompt.mailListName).getFullPrompt(user=user)
                state.menu = 'listadmin'
                state.step='recordname'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'step': state.step}
                )
                state.dtmf=['#']
                state.action="record"
                state.folder=user.vm_prefs.getNameFolder()
            elif key == '23':
                # play back recording
                promptMsg = {'uri':vmfile, 'delayafter' : 10}
                prompt = combinePrompts(user, None, None, promptMsg, Prompt.mailListRecord)
                state.menu = 'listadmin'
                state.step = 'approve'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmfile':vmfile, 'step': state.step}
                )
                state.dtmf=['1', '23', '#', '*3', '*7', '*4']                
                state.action = "play"
            elif key == '*3':
                # exit to top menu
                prompt = Prompt.getByName(name=Prompt.mailListMenu).getFullPrompt()
                state.menu = 'listadmin'
                state.step = 'start'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
                state.dtmf=['0', '1', '*7', '*4']
                user_session.saveState(state)
                state.action="play"
            elif key == '#':
                # approve recording, set passcode
                prompt = Prompt.getByName(name=Prompt.mailListCode).getFullPrompt()
                state.menu = 'listadmin'
                state.step = 'keycode'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step, 'vmfile':vmfile})
                state.maxlength = 6
                state.dtmf=['!', '#', '*7', '*4']
                state.action="play"
        elif step == 'keycode':
            # validate keycode - make sure it's available, if not send them back to get a new keycode
            user = DBSession.query(User).filter_by(extension=key).first()
            if not user:
                # we have an available list keycode, accept it
                prompt = Prompt.getByName(name=Prompt.mailListApprove).getFullPrompt()
                state.menu = 'listadmin'
                state.step = 'keycode'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step, 'keycode': key, 'vmfile':vmfile})
                state.dtmf=['0', '#', '*7', '*4']
                state.action="play"
            else:
                # invalid list keycode, try again.
                promptFirst = Prompt.mailListExists
                promptSecond = Prompt.mailListCode
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.menu = 'listadmin'
                state.step = 'keycode'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step, 'vmfile':vmfile})
                state.maxlength = 6
                state.dtmf=['!', '#', '*7', '*4']
                state.action="play"
        elif step == 'codeapprove':
            if key == '0':
                prompt = Prompt.getByName(name=Prompt.mailListMenu).getFullPrompt(user=user)
                state.menu = 'listadmin'
                state.step = 'start'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
                state.dtmf=['0', '1', '*7', '*4']
                state.action="play"
            elif key == '#':
                # TODO - save list & name
                # Create the list in the user table and save the name as the name 
                # in the vm_prefs
                # TODO where the hell do we allow people to be added to this list
                promptFirst = Prompt.messageSaved
                promptSecond = Prompt.personalOptions
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.menu = 'options'
                state.step = None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid})
                state.dtmf=['1', '3', '4', '6', '*4', '*7']
                state.action="play"
    elif menu == 'password':
        # Need to test this. I think this is done
        if step == 'firstpass':
            if len(key) < 4:
                prompt = Prompt.getByName(name=Prompt.passwordNew).getFullPrompt(user=user)
                state.menu = 'password'
                state.step = 'firstpass'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
                state.maxlength = 8
                state.dtmf=['!', '*7', '*4']
                state.action="play"
            else:
                prompt = Prompt.getByName(name=Prompt.passwordReEnter).getFullPrompt()
                state.password = key
                state.menu = 'password'
                state.step = 'secondpass'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
                state.maxlength = 8
                state.dtmf=['!', '*7', '*4']
                state.action="play"
        if step == 'secondpass':
            firstpass = state.password
            if key == firstpass:
                # Save the password in the db
                user.pin = key
                state.password = None
                state.menu = 'main'
                state.step = None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                DBSession.add(user)
                promptFirst = Prompt.passwordChanged
                promptSecond = Prompt.activityMenu
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.action="play"
            else:
                prompt = Prompt.getByName(name=Prompt.passwordReEnter).getFullPrompt(user=user)
                state.menu = 'password'
                state.step = 'secondpass'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
                state.maxlength = 8
                state.dtmf=['!', '*7', '*4']
                state.action="play"
    elif menu == 'nameadmin':
        # Change name Recording
        if step == 'recordoptions':
            if key =='1':
                prompt = Prompt.getByName(name=Prompt.recordName).getFullPrompt()
                state.menu = 'nameadmin'
                state.step = 'recordoptions'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'step':state.step}
                )
                state.dtmf=['#']
                state.action="record"
                state.folder=user.vm_prefs.getNameFolder() 
            elif key =='23':
                # handle both newly recorded and previously recorded names
                if vmfile:  #is there a new recording?
                    promptFirst = {'uri': vmfile, 'delayafter': 10}
                elif user.vm_prefs.vm_name_recording:
                    promptFirst = {'uri': user.vm_prefs.vm_name_recording, 'delayafter': 10}
                else:
                    promptFirst = Prompt.greetingsNotSet
                promptSecond = Prompt.mailListRecord
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.menu = 'nameadmin'
                state.step = 'recordoptions'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'vmfile': vmfile, 'step': state.step})
                state.dtmf=['1', '23', '*3', '#', '7', '*4']
                state.action="play"
            elif key == '*3':
                # delete current recording or previous recording
                if not vmfile and user.vm_prefs.vm_name_recording:   # TODO - Add to cron job
                    user.vm_prefs.vm_name_recording = None
                    DBSession.add(user.vm_prefs)
                promptFirst = Prompt.rsfMessageDeleted
                promptSecond = Prompt.recordNameIs
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.menu = 'nameadmin'
                state.step = 'recordoptions'
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid, 'step': state.step})
                state.dtmf=['*7', '*4']
                state.action="play"
            elif key == '#':
                if vmfile:
                    user.vm_prefs.vm_name_recording = vmfile
                    DBSession.add(user.vm_prefs)
                promptFirst = Prompt.messageSaved
                promptSecond = Prompt.activityMenu
                state.menu = 'main'
                state.step = None
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.action="play"
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
    elif menu == "vmaccess":
        if step == "fwdreply":
            if key == "2" or key == "7" or key == "19":
                prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow).getFullPrompt(user=user)
                if key == "2":
                    type = 'fwd'
                elif key == "7":
                    type = 'replyWithout'
                elif key == "19":
                    type = 'reply'
                state.menu = 'record'
                state.step = 'record'
                state.action="record"
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmid':vmid, 'type':type, 'step': state.step}
                )
                state.dtmf=['#']
                state.folder=user.vm_prefs.getVmFolder()
            elif key == "4":
                type = 'send'
                prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow).getFullPrompt(user=user)
                state.menu = 'record'
                state.step = 'record'
                state.nextaction = request.route_url(
                        'handlekey',
                        _query={'user': extension, 'menu': state.menu, 'uid': callid, 'type':send, 'step': state.step}
                    )
                state.dtmf = ['#']
                state.action = "record"
                state.folder = user.vm_prefs.getVmFolder()
        else:
            if key == "0":
                return getMessage(
                    request=request, menu="vmaccess", user=user, state=state, user_session=user_session, repeat=1)
            if key == "1":
                # TODO Need to figure the fwd/reply scenario
                # forward / reply to the message
                prompt = Prompt.getByName(name=Prompt.replyForwardMessage).getFullPrompt()
                state.menu = 'vmaccess'
                state.step = 'fwdreply'
                state.dtmf = ['2', '4', '7', '19',]
                state.action="play"
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': state.menu, 'uid': callid, 'vmid':vmid, 'step': state.step}
                )
            elif key == "*3":
                # delete the message
                v = DBSession.query(Voicemail).filter_by(id = vmid).first()
                if v.status == 0:
                    v.status = 1
                    v.deleted_on = datetime.datetime.utcnow()
                else:
                    v.status = 0
                    v.deleted_on = None
                DBSession.add(v)
                state.nextMessage()
                state.menu='vmaccess'
                state.step=None
                return getMessage(
                    request=request, menu="vmaccess", user=user, state=state, user_session=user_session)
            elif key == "#":
                # skip message
                v = DBSession.query(Voicemail).filter_by(id = vmid).first()
                v.is_read = 1
                v.read_on = datetime.datetime.utcnow()
                DBSession.add(v)
                state.nextMessage()
                state.menu='vmaccess'
                state.step=None
                return getMessage(
                    request=request, menu="vmaccess", user=user, state=state, user_session=user_session)
            elif key == "23":
                # play header
                state.mode = "Header"
                return getMessage(
                    request=request, menu="vmaccess", user=user, state=state, user_session=user_session, repeat=1, msgType="Header")
            elif key == "4":
                # rewind. Handled in asterisk
                return returnPrompt(name=Prompt.invalidRequest)
            elif key == "5":
                # toggle pause/play. Handled in asterisk
                return returnPrompt(name=Prompt.invalidRequest)
            elif key == "6":
                # advance . Handled in asterisk
                return returnPrompt(name=Prompt.invalidRequest)
            elif key == "44":
                state.previousMessage()
                state.menu='vmaccess'
                state.step=None
                return getMessage(
                    request=request, menu="vmaccess", user=user, state=state, user_session=user_session, repeat=1)
            else:
                log.debug(
                    "Invalid Input with extension %s key %s vmid %s menu %s",
                    extension, key, vmid, menu)
                return returnPrompt(name=Prompt.invalidRequest)
    if state.menu != "main":
        if "*7" not in state.dtmf:
            state.dtmf.append("*7")
    if "*4" not in state.dtmf:
        state.dtmf.append("*4")
    user_session.saveState(state)
    return createReturnDict(
        request,
        action=state.action,
        nextaction=state.nextaction,
        folder=state.folder,
        prompt=prompt,
        invalidaction=state.invalidaction,
        dtmf=state.dtmf,
        maxlength=state.maxlength
    )

    
def getMessage(request, menu, user, state=None, vmid=None,user_session=None, repeat=0, msgType=None):
    # Lets check if unread vms are there
    # if not then old messages
    # else no message
    v = None
    prompt = None
    log.debug(
        "Called getMessage with state %s %s %s %s" % \
            (state.unread, state.read, state.message_type, state.curmessage))

    msgToGet = None
    messagePrompt = None
    typePrompt = None
    if state.curmessage == 1:
        prompt = Prompt.firstMessage
        messagePrompt = Prompt.messagePrompt
    elif (state.message_type == "Unread" and state.curmessage == len(state.unread)) or \
         (state.message_type == "read" and state.curmessage == len(state.read)):
        prompt = Prompt.lastMessage
        messagePrompt = Prompt.messagePrompt
    else:
        prompt = Prompt.nextMessage

    if messagePrompt:
        if state.message_type == "Unread":
            typePrompt = Prompt.newPrompt
        else:
            typePrompt = Prompt.oldPrompt

    if state.message_type == "Unread" and state.curmessage <= len(state.unread): #unread messages
        msgToGet = state.unread[state.curmessage - 1]
    elif state.curmessage <= len(state.read):
        msgToGet = state.read[state.curmessage - 1]
    else:
        prompt = Prompt.noMoreMessage

    if repeat:
        prompt = None

    promptHeader = None
    promptVM = None
    if msgToGet:
        v = DBSession.query(Voicemail).filter_by(id=msgToGet).first()
        promptHeader = Prompt.vmMessageHeader
        promptVM = Prompt.vmMessage

    if msgType:
        promptType = msgType
    else:
        promptType = state.mode
    if promptType == "Header":
        promptVM = None
    elif promptType == "VM":
        promptHeader = None

    if v is not None:
        retPrompt = combinePrompts(user, v, state.curmessage, prompt, typePrompt, messagePrompt, promptHeader, promptVM, Prompt.postMessage)
        state.menu='vmaccess'
        state.step = None
        state.nextaction = request.route_url(
                'handlekey',
                _query={
                    'user':user.extension, 'menu': state.menu, 'vmid': v.id, 'uid':state.uid})
        state.dtmf=['0', '1', '*3', '#', '23', '4', '5', '6', '44', '*7', '*4']
        state.action = "play"
    else:
        state.reset()
        state.action = "play"
        state.menu = "main"
        state.nextaction=request.route_url(
                'handlekey',
                _query={'user':user.extension, 'menu':'main', 'uid':state.uid})
        state.dtmf=['1', '2', '3', '5', '7', '*7', '*4']
        retPrompt = combinePrompts(user, v, state.curmessage, prompt, Prompt.activityMenu)
    user_session.saveState(state)
    return createReturnDict(request,
        action=state.action,
        prompt=retPrompt,
        invalidaction=state.invalidaction,
        nextaction=state.nextaction,
        dtmf=state.dtmf,
    )


def returnHelpMenu(request=None, user=None):
    prompt = Prompt.getByName(name=Prompt.helpMenu)
    return createReturnDict(request,
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
        user_session.loadState(user, callid)
    return user_session


def stillThereLoop(request=None, user=None, user_session=None ):
    state = None
    if user_session:
        state = user_session.getCurrentState()
    if state and state.retryCount < 3:
        log.debug("StillThereloop called with state %d", state.retryCount)
        state.retryCount = state.retryCount + 1
        user_session.saveState(state=state)
    else:
        return returnPrompt(name=Prompt.goodbye)

    extraPrompt = None
    if state.menu is not None:
        if state.menu == "main":
            extraPrompt = Prompt.loginStillThere
        elif state.menu == "record":
            if state.step == "record":
                extraPrompt = Prompt.rsfRecordStillThere
            elif state.step == "approve":
                extraPrompt = Prompt.rsfForwardStillThere
            elif state.step == "reply":
                extraPrompt = Prompt.rsfForwardStillThere
            else:
                extraPrompt = None
        elif state.menu == "vmaccess":
            extraPrompt = Prompt.stillThereGetMessage
        elif state.menu == "personal":
            if state.step == "0":
                extraPrompt = Prompt.rsfForwardStillThere
            elif state.step == "1":
                extraPrompt = Prompt.rsfRecordStillThere
            else:
                extraPrompt = Prompt.personalStillThere
        elif state.menu == "send":
            if state.step == "input":
                extraPrompt = Prompt.sendStillThere
            elif state.step == "approve":
                extraPrompt = Prompt.rsfForwardStillThere
            else:
                extraPrompt = Prompt.sendStillThere
        elif state.menu == "listadmin":
            if state.step == "start":
                extraPrompt = Prompt.mailListMenuStillThere
            elif state.step == "firstpass":
                extraPrompt = Prompt.mailListMenuStillThere
            elif state.step == "recordname":
                extraPrompt = Prompt.mailListMenuStillThere
            elif state.step == "approve":
                extraPrompt = Prompt.mailListMenuStillThere
            elif state.step == "keycode":
                extraPrompt = Prompt.mailListMenuStillThere
            elif state.step == "codeapprove":
                extraPrompt = Prompt.mailListMenuStillThere
            else:
                extraPrompt = Prompt.mailListMenuStillThere
        elif state.menu == "nameadmin":
            extraPrompt = Prompt.rsfRecordStillThere
        elif state.menu == "options":
            extraPrompt = Prompt.personalGreetingStillThere
        elif state.menu == "password":
            if state.step == "firstpass":
                extraPrompt = None
            elif state.step == "secondpass":
                extraPrompt = None
            else:
                extraPrompt = None

    retPrompt = combinePrompts(user, None, None, Prompt.stillThere, extraPrompt)

    return createReturnDict(request,
        action=state.action,
        prompt=retPrompt,
        nextaction=state.nextaction,
        invalidaction=state.invalidaction,
        dtmf=state.dtmf,
        folder=state.folder,
        maxlength=state.maxlength
        )

def combinePrompts(user, vm, number, *p):
    retPrompt = []
    for i in p:
        if i:
            if type(i) != dict:
                prompt = Prompt.getByName(name=i)
                j = prompt.getFullPrompt(user=user, vm=vm, param=number)
            else:
                j = [i,]
            for k in j:
                retPrompt.append(k)
    return retPrompt


@view_config(route_name='invalidmessage', renderer='json')
def invalidMessage(request):
    return returnPrompt(name=Prompt.invalidMessage)


def doPersonalGreeting(request, callid, user, menu, key, step, type, state, user_session):
    firstPrompt = None
    promptName = Prompt.greetingsNotSet
    secondPrompt = Prompt.greetingsRecordMenu

    extension = user.extension
    vmfile = request.GET.get('vmfile', None)
    if type == "unavail":
        firstPrompt = Prompt.greetingsUnavailIs
        if user.vm_prefs.unavail_greeting:
            promptName = Prompt.userUnavailGreeting
        else:
            secondPrompt = Prompt.greetingsRecordUnavail
    elif type == "busy":
        firstPrompt = Prompt.greetingsBusyIs
        if user.vm_prefs.busy_greeting:
            promptName = Prompt.userBusyGreeting
        else:
            secondPrompt = Prompt.greetingsRecordBusy
    elif type == "tmp":
        firstPrompt = Prompt.greetingsTmpIs
        if user.vm_prefs.tmp_greeting:
            promptName = Prompt.userTmpGreeting
        else:
            secondPrompt = Prompt.greetingsRecordTmp
    
    retPrompt = None
    state.invalidaction=request.route_url('invalidmessage')
    if step == '0':
        retPrompt = combinePrompts(user, None, None, firstPrompt, promptName, secondPrompt)
        state.menu='personal'
        state.step ='1'
        state.nextaction=request.route_url(
            'handlekey',
            _query={'user': extension, 'type':type, 'menu': state.menu, 'uid':callid, 'step':state.step})
        state.dtmf=['1', '23', '#', '*7', '*4']
        state.action="record"
        state.folder=user.vm_prefs.getGreetingFolder()
    elif step == '1':
        if key == '1':
            retPrompt = Prompt.getByName(Prompt.greetingsRecordMenu).getFullPrompt(user=user)
            state.action="record"
            state.menu='personal'
            state.step='1'
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'uid':callid,
                            'type':type, 'menu':state.menu, 'step':state.step})
            state.dtmf=['1', '23', '#','*7', '*4' ]
            state.folder=user.vm_prefs.getGreetingFolder()
        elif key == '23':
            retPrompt =  {'uri':vmfile, 'delayafter':10}
            state.action="play"
            state.menu='personal'
            state.step='1'
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'uid':callid,'vmfile':vmfile,
                            'type':type, 'menu':state.menu, 'step':state.step})
            state.dtmf=['1', '23', '#', '*7', '*4']
        elif key == '#':
            if type == "unavail":
                user.vm_prefs.unavail_greeting = vmfile
            elif type == "busy":
                user.vm_prefs.busy_greeting = vmfile
            elif type == "tmp":
                user.vm_prefs.tmp_greeting = vmfile
            DBSession.add(user.vm_prefs)
            retPrompt = combinePrompts(user, None, None, Prompt.greetingsApproved, Prompt.activityMenu)
            state.action="play"
            state.menu='main'
            state.step=None
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'menu':state.menu, 'uid':callid})
            state.dtmf=['1', '2', '3', '5', '7', '*4']
    user_session.saveState(state)
    return createReturnDict(request,
        action=state.action,
        prompt=retPrompt,
        nextaction=state.nextaction,
        dtmf=state.dtmf,
        folder=state.folder,
        invalidaction=state.invalidaction
    )

def deliverMessage(request, user, extension, cid_number, vmfile, duration, vm=None, attached=None):
    tuser = user
    if not tuser:
        tuser = DBSession.query(User).filter_by(extension=extension).first()
    email_with_attachment = []
    email_message = []
    sms_message = []
    subject = "New Voicemail"
    time_message = datetime.datetime.utcnow()
    preamble = 'Voicemail received from %s on %s duration %s seconds' % (cid_number, time_message, duration)
    smtphost = request.registry.settings['smtp_host']
    mail_from = request.registry.settings['mail_from']
    file = vmfile[6:] # remove file:/
    if tuser and tuser.is_list:
        for j in tuser.members:
            vuser = DBSession.query(User).filter_by(extension=j).first() 
            v = Voicemail()
            v.cid_number = cid_number
            v.path = vmfile
            v.create_date = time_message
            v.is_read = False
            v.status = 0
            v.duration = duration
            v.user = vuser
            if vuser.vm_prefs.deliver_vm == 1:
                if vuser.vm_prefs.email:
                    if vuser.vm_prefs.attach_vm == 1:
                        email_with_attachement.append(vuser.vm_prefs.email)
                    else:
                        email_message.append(vuser.vm_prefs.email)
                if vuser_vm_prefs.sms_addr:
                    sms_message.append(vuser.vm_prefs.email)
            if vm:
                reply_to = ReplyTo()
                reply_to.parentVoicemail = vm
                reply_to.is_attached = False
                if attached == "attached":
                    reply_to.is_attached = True
                v.reply_to = reply_to
            DBSession.add(v)
            DBSession.flush()
            DBSession.refresh(vuser)
            postMWI(request, vuser)
    else:
        v = Voicemail()
        v.cid_number = cid_number
        v.path = vmfile
        v.create_date = time_message
        v.is_read = False
        v.status = 0
        v.duration = duration
        v.user = tuser
        if tuser.vm_prefs.deliver_vm == 1:
            if tuser.vm_prefs.email:
                if tuser.vm_prefs.attach_vm == 1:
                    email_with_attachement.append(tuser.vm_prefs.email)
                else:
                    email_message.append(tuser.vm_prefs.email)
            if tuser_vm_prefs.sms_addr:
                sms_message.append(tuser.vm_prefs.email)
        if vm:
            reply_to = ReplyTo()
            reply_to.parentVoicemail = vm
            reply_to.is_attached = False
            if attached == "attached":
                reply_to.is_attached = True
            v.reply_to = reply_to
        DBSession.add(v)
        DBSession.flush()
        DBSession.refresh(tuser)
        postMWI(request, tuser)
    if len(email_message) != 0:
        sendEmail(request, subject, mail_from, email_message, None, preamble, smtphost)
    if len(email_with_attachment) != 0:
        sendEmail(request, subject, mail_from, email_with_attachment, file, preamble, smtphost)
    if len(sms_message) != 0:
        sendEmail(request, subject, mail_from, sms_message, None, preamble, smtphost)



def postMWI(request, user):
    unread = 0
    read = 0
    for i in user.voicemails:
        if i.is_read:
            read = read + 1
        else:
            unread = unread + 1

    data = {'user':user.extension, 'new':unread, 'old':read} 
    pdata = json.dumps(data)
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    url = request.registry.settings['mwi.url']
    try:
        r = requests.post(url, data=pdata, headers=headers)
        if r.status_code != 200:
            log.debug("Error in posting MWI to %s: %s %s", url, pdata, headers)
    except Exception , e:
        log.exception("Could not post to MWI")


def returnLoggedIn(request, user, callid, promptBefore):
    user_session = getUserSession(callid, user)
    log.debug("UserSession created for a user Session %s" % user_session)
    onOffPrompt = None
    if user.vm_prefs.tmp_greeting and user.vm_prefs.is_tmp_greeting_on:
        onOffPrompt = Prompt.onPrompt
    else:
        onOffPrompt = Prompt.offPrompt
        
    retPrompt = combinePrompts(
        user, None, None, Prompt.loginLoggedIn,
        onOffPrompt, Prompt.vmSummary, Prompt.activityMenu)
    state = user_session.getCurrentState()
    state.menu = "main"
    state.nextaction=request.route_url(
            'handlekey',
            _query={'user':user.extension, 'menu':'main', 'uid':callid})
    state.dtmf=['1', '2', '3', '5', '7', '*4']
    state.action = "play"
    user_session.saveState(state)
    return createReturnDict(request,
        action=state.action,
        prompt=retPrompt,
        invalidaction=request.route_url('invalidmessage'),
        nextaction=state.nextaction,
        dtmf=state.dtmf
        )

def sendEmail(request, subject, mail_from, list_of_recipients, file, preamble, smtphost):
    # Create the container (outer) email message.
    msg = MIMEMultipart()
    msg['Subject'] = subject
    me = mail_from
    # family = the list of all recipients' email addresses
    family = list_of_recipients
    msg['From'] = me
    msg['BCC'] = COMMASPACE.join(family)
    msg.preamble = preamble
    if file:
        # Open the files in binary mode.  Let the MIMEAudio class automatically
        # guess the specific audio type.
        fp = open(file, 'rb')
        wav = MIMEAudio(fp.read())
        fp.close()
        wav.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file))
        msg.attach(wav)

    # Send the email via our own SMTP server.
    s = smtplib.SMTP(smtphost)
    s.sendmail(me, family, msg.as_string())
    s.quit()

