from sqlalchemy import (
    Column,
    Integer,
    Text,
    String,
    DateTime,
    Unicode,
    Boolean,
    )

import datetime
import time
from sqlalchemy.orm import relationship, backref, mapper

from sqlalchemy.ext.associationproxy import association_proxy

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )
from sqlalchemy.schema import Table, ForeignKey

from zope.sqlalchemy import ZopeTransactionExtension

from pyramid.security import (
    Allow,
    Everyone,
    )

import json

import logging
log = logging.getLogger(__name__)


class RootFactory(object):
    __acl__ = [ (Allow, Everyone, 'user'),
                (Allow, 'g:admin', 'admin') ]
    def __init__(self, request):
        pass
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

user_groups = Table('user_groups', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', Integer, ForeignKey('groups.id')))

user_list = Table('user_list', Base.metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column("list_id", Integer, ForeignKey('users.id')),
      Column("user_id", Integer, ForeignKey('users.id')))

class UserList(object):
    pass

mapper(UserList, user_list)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Unicode(100), nullable=False, unique=True)
    name = Column(Unicode(80), nullable=False)
    extension = Column(String(10), nullable=False, unique=True)
    pin = Column(String(10), nullable=False, unique=True)
    create_date = Column(DateTime, nullable=False, default=datetime.datetime.utcnow )
    last_login = Column(DateTime)
    status = Column(Integer, nullable=False)
    is_list = Column(Boolean, default=False)

    voicemails = relationship("Voicemail", backref='user', cascade="all, delete, delete-orphan", 
        order_by="(desc(Voicemail.is_read), desc(Voicemail.create_date))")
    role = relationship("UserRole", backref='users')
    vm_prefs = relationship("UserVmPref", uselist=False, backref='user')

    members = relationship("User", secondary=user_list,
              primaryjoin=id==user_list.c.list_id,
              secondaryjoin=id==user_list.c.user_id,
              backref="lists")

    unreadCount = 0
    readCount = 0


    def __init__(self, username, name, extension, pin, status):
        self.username = username
        self.name = name
        self.extension = extension
        self.pin = pin
        self.status = status

    def getReadCount(self):
        readCount = 0
        for i in self.voicemails:
            if i.is_read: 
                readCount = readCount + 1
        return readCount

    def getUnreadCount(self):
        unreadCount = 0
        for i in self.voicemails:
            if not i.is_read: 
                unreadCount = unreadCount + 1
        return unreadCount

class UserRole(Base):
    __tablename__ = 'user_roles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(Unicode(20), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))


    def __init__(self, name, user_id):
        self.role_name = name
        self.user_id = user_id


class Voicemail(Base):
    __tablename__ = 'voicemails'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    duration = Column(Integer)
    create_date = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    path = Column(String(256))
    is_read = Column(Boolean)
    status = Column(Integer)
    deleted_on = Column(DateTime)
    read_on = Column(DateTime)
    cid_name = Column(String(80))
    cid_number = Column(String(20))
    reply_id = Column(Integer, ForeignKey('reply_to.id'))

    reply_to = relationship("ReplyTo", foreign_keys=reply_id, uselist=False)

    def __init__(self, path = None, cid_name = None, cid_number = None, duration = 0, user = None, create_date = None, is_read = False, status = 0):
        self.path = path
        self.cid_name = cid_name
        self.cid_number = cid_number
        self.duration = duration
        self.user = user
        self.create_date = create_date
        self.is_read = is_read
        self.status = status

class UserVmPref(Base):
    __tablename__ = 'user_vm_prefs'
    id = Column(Integer, primary_key = True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    folder = Column(String(100))
    deliver_vm = Column(Boolean, nullable=False)
    attach_vm = Column(Boolean)
    notification_method = Column(Integer)
    email = Column(String(100))
    sms_addr = Column(String(80))
    ivr_tree_id = Column(Integer, ForeignKey('ivr_tree.id'))
    vm_greeting = Column(String(100))
    unavail_greeting = Column(String(100))
    busy_greeting = Column(String(100))
    tmp_greeting = Column(String(100))
    is_tmp_greeting_on = Column(Boolean)
    vm_name_recording = Column(String(100))
    greeting_prompt_id = Column(Integer, ForeignKey('prompts.id'))
    last_changed = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    greeting = relationship('Prompt')
    ivr = relationship('IvrTree')

    def getVmFolder(self):
        return self.folder

    def getNameFolder(self):
        return self.folder + "/name"

    def getGreetingFolder(self):
        return self.folder + "/greeting"


class IvrTree(Base):
    __tablename__ = 'ivr_tree'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode(40), nullable=False, unique=True)
    parent_id = Column(Integer, ForeignKey('ivr_tree.id'))
    current_prompt_id = Column(Integer, ForeignKey('prompts.id'))
    parent_prompt_id = Column(Integer, ForeignKey('prompts.id'))
    dtmf_len = Column(Integer)
    dtmf_key = Column(String(1))
    timeout = Column(Integer)
    is_interruptable = Column(Boolean)

    parent      = relationship("IvrTree",
                     primaryjoin=('ivr_tree.c.id==ivr_tree.c.parent_id'),
                     remote_side='IvrTree.id',
                     backref=backref("children" ))

    current_prompt = relationship("Prompt", primaryjoin=('ivr_tree.c.current_prompt_id==prompts.c.id'))
    parent_prompt = relationship("Prompt",primaryjoin=('ivr_tree.c.parent_prompt_id==prompts.c.id'))

