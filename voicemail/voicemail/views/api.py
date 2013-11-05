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
            folder=user.vm_prefs.getVmFolder(),
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
        user_session = getUserSession(callid, user)
        log.debug("UserSession created for a user Session %s" % user_session)
            
        # TODO add temporary greeting stuff
        retPrompt = combinePrompts(
            user, None, None, Prompt.loginLoggedIn,
            Prompt.vmSummary, Prompt.activityMenu)
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
    duration = request.GET.get('duration', 0)

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
    step = request.GET.get('step', '0')
    duration = request.GET.get('duration', 0)
    msgtype = request.GET.get('type', 0)
    log.debug(
        "HandleKey called with extension %s key %s vmid %s menu %s",
        extension, key, vmid, menu)
    if extension is None or (key is None and vmid is None) or menu is None \
            or callid is None:
        log.debug(
            "Invalid parameters extension %s key %s menu %s",
            extension, key, menu)
        return returnPrompt(name=Prompt.invalidRequest)

    user = DBSession.query(User).filter_by(extension=extension).first()
    success, retdict = userCheck(user)
    if not success:
        log.debug("User Not Found extension %s", extension)
        return retdict
    user_session = getUserSession(callid, user)
    state = user_session.getCurrentState()
    if not key:
        return stillThereLoop(request, user, user_session)
    else:
        state.dtmf = None
        state.nextaction = None
        state.retryCount = 0
        user_session.saveState(state)

    if key and key != "#":
        key = key.strip("#")

    # Handle GLOBAL keys - *7 return to main menu, *4 help
    if key == "*7":
        prompt = Prompt.getByName(name=Prompt.activityMenu)
        state.nextaction=request.route_url(
            'handlekey',
            _query={'user': extension, 'menu': 'main', 'uid':callid})
        state.dtmf = ['1', '2', '3', '5', '7', '*4']
        state.menu = 'main'
        user_session.saveState(state)
        return dict(
            action="play",
            prompt=prompt.getFullPrompt(),
            nextaction=state.nextaction,
            invalidaction=request.route_url('invalidmessage'),
            dtmf = state.dtmf
        )
    elif key == "*4":
        return returnHelpMenu(request=request, user=user)    
    elif menu == "main":
        if key == "1":
            prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow)
            state.nextaction = request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'type':'send', 'step': 'record'}
                )
            state.dtmf = ['#']
            state.menu = 'record'
            state.step = 'record'
            user_session.saveState(state)
            return dict(
                action="record",
                prompt=prompt.getFullPrompt(user=user),
                nextaction=state.nextaction,
                invalidaction=request.route_url('invalidmessage'),
                dtmf=state.dtmf,
                folder=user.vm_prefs.getVmFolder(),
                )
        elif key == "2":
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state, user_session=user_session)
        elif key == "3":
            prompt = Prompt.getByName(name=Prompt.personalGreeting)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'personal', 'uid':callid})
            state.dtmf=['1', '2', '3', '4']
            state.menu = 'personal'
            state.step=None
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf
            )
        elif key == "5":
            prompt = Prompt.getByName(name=Prompt.personalOptions)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'options', 'uid':callid})
            state.dtmf=['1', '3', '4', '6', '*4', '*7']
            state.menu = 'options'
            state.step = None
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf
            )
        elif key == "7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == "personal":
        if key == "1":
            if user.vm_prefs.is_tmp_greeting_on:
                user.vm_prefs.is_tmp_greeting_on = 0
            else:
                user.vm_prefs.is_tmp_greeting_on = 1
            DBSession.add(user)
            ### TODO 
            # toggled personal greeting
            # figure out the prompt to return for confirmation
            # returning them to the previous menu
            prompt = Prompt.getByName(name=Prompt.activityMenu)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'main', 'uid':callid})
            state.dtmf=['1', '2', '3', '5', '7', '*4']
            state.menu ='main'
            state.step = None
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf
            )
        elif key == "2":
            return doPersonalGreeting(request, callid, user, menu, key, step=step, type="unavail", state=state, user_session=user_session) 
        elif key == "3":
            return doPersonalGreeting(request, callid, user, menu, key, step=step, type="busy", state=state, user_session=user_session) 
        elif key == "4":
            return doPersonalGreeting(request, callid, user, menu, key, step=step, type="tmp", state=state, user_session=user_session) 
    elif menu == "record":
        if step == 'record':
            #TODO Check this duration condition.
            #seems like this should be if vmfile is not there
            #also it shouldn't play the still there loop here should be 
            #something different
            if not duration:
                # do still there loop
                return stillThereLoop( request=request, user=user, user_session=user_session)
            else:
                # we have a recorded message, play instruction for handling the recording
                prompt = Prompt.getByName(name=Prompt.rsfMenuRecord)
                _query = None
                if vmid:
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'step': 'approve', 'msgtype': msgtype, 'vmid':vmid}
                else:
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'step': 'approve', 'msgtype': msgtype}

                state.nextaction=request.route_url( 'handlekey', _query=_query)
                state.dtmf=['1', '23', '*3', '#']                
                state.menu='record'
                state.step='approve'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(user=user),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf
                )
        elif step == 'approve':
            if key == "1":
                prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow)
                _query = None
                if vmid:
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'step': 'record', 'msgtype': msgtype, 'vmid':vmid}
                else:
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'step': 'record', 'msgtype': msgtype}
                state.nextaction=request.route_url( 'handlekey', _query=_query)
                state.dtmf=['#']
                state.menu='record'
                state.step='record'
                user_session.saveState(state)
                return dict(
                    action="record",
                    prompt=prompt.getFullPrompt(user=user),
                    invalidaction=request.route_url('invalidmessage'),
                    folder=user.vm_prefs.getVmFolder(),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf
                    )
            elif key == "23":
                vmfile = request.get('vmfile', None)
                promptMsg = {'uri':vmfile, 'delayafter' : 10}
                prompt = combinePrompts(user, None, None, promptMsg, Prompt.rsfRecordStillThere)
                _query = None
                if vmid:
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'vmfile':vmfile, 'step': 'approve', 'msgtype': msgtype, 'vmid':vmid}
                else:
                    _query={'user': extension, 'menu': 'record', 'uid': callid, 'vmfile':vmfile, 'step': 'approve', 'msgtype': msgtype}
                state.nextaction=request.route_url( 'handlekey', _query=_query)
                state.dtmf=['1', '23', '*3', '*7', '#']                
                state.menu='record'
                state.step='approve'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf
                )
            elif key == "*3":
                # TODO suspect next action here. Check this with Chris
                # Not deleting the file 
                # TODO to create a cron to delete
                prompt = Prompt.getByName(name=Prompt.rsfMessageDeleted)
                state.nextaction=request.route_url( 'handlekey', 
                        _query={'user': extension, 'menu': 'record', 'uid': callid, 'vmfile':vmfile, 'vmid':vmid, 'step': 'approve', 'msgtype': msgtype})
                state.dtmf=['1', '23', '*3', '*7', '#']                
                state.menu='record'
                state.step='approve'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(user=user),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf
                    )
            elif key == "#":
                promptFirst = Prompt.getByName(name=Prompt.rsfApprovedMessage)
                if msgtype == 'fwd' or msgtype == 'send':
                    promptSecond = Prompt.getByName(name=Prompt.sendInputList)
                    prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                    state.nextaction=request.route_url(
                        'handlekey',
                        _query={'user': extension, 'menu': 'send', 'uid': callid, 'vmfile':vmfile, 'step': 'input'}
                    )
                    state.dtmf=['!', '*7', '#']
                    state.maxkeylength = 6
                    state.menu = 'send'
                    state.step = 'input'
                    user_session.saveState(state)
                    return dict(
                        action="play",
                        prompt=prompt,
                        invalidaction=request.route_url('invalidmessage'),
                        nextaction=state.nextaction,
                        dtmf=state.dtmf,
                        maxlength=state.maxlength
                    )                    
                elif msgtype == 'reply':
                    promptSecond = Prompt.getByName(name=Prompt.rsfCreateForward)
                    prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                    state.nextaction=request.route_url(
                        'handlekey',
                        _query={'user': extension, 'menu': 'record', 'uid': callid, 'vmfile':vmfile, 'vmid':vmid, 'step': 'reply', 'msgtype': msgtype}
                    )
                    state.dtmf=['0', '*7', '#']
                    state.menu = 'record'
                    state.step = 'reply'
                    user_session.saveState(state)
                    return dict(
                        action="play",
                        prompt=prompt,
                        invalidaction=request.route_url('invalidmessage'),
                        nextaction=state.nextaction,
                        dtmf=state.dtmf
                        )
        elif step == 'reply':
            if key == '0':
                #
                # TODO - Delete cron job
                prompt = combinePrompts(user, None, None, Prompt.rsfCancelled, Prompt.activityMenu)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'menu':'main', 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.menu='main'
                state.step=None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf
                )
            elif key == '#':
                curvm = DBSession.query(Voicemail).filter_by(id=vmid).first()
                # Deliver the reply to the user who send it to us
                tuser = DBSession.query(User).filter_by(extension=curvm.cid_number).first()
                if tuser:
                    v = Voicemail()
                    v.cid_number = user.extension
                    v.path = vmfile
                    v.create_date = datetime.datetime.utcnow()
                    v.is_read = False
                    v.status = 0
                    v.duration = duration
                    v.user = tuser
                    v.reply_to = curvm

                    DBSession.add(v)
                    # TODO call the asterisk stuff here fo indicator change
                        
                # TODO this should go back to playing the nxt message. Check with Chris
                prompt = combinePrompts(user, None, None, Prompt.rsfDelivered, Prompt.activityMenu)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'menu':'main', 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.menu='main'
                state.step = None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
    elif menu == "send":
        if key == '#':
            # done entering list
            if len(state.destlist):
                # process list - deliver messages
                for i in state.destlist:
                    tuser = DBSession.query(User).filter_by(extension=i).first()
                    if tuser and tuser.is_list:
                        for j in tuser.members:
                            vuser = DBSession.query(User).filter_by(extension=j).first() 
                            v = Voicemail()
                            v.cid_number = user.extension
                            v.path = vmfile
                            v.create_date = datetime.datetime.utcnow()
                            v.is_read = False
                            v.status = 0
                            v.duration = duration
                            v.user = vuser
                            DBSession.add(v)
                    # TODO call the asterisk stuff here fo indicator change
                    else:
                        v = Voicemail()
                        v.cid_number = user.extension
                        v.path = vmfile
                        v.create_date = datetime.datetime.utcnow()
                        v.is_read = False
                        v.status = 0
                        v.duration = duration
                        v.user = tuser
                        DBSession.add(v)
                        # TODO call the asterisk stuff here fo indicator change
                      
                listcount = len(state.destlist)
                # TODO should the next step be play next message or go to main menu
                # TODO check with Chris
                prompt = Prompt.getByName(name=Prompt.sendApprovedCount)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'main', 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.menu='main'
                state.step = None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(param=listcount),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf
                )                                       
            else:
                # drop back to list entry loop
                promptFirst = Prompt.getByName(name=Prompt.sendInvalid)
                promptSecond = Prompt.getByName(name=Prompt.sendInputList)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'send', 'uid': callid, 'vmfile':vmfile}
                )
                state.dtmf=['!', '*7', '#']
                state.maxkeylength = 6
                state.menu='send'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )
        elif key == '0':
            # Cancel list entry
            promptFirst = Prompt.getByName(name=Prompt.rsfCancelled)
            promptSecond = Prompt.getByName(name=Prompt.activityMenu)
            prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'main', 'uid':callid}),
            state.dtmf=['1', '2', '3', '5', '7', '*4']
            state.destlist = None
            state.menu='main'
            state.step=None
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt,
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf
            )
            
        else:
            # determine if the entry matches a list or user
            newuser = DBSession.query(User).filter_by(extension=key).first()
            if not newuser:
                # requested value doesn't match a user or list
                promptFirst = Prompt.getByName(name=Prompt.sendInvalid)
                promptSecond = Prompt.getByName(name=Prompt.sendStillThere)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'send', 'uid': callid, 'vmfile':vmfile}
                ),
                state.dtmf=['!', '*7', '#'],
                state.maxkeylength = 6
                state.menu='send'
                state.step=None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )
            else:
                # entered value matches a user or list, add to / delete fromlist of entered destinations
                if state.destlist and key in state.destlist:
                    state.destlist.remove(key)
                    promptSecond = Promtp.getByName(name=Prompt.sendRemoved)
                else:
                    if not state.destlist:
                        state.destlist = []
                    state.destlist.append(key)
                    promptSecond = Prompt.getByName(name=Prompt.sendAdded)
                    
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'send', 'uid': callid, 'vmfile':vmfile}
                ),
                state.dtmf=['!', '*7', '#'],
                state.maxkeylength = 6
                state.menu='send'
                state.step=None
                user_session.saveState(state)
                promptFirst = prompt.TTS  
                promptThird = Prompt.getByName(name=Prompt.sendStillThere)
                prompt = combinePrompts(user, None, key, promptFirst, promptSecond, promptThird)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )                    
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
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'main', 'uid':callid}),
            state.dtmf=['1', '2', '3', '5', '7', '*4'],
            state.menu='main'
            state.step=None
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(user=user),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtfm=state.dtmf
            )
        elif key == "7":
            return returnPrompt(name=Prompt.invalidRequest)
    elif menu == 'options':
        # Personal Options Menu - main menu selection 5
        if key == '1':
            # Administer mailing lists
            prompt = Prompt.getByName(name=Prompt.mailListMenu)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'start'})
            state.dtmf=['0', '1', '*7', '*4']
            state.menu = 'listadmin'
            state.step = 'start'
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf
            )            
        elif key == '3':
            # Change Password
            prompt = Prompt.getByName(name=Prompt.passwordNew)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'password', 'uid':callid, 'step': 'firstpass'})
            state.maxkeylength = 8
            state.dtmf=['!', '*7', '*4']
            state.menu='password'
            state.step='firstpass'
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf,
                maxlength=state.maxlength
            )
        elif key == '4':
            #Record name
            promptFirst = Prompt.getByName(name=Prompt.recordNameIs)
            namefile = user.vm_prefs.vm_name_recording
            promptSecond = None
            promptThird = None
            if not namefile:
                promptSecond = Prompt.getByName(name=Prompt.greetingsNotSet)
                promptThird = Prompt.getByName(name=Prompt.mailListRecord)
            else:
                promptSecond = {'uri':namefile, 'delayafter' : 10}
                promptThird = promptSecond = Prompt.getByName(name=Prompt.mailListRecord)

            prompt = combinePrompts(user, None, None, promptFirst, promptSecond, promptThird)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'nameadmin', 'uid':callid, 'step': 'recordoptions'})
            state.dtmf=['1', '23', '*3', '#', '7', '*4']
            state.menu = 'nameadmin'
            state.step = 'recordoptions'
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt,
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf,
            )
        elif key == '6':
            # Toggle auto-login on/off
            # TODO - No idea what this is 
            # placeholder returns to main Menu
            prompt = Prompt.getByName(name=Prompt.activityMenu)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'main', 'uid':callid}),
            state.dtmf=['1', '2', '3', '5', '7', '*4']
            state.menu='main'
            state.step=None
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf,
            )
    elif menu == 'listadmin':
        listid = request.GET.get('list', None)
        vmfile = request.GET.get('vmfile', None)
        # Administer Lists
        if step == 'start':
            if key == '1':
                prompt = Prompt.getByName(name=Prompt.mailListName)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid': callid, 'step': 'recordname'}
                )
                state.dtmf=['#']
                state.menu = 'listadmin'
                state.step='recordname'
                user_session.saveState(state)
                return dict(
                    action="record",
                    prompt=prompt.getFullPrompt(user=user),
                    invalidaction=request.route_url('invalidmessage'),
                    folder=user.vm_prefs.getNameFolder(),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    )
            elif key == '0':
                # TODO - Play List Names - need flow mapped
                pass
        elif step == 'recordname':
            # TODO - check recording duration - re-record if not there
            prompt = Prompt.getByName(name=Prompt.mailListRecord)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'approve', 'vmfile': vmfile}),
            state.dtmf=['1', '23', '#', '*3', '*7', '*4']
            state.menu = 'listadmin'
            state.step='approve'
            user_session.saveState(state)
            return dict(
                action="play",
                prompt=prompt.getFullPrompt(),
                invalidaction=request.route_url('invalidmessage'),
                nextaction=state.nextaction,
                dtmf=state.dtmf,
            )
        elif step == 'approve':
            if key == '1':
                # re-record
                prompt = Prompt.getByName(name=Prompt.mailListName)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid': callid, 'step': 'recordname'}
                )
                state.dtmf=['#']
                state.menu = 'listadmin'
                state.step='recordname'
                user_session.saveState(state)
                return dict(
                    action="record",
                    prompt=prompt.getFullPrompt(user=user),
                    invalidaction=request.route_url('invalidmessage'),
                    folder=user.vm_prefs.getNameFolder(),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            elif key == '23':
                # play back recording
                promptMsg = {'uri':vmfile, 'delayafter' : 10}
                prompt = combinePrompts(user, None, None, promptMsg, Prompt.mailListRecord)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid': callid, 'vmfile':vmfile, 'step': 'approve'}
                ),
                state.dtmf=['1', '23', '#', '*3', '*7', '*4']                
                state.menu = 'listadmin'
                state.step = 'approve'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            elif key == '*3':
                # exit to top menu
                prompt = Prompt.getByName(name=Prompt.mailListMenu)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'start'})
                state.dtmf=['0', '1', '*7', '*4']
                state.menu = 'listadmin'
                state.step = 'start'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            elif key == '#':
                # approve recording, set passcode
                prompt = Prompt.getByName(name=Prompt.mailListCode)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'keycode', 'vmfile':vmfile})
                state.maxkeylength = 6,
                state.dtmf=['!', '#', '*7', '*4']
                state.menu = 'listadmin'
                state.step = 'keycode'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )
        elif step == 'keycode':
            # validate keycode - make sure it's available, if not send them back to get a new keycode
            user = DBSession.query(User).filter_by(extension=key).first()
            if not user:
                # we have an available list keycode, accept it
                prompt = Prompt.getByName(name=Prompt.mailListApprove)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'codeapprove', 'keycode': key, 'vmfile':vmfile}),
                state.dtmf=['0', '#', '*7', '*4']
                state.menu = 'listadmin'
                state.step = 'keycode'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            else:
                # invalid list keycode, try again.
                promptFirst = Prompt.getByName(name=Prompt.mailListExists)
                promptSecond = Prompt.getByName(name=Prompt.mailListCode)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'keycode', 'vmfile':vmfile}),
                state.maxkeylength = 6,
                state.dtmf=['!', '#', '*7', '*4']
                state.menu = 'listadmin'
                state.step = 'keycode'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )                
        elif step == 'codeapprove':
            if key == '0':
                prompt = Prompt.getByName(name=Prompt.mailListMenu)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'listadmin', 'uid':callid, 'step': 'start'})
                state.dtmf=['0', '1', '*7', '*4']
                state.menu = 'listadmin'
                state.step = 'start'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            elif key == '#':
                # TODO - save list & name
                # Create the list in the user table and save the name as the name 
                # in the vm_prefs
                # TODO where the hell do we allow people to be added to this list
                promptFirst = Prompt.getByName(name=Prompt.messageSaved)
                promptSecond = Prompt.getByName(name=Prompt.personalOptions)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'options', 'uid':callid})
                state.dtmf=['1', '3', '4', '6', '*4', '*7']
                state.menu = 'options'
                state.step = None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
    elif menu == 'password':
        # Need to test this. I think this is done
        if step == 'firstpass':
            if len(key) < 4:
                prompt = Prompt.getByName(name=Prompt.passwordNew)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'password', 'uid':callid, 'step': 'firstpass'})
                state.maxkeylength = 8
                state.dtmf=['!', '*7', '*4']
                state.menu = 'password'
                state.step = 'firstpass'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )
            else:
                prompt = Prompt.getByName(name=Prompt.passwordReEnter)
                state.password = key
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'password', 'uid':callid, 'step': 'secondpass'}),
                state.maxkeylength = 8,
                state.dtmf=['!', '*7', '*4']
                state.menu = 'password'
                state.step = 'secondpass'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )            
        if step == 'secondpass':
            firstpass = state.password
            if key == firstpass:
                # Save the password in the db
                user.pin = key
                state.password = None
                DBSession.add(user)
                user_session.saveState(state)
                promptFirst = Prompt.getByName(name=Prompt.passwordChanged)
                promptSecond = Prompt.getByName(name=Prompt.activityMenu)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'main', 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.menu = 'main'
                state.step = None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            else:
                prompt = Prompt.getByName(name=Prompt.passwordReEnter)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'password', 'uid':callid, 'step': 'secondpass'})
                state.maxkeylength = 8
                state.dtmf=['!', '*7', '*4']
                state.menu = 'password'
                state.step = 'secondpass'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    maxlength=state.maxlength
                )
    elif menu == 'nameadmin':
        # Change name Recording
        if step == 'recordoptions':
            vmfile = request.GET.get('vmfile', None)
            if key =='1':
                prompt = Prompt.getByName(name=Prompt.recordName)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'nameadmin', 'uid': callid, 'step': 'recordname'}
                ),
                state.dtmf=['#'],
                state.menu = 'nameadmin'
                state.step = 'recordname'
                user_session.saveState(state)
                return dict(
                    action="record",
                    prompt=prompt.getFullPrompt(user=user),
                    invalidaction=request.route_url('invalidmessage'),
                    folder=user.vm_prefs.getNameFolder(),  
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                    )
            elif key =='23':
                # handle both newly recorded and previously recorded names
                if vmfile:  #is there a new recording?
                    promptFirst = {'uri': vmfile, 'delayafter': 10}
                elif user.vm_prefs.vm_name_recording:
                    promptFirst = {'uri': user.vm_prefs.vm_name_recording, 'delayafter': 10}
                else:
                    promptFirst = Prompt.getByName(name=Prompt.greetingsNotSet)
                promptSecond = Prompt.getByName(name=Prompt.mailListRecord)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'nameadmin', 'uid':callid, 'namefile': namefile, 'step': 'recordoptions'})
                state.dtmf=['1', '23', '*3', '#', '7', '*4']
                state.menu = 'nameadmin'
                state.step = 'recordoptions'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
            elif key == '*3':
                # delete current recording or previous recording
                if not vmfile and user.vm_prefs.vm_name_recording:   # TODO - Add to cron job
                    user.vm_prefs.vm_name_recording = None
                    DBSession.add(user.vm_prefs)
                promptFirst = Prompt.getByName(name=Prompt.rsfMessageDeleted)
                promptSecond = Prompt.getByName(name=Prompt.recordNameIs)
                prompt = combinePrompts(user, None, None, promptFirst, promptSecond)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'nameadmin', 'uid':callid, 'step': 'start'})
                state.dtmf=['*7', '*4']
                state.menu = 'nameadmin'
                state.step = 'start'
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt,
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )                
            elif key == '#':
                if vmfile:
                    user.vm_prefs.vm_name_recording = vmfile
                    DBSession.add(user.vm_prefs)
                promptFirst = Prompt.getByName(name=Prompt.messageSaved)
                promptSecond = Prompt.getByName(name=Prompt.activityMenu)
                state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user': extension, 'menu': 'main', 'uid':callid})
                state.dtmf=['1', '2', '3', '5', '7', '*4']
                state.menu = 'main'
                state.step = None
                user_session.saveState(state)
                return dict(
                    action="play",
                    prompt=prompt.getFullPrompt(),
                    invalidaction=request.route_url('invalidmessage'),
                    nextaction=state.nextaction,
                    dtmf=state.dtmf,
                )
        elif step == 'recordname':
            # TODO - handle post-recording 
            pass
    elif menu == 'scan':
        #TODO - Scan Messages
        pass
    elif menu == "vmaccess":
        log.debug(
            "HandleKey called with extension %s key %s vmid %s menu %s",
            extension, key, vmid, menu)
        if key == "0":
            # listen to the message
            # TODO what to do here?
            # I have no idea when this happens and what to do
            return returnPrompt(name=Prompt.invalidRequest)
        if key == "1":
            # forward / reply to the message
            prompt = Prompt.getByName(name=Prompt.rsfInputRecordNow)
            state.nextaction=request.route_url(
                'handlekey',
                _query={'user': extension, 'menu': 'record', 'uid': callid, 'vmid':vmid, 'type':'reply', 'step': 'record'}
            )
            state.dtmf=['#']
            state.menu = 'record'
            state.step = 'record'
            user_session.saveState(state)
            return dict(
                action="record",
                prompt=prompt.getFullPrompt(user=user),
                invalidaction=request.route_url('invalidmessage'),
                folder=user.vm_prefs.getVmFolder(),
                nextaction=state.nextaction,
                dtmf=state.dtmf,
                )
        elif key == "*3":
            # delete the message
            v = DBSession.query(Voicemail).filter_by(id = vmid).first()
            v.status = 1
            v.deleted_on = datetime.datetime.utcnow()
            DBSession.add(v)
            state.nextMessage()
            state.menu='vmaccess'
            state.step=None
            user_session.saveState(state=state)
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
            user_session.saveState(state=state)
            return getMessage(
                request=request, menu="vmaccess", user=user, state=state, user_session=user_session)
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
        else:
            log.debug(
                "Invalid Input with extension %s key %s vmid %s menu %s",
                extension, key, vmid, menu)
            return returnPrompt(name=Prompt.invalidRequest)
    return returnPrompt(name=Prompt.invalidRequest)

