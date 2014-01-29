import deform
import colander
import six

from deform.schema import FileData

from ..models.models import (
    DBSession,
    User,
    )
import logging
log = logging.getLogger(__name__)

@colander.deferred
def deferred_csrf_default(node, kw):
    request = kw.get('request')
    csrf_token = request.session.get_csrf_token()
    return csrf_token


@colander.deferred
def deferred_csrf_validator(node, kw):
    def validate_csrf(node, value):
        request = kw.get('request')
        csrf_token = request.session.get_csrf_token()

        if six.PY3:
            if not isinstance(csrf_token, str):
                csrf_token = csrf_token.decode('utf-8')

        if value != csrf_token:
            raise colander.Invalid(node,
                                   'Invalid cross-site scripting token')
    return validate_csrf

@colander.deferred
def deferred_choices_widget(node,kw):
    choices = (
    ('', '- Select -'),
    ('admin', 'Admin'),
    )
    return deform.widget.SelectWidget(values=choices)

def user_DoesExist(node,appstruct):
    if appstruct.get('username'):
        if DBSession.query(User).filter_by(username=appstruct['username']).count() > 0:
            raise colander.Invalid(node, 'Username already exist.!!')
    if DBSession.query(User).filter_by(extension=appstruct['extension']).count() > 0:
        raise colander.Invalid(node, 'Extension already assigned.!!')

def list_DoesExist(node,appstruct):
    if appstruct.get('username'):
        if DBSession.query(User).filter_by(username=appstruct['username']).count() > 0:
            raise colander.Invalid(node, 'Listname already exist.!!')
    if DBSession.query(User).filter_by(extension=appstruct['extension']).count() > 0:
        raise colander.Invalid(node, 'Extension already assigned.!!')
    
def CheckAuthentication(node,appstruct):
    if (DBSession.query(User).filter_by(username=appstruct['username'], pin=appstruct['password']).count() == 0) and \
       (DBSession.query(User).filter_by(extension=appstruct['username'], pin=appstruct['password']).count() == 0):
        raise colander.Invalid(node, 'Invalid Username or password')
    
def checkUploadFile(node,data):
    AUDIO_EXTS = ['audio/mp3', 'audio/wav']
    if data['mimetype'] not in AUDIO_EXTS:
        raise colander.Invalid(node, 'Invalid file format')
    pass

class CSRFSchema(colander.Schema):
    csrf_token = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.HiddenWidget(),
        default=deferred_csrf_default,
        validator=deferred_csrf_validator,
    )


class Store(dict):
    def preview_url(self, name):
        return "/tmp"
 
store = Store()

class LoginSchema(CSRFSchema):
    username = colander.SchemaNode(colander.String())
    came_from = colander.SchemaNode(colander.String(),
                    widget = deform.widget.HiddenWidget())
    password = colander.SchemaNode(
                    colander.String(),
                    validator=colander.Length(min=4, max=20),
                    widget=deform.widget.PasswordWidget(size=20),
                    description='Enter a password')

class ListSchema(CSRFSchema):
    username = colander.SchemaNode(colander.String(), 
                   description="Login for the list", missing=None)
    name = colander.SchemaNode(colander.String(), 
                   description='List name')
    extension = colander.SchemaNode(colander.String(), 
                    description='Extension')
    pin = colander.SchemaNode(colander.String(), 
              description='PIN')


class UserSchema(CSRFSchema):
    username = colander.SchemaNode(colander.String(), 
                   description="Login for the user", missing=None, default=None)
    name = colander.SchemaNode(colander.String(), 
                   description='Full name')
    extension = colander.SchemaNode(colander.String(), 
                    description='Extension')
    pin = colander.SchemaNode(colander.String(), 
              description='PIN')

    
class VMPrefSchema(CSRFSchema):
    deliver_vm = colander.SchemaNode(colander.Boolean(),
                    description="Deliver VM", missing=None)
    attach_vm = colander.SchemaNode(colander.Boolean(),
                    description="Attach VM", missing=None)
    email = colander.SchemaNode(colander.String(),
                    validator=colander.Email(),
                    description="Email", missing=None)
    sms_addr = colander.SchemaNode(colander.String(),
                    description="SMS Address", missing=None)
    vm_greeting = colander.SchemaNode(FileData(), widget=deform.widget.FileUploadWidget(store),
                    description="VM Greeting", missing=None,
                    validator = checkUploadFile)
    vm_name_recording = colander.SchemaNode(FileData(), widget=deform.widget.FileUploadWidget(store),
                    description="VM Name Recording", missing=None,
                    validator = checkUploadFile)

class ListUserAddSchema(CSRFSchema):
    widget = deform.widget.AutocompleteInputWidget(
          size=30,
          min_length=1,
          values = '/list/users')
    sext = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(max=30),
        widget = widget,
        description='Enter an Extension')