class Prompt(Base):
    __tablename__ = 'prompts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(40), nullable = False)

    invalidRequest = "Invalid_Request"                                #  1
    invalidMessage = "Invalid_Message"                                #  7
    userGreeting = "User_Greeting"                                    #  3
    userNameRecording = "User_Name_Recording"                         #  4
    userLeaveMessage = "User_Leave_Message"                           #  5
    userNotExist = "User_Not_Exist"                                   #  2
    activityMenu = "Activity_Menu"                                    #  8
    messageSaved = "Message_Saved"                                    #  6
    helpMenu = "Help_Menu"                                            #  9
    vmSummary = "VM_Summary"                                          # 10
    firstMessage = "First_Message"                                    # 12
    nextMessage = "Next_Message"                                      # 14
    lastMessage = "Last_Message"                                      # 13
    vmMessageHeader = "VM_Message_Header"                             # 11
    noMoreMessage = "No_More_Message"                                 # 15
    postMessage = "Post_Message"                                      # 16
    stillThere = "Still_There"                                        # 17
    stillThereGetMessage = "Still_There_VM_Get_Message"               # 19
    goodbye = "Goodbye"                                               # 18
    main1RecordMessage = "Main_1_Record_Message"                      # 653 - mc-input-recordnow - "Record the message/comment and press pound"
    # Login Menu: External Access Prompts
    loginWelcomeMessage = "Login_Welcome_Message"                     # 20
    loginInvalidMailbox = "Login_Invalid_Mailbox"                     # 21
    loginInputPassword = "Login_Input_Password_Message"               # 22
    loginInvalidPassword = "Login_Invalid_Password"                   # 23
    loginLoggedIn = "Login_Logged_In"                                 # 24
    loginStillThere = "Login_Still_There_Message"                     # 28
    # Record, Send, Forward, Reply Menu
    rsfInputRecordNow = "RSF_Input_Record_Now"                        # 25
    rsfMenuRecord = "RSF_Amenu_Record"                                # 26
    rsfMessageDeleted = "RSF_Message_Deleted"                         # 27
    rsfApprovedMessage = "RSF_Approved_Message"                       # 29
    rsfCreateForward = "RSF_Create_Forward_Message"                   # 30
    rsfRecordStillThere = "RSF_Record_Still_There_Message"            # 31
    rsfForwardStillThere = "RSF_Forward_Still_There_Message"          # 32
    rsfDelivered = "RSF_Delivered_Message"                            # 33
    rsfCancelled = "RSF_Cancelled_Message"                            # 34
    # Send Message Menu
    sendInputList = "Send_Input_List_Now"                             # 35
    sendStillThere = "Send_Still_There_Message"                       # 36
    sendInvalid = "Send_Invalid_Mailbox_List"                         # 37
    sendApprovedCount = "Send_Approved_Delivered_Count"               # 38
    sendRemoved = "Send_Removed_Message"                              # 39
    sendAdded = "Send_Added_Message"                                  # 40
    # Personal Greetings Menu
    personalGreeting = "Personal_Greeting_Message"                    # 41
    personalGreetingStillThere = "Personal_Greeting_Still_There_Message" # 42
    # Greetings Menu
    greetingsBusyIs = "Greetings_Busy_Is_Message"                     # 43
    greetingsTmpIs = "Greetings_Temp_Is_Message"                      # 44
    greetingsUnavailIs = "Greetings_Unavailable_Is_Message"           # 45
    greetingsNotSet = "Greetings_Not_Set_Message"                     # 46
    greetingsRecordMenu = "Greetings_Record_Menu"                     # 47
    greetingsRecordBusy = "Greetings_Busy_Record_Message"             # 48
    greetingsRecordUnavail = "Greetings_Unavail_Record_Message"       # 49
    greetingsRecordTmp = "Greetings_Tmp_Record_Message"               # 50
    greetingsApproved = "Greetings_Approved_Message"                  # 51
    greetingsBusyNotSet = "Greetings_Busy_Not_Set"                    # 52
    greetingsUnavailNotSet = "Greetings_Unavail_Not_Set"              # 53
    greetingsTmpNotSet = "Greetings_Tmp_Not_Set"                      # 54
    # Personal Options Menu
    personalOptions = "Personal_Options_Menu"                         # 55
    personalStillThere = "Personal_Options_Still_There_Message"       # 56
    # Administrator Mainling List Menu
    mailListMenu = "AML_Menu_Message"                                 # 57
    mailListMenuStillThere = "AML_ListStillThere"                     # 75
    mailListRecord = "AML_Record_Message"                             # 58
    mailListName = "AML_Record_List_Name"                             # 59
    mailListCode = "AML_Enter_Key_Code"                               # 60
    mailListExists = "AML_List_Already_Exists"                        # 76
    mailListApprove = "AML_List_Approve"                              # 77
    # Change Password Menu
    passwordNew = "Password_Enter_New"                                # 61
    passwordNoMatch = "Password_No_Match"                             # 62
    passwordReEnter = "Password_Re_Enter_New"                         # 63
    passwordChanged = "Password_Changed_Message"                      # 64
    # Record Name Menu
    recordNameIs = "Record_Name_Name_Is"                              # 65
    recordName = "Record_Name_Record"                                 # 66
    # Scan Message Menu
    scanMenu = "Scan_Menu_Message"                                    # 67
    scanStillThere = "Scan_Still_There_Message"                       # 68
    # Internal Access Menu
    invalidOption = "Invalid_Option"                                  # 69
    internalWelcome = "Internal_Access_Welcome"                       # 70

    userUnavailGreeting = "User_Unavail_Greeting"                     # 71
    userBusyGreeting = "User_Busy_Greeting"                           # 72
    userTmpGreeting = "User_Tmp_Greeting"                             # 73
    userName = "User_Name"                                            # 74

    sayNumber = "Say_Number"                                          # 78
    TTS  = "TTS"                                                      # 79
    tmpGreetingStatus = "Temp_Greeting_Status"                        # 80
    onPrompt = "on_prompt"                                            # 81
    offPrompt = "off_prompt"                                          # 82
    vmMessage = "VM_Message"                                          # 83
    newPrompt = "New_Prompt"                                          # 84
    oldPrompt = "Old_Prompt"                                          # 85
    messagePrompt = "Message_Prompt"                                  # 86
    replyForwardMessage = "Reply_Forward_Message"                     # 87
    

    @staticmethod
    def getByName(name=None):
        return DBSession.query(Prompt).filter_by(name=name).first()


    def getFullPrompt(self, user=None, vm=None, param=None):
        listprompt = []
        for i in self.details:
            if i.prompt_type == 1:
                listprompt.append({'uri':i.path, 'delayafter':i.delay_after})
            elif i.prompt_type == 2:
                if i.path == "tts":
                    listprompt.append({'tts':list(param), 'delayafter':i.delay_after})
                elif i.path == "Unread-Count":
                    listprompt.extend(self._getSubPrompt(count=user.getUnreadCount(), new=1))
                elif i.path == "Read-Count":
                    listprompt.extend(self._getSubPrompt(count=user.getReadCount(), new=0))
                elif i.path == "VM-Header":
                    listprompt.extend(self._getVmTime(vm=vm))
                elif i.path == "sayNum":
                    listprompt.append({'sayNum':'%s'%param, 'delayafter':i.delay_after})
            elif i.prompt_type == 3:
                if user.vm_prefs.vm_name_recording:
                    listprompt.append({'uri':user.vm_prefs.vm_name_recording, 'delayafter':i.delay_after})
                else:
                    listprompt.append({'tts':list(user.extension), 'delayafter':i.delay_after})
            elif i.prompt_type == 4:
                listprompt.append({'uri':user.vm_prefs.vm_greeting, 'delayafter':i.delay_after})
            elif i.prompt_type == 5:
                listprompt.append({'uri':vm.path, 'delayafter':i.delay_after})
                replied = vm.reply_to
                while replied is not None and replied.is_attached:
                    listprompt.append({'uri':replied.parentVoicemail.path, 'delayafter':i.delay_after})
                    replied = replied.parentVoicemail.reply_to
            elif i.prompt_type == 6:
                listprompt.append({'uri':user.vm_prefs.unavail_greeting, 'delayafter':i.delay_after})
            elif i.prompt_type == 7:
                listprompt.append({'uri':user.vm_prefs.busy_greeting, 'delayafter':i.delay_after})
            elif i.prompt_type == 8:
                listprompt.append({'uri':user.vm_prefs.tmp_greeting, 'delayafter':i.delay_after})
        return listprompt
    
    def _getVmTime(self, vm):
        retlist = []
        retlist.append({'datetime':'%d' % int(time.mktime(vm.create_date.timetuple())), 'delayafter':2})
        return retlist

    def _getSubPrompt(self, count, new=0):
        retlist = []
        if count == 0:
            retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-no.wav', 'delayafter':2}) 
            if new:
                retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-newm.wav', 'delayafter':2}) 
            else:
                retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-oldm.wav', 'delayafter':2}) 
            retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-messages.wav', 'delayafter':2}) 
        elif count == 1:
            retlist.append({'tts':'1', 'delayafter':2}) 
            if new:
                retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-newm.wav', 'delayafter':2}) 
            else:
                retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-oldm.wav', 'delayafter':2}) 
            retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-message.wav', 'delayafter':2}) 
        else:
            retlist.append({'tts':'%s'%count, 'delayafter':2}) 
            if new:
                retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-newm.wav', 'delayafter':2}) 
            else:
                retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-oldm.wav', 'delayafter':2}) 
            retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-messages.wav', 'delayafter':2}) 
        return retlist