def scanmessages(request):
    extension = request.GET.get('user', None)
    key = request.GET.get('key', None)
    callid = request.GET.get('uid', None)
    callerid = request.GET.get('callerid', None)
    vmfile = request.GET.get('vmfile', None)
    duration = request.GET.get('duration', 0)
    source = request.GET.get('source', None)   
    # TODO - Finish this section
    
    
    
def getMessage(request, menu, user, state=None, vmid=None,user_session=None):
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
    retPrompt.extend(prompt.getFullPrompt(user=user, param=state.curmessage))
    prompt = Prompt.getByName(name=Prompt.vmMessage)
    p = prompt.getFullPrompt(user=user, vm=v, param=user.extension)
    for i in p:
        retPrompt.append(i)
    prompt = Prompt.getByName(name=Prompt.postMessage)
    p = prompt.getFullPrompt(user=user)
    for i in p:
        retPrompt.append(i)
    state.nextaction = request.route_url(
            'handlekey',
            _query={
                'user':user.extension, 'menu': 'vmaccess', 'vmid': v.id, 'uid':state.uid})
    state.dtmf=['0', '1', '*3', '#', '23', '4', '5', '6', '44']
    state.menu='vmaccess'
    state.step = None
    user_session.saveState(state)
    return dict(
        action="play",
        prompt=retPrompt,
        invalidaction=request.route_url('invalidmessage'),
        nextaction=state.nextaction,
        dtmf=state.dtmf,
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

    retPrompt = combinePrompt(user, None, None, Prompt.stillThere)

    return dict(
        action="play",
        prompt=retPrompt,
        nextaction=state.nextaction,
        invalidaction=request.route_url('invalidmessage'),
        dtmf=state.dtmf,
        )

def combinePrompts(user, vm, number, *p):
    retPrompt = []
    for i in p:
        if i:
            prompt = Prompt.getByName(name=i)
            j = prompt.getFullPrompt(user=user, vm=vm, param=number)
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
    action = None
    invalidaction=request.route_url('invalidmessage')
    folder = None
    if step == '0':
        retPrompt = combinePrompts(user, None, None, firstPrompt, promptName, secondPrompt)
        state.nextaction=request.route_url(
            'handlekey',
            _query={'user': extension, 'type':type, 'menu': 'personal', 'uid':callid, 'step':'1'})
        state.dtmf=['1', '23', '#']
        state.menu='personal'
        state.step ='1'
        action="play"
    elif step == '1':
        if key == '1':
            retPrompt = Prompt.getByName(Prompt.greetingsRecordMenu).getFullPrompt(user=user)
            action="record"
            folder=user.vm_prefs.getGreetingFolder()
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'uid':callid,
                            'type':type, 'menu':'personal', 'step':'2'})
            state.dtmf=['1', '23', '#', ]
            state.menu='personal'
            state.step='2'
        elif key == '23':
            retPrompt = combinePrompts(user, None, None, firstPrompt, promptName, secondPrompt)
            action="play"
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'uid':callid,
                            'type':type, 'menu':'personal', 'step':'1'})
            state.dtmf=['1', '23', '#' ]
            state.menu='personal'
            state.step='1'
            folder=user.vm_prefs.getGreetingFolder()
    elif step == '2':
        if key == '1':
            retPrompt = Prompt.getByName(Prompt.greetingsRecordMenu).getFullPrompt(user=user)
            action="record",
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'uid':callid,
                            'type':type, 'menu':'personal', 'step':'2'})
            state.dtmf=['1', '23', '#', ]
            folder=user.vm_prefs.getGreetingFolder()
            state.menu='personal'
            state.step='2'
        elif key == '23':
            file = request.get('file', None)
            retPrompt =  {'uri':file, 'delayafter':10}
            action="play"
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'uid':callid,'file':file,
                            'type':type, 'menu':'personal', 'step':'2'})
            state.dtmf=['1', '23', '#' ]
            state.menu='personal'
            state.step='2'
        elif key == '#':
            file = request.get('file', None)
            if type == "unavail":
                user.vm_prefs.unavail_greeting = file
            elif type == "busy":
                user.vm_prefs.busy_greeting = file
            elif type == "tmp":
                user.vm_prefs.tmp_greeting = file
            DBSession.add(user.vm_prefs)
            retPrompt = combinePrompts(user, None, None, Prompt.greetingsApproved, Prompt.activityMenu)
            action="play"
            state.nextaction=request.route_url(
                    'handlekey',
                    _query={'user':extension, 'menu':'main', 'uid':callid})
            state.dtmf=['1', '2', '3', '5', '7', '*4']
            state.menu='main'
            state.step=None
    user_session.saveState(state)
    return dict(
        action=action,
        prompt=retPrompt,
        nextaction=state.nextaction,
        dtmf=state.dtmf,
        folder=folder,
        invalidaction=invalidaction
    )
