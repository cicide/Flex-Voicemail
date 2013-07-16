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
from sqlalchemy.orm import relationship, backref

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

    voicemails = relationship("Voicemail", backref='user', cascade="all, delete, delete-orphan")
    role = relationship("UserRole", backref='users')
    vm_prefs = relationship("UserVmPref", uselist=False, backref='user')

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
    vm_name_recording = Column(String(100))
    greeting_prompt_id = Column(Integer, ForeignKey('prompts.id'))
    last_changed = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    greeting = relationship('Prompt')
    ivr = relationship('IvrTree')

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

    invalidRequest = "Invalid_Request"
    invalidMessage = "Invalid_Message"
    userGreeting = "User_Greeting"
    userNameRecording = "User_Name_Recording"
    userLeaveMessage = "User_Leave_Message"
    userNotExist = "User_Not_Exist"
    userVmAccess = "User_Vm_Access"
    messageSaved = "Message_Saved"
    helpMenu = "Help_Menu"
    vmSummary = "VM_Summary"

    def getFullPrompt(self, user=None):
        listprompt = []
        for i in self.details:
            if i.prompt_type == 1:
                listprompt.append({'uri':i.path, 'delayafter':i.delay_after})
            elif i.prompt_type == 2:
                if i.path == "Extension":
                    extension = user.extension
                    listprompt.append({'tts':list(extension), 'delayafter':i.delay_after})
                elif i.path == "Unread-Count":
                    listprompt.extend(self._getSubPrompt(count=user.getUnreadCount(), new=1))
                elif i.path == "Read-Count":
                    listprompt.extend(self._getSubPrompt(count=user.getReadCount(), new=0))
            elif i.prompt_type == 3:
                listprompt.append({'uri':user.vm_prefs.vm_name_recording, 'delayafter':i.delay_after})
            elif i.prompt_type == 4:
                listprompt.append({'uri':user.vm_prefs.vm_greeting, 'delayafter':i.delay_after})
        return listprompt
    
    def _getSubPrompt(self, count, new=0):
        retlist = []
        if count == 0:
           retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-no.wav', 'delayafter' : 2}) 
           if new:
               retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-newm.wav', 'delayafter' : 2}) 
           else:
               retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-oldm.wav', 'delayafter' : 2}) 
           retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-messages.wav', 'delayafter' : 2}) 
        elif count == 1:
           retlist.append({'tts':'1', 'delayafter' : 2}) 
           if new:
               retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-newm.wav', 'delayafter' : 2}) 
           else:
               retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-oldm.wav', 'delayafter' : 2}) 
           retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-message.wav', 'delayafter' : 2}) 
        else:
           retlist.append({'tts':'%s'%count, 'delayafter' : 2}) 
           if new:
               retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-newm.wav', 'delayafter' : 2}) 
           else:
               retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-oldm.wav', 'delayafter' : 2}) 
           retlist.append({'uri':'file://var/lib/asterisk/sounds/en/macp/mc-message-messages.wav', 'delayafter' : 2}) 
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