class PromptDetails(Base):
    __tablename__ = 'prompt_details'
    id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_id = Column(Integer, ForeignKey('prompts.id'))
    sequence_number = Column(Integer, nullable=False)
    prompt_type = Column(Integer, nullable=False)
    path = Column(String(100))
    delay_before = Column(Integer)
    delay_after = Column(Integer)

    prompts = relationship("Prompt", backref=backref('details', order_by=sequence_number))

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(40), nullable = False)

    def __init__(self, name):
        self.name = name

class ReplyTo(Base):
    __tablename__ = 'reply_to'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vm_id = Column(Integer,  ForeignKey('voicemails.id'))
    is_attached = Column(Boolean)

    parentVoicemail = relationship("Voicemail", uselist=False, foreign_keys=vm_id)

class UserSession(Base):
    __tablename__ = 'user_session'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(40))
    data = Column(Text)
    create_date = Column(DateTime, nullable=False, default=datetime.datetime.utcnow )
    last_updated = Column(DateTime)

    
    def loadState(self, user, callid):
        self.uid = callid
        state = State()
        state.unread = []
        state.read = []
        state.curmessage = 1
        state.uid = callid
        if user:
            for i in user.voicemails:
                if i.status == 1:
                    continue
                if i.is_read:
                    state.read.append(i.id)
                else:
                    state.unread.append(i.id)
            if len(state.unread) == 0:
                state.message_type = "read"
        self.saveState(state=state)


    def getCurrentState(self):
        s = State()
        cdata =  json.loads(self.data)
        for i in s.__dict__:
            s.__dict__[i] = cdata.get(i, None)
        return s
    

    def saveState(self, state):
        self.last_updated = datetime.datetime.utcnow()
        self.data = json.dumps(state, default=lambda o: o.__dict__)
        DBSession.add(self)
        DBSession.flush()
       

class State():

    def __init__(self):
        self.unread = None
        self.read = None
        self.curmessage = 0
        self.uid = None
        self.message_type = "Unread"
        self.retryCount = 0
        self.password = None
        self.destlist = None
        self.dtmf = None
        self.nextaction = None
        self.maxlength = None
        self.menu = None
        self.step = None
        self.invalidaction = None
        self.action = None
        self.folder = None
        self.mode = "Full"


    def previousMessage(self):
        self.curmessage = self.curmessage - 1
        if self.message_type == "read":
            if self.curmessage < 1:
                if len(self.unread):
                    self.curmessage = len(self.unread)
                    self.message_type = "unread"
        if state.curmessage < 1:
            state.curmessage = 1


    def reset(self):
        self.curmessage = 0
        self.message_type = "unread"
        if len(self.unread) == 0:
            self.message_type = "read"


    def nextMessage(self):
        self.curmessage = self.curmessage + 1
        if self.message_type == "Unread":
            if self.curmessage > len(self.unread):
                self.message_type = "read"
                self.curmessage = 1
