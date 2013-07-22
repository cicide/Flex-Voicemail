import deform
import colander
import six

from ..models.models import (
    DBSession,
    User,
    )

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
    if DBSession.query(User).filter_by(username=appstruct['username']).count() > 0:
        raise colander.Invalid(node, 'Username already exist.!!')

class CSRFSchema(colander.Schema):
    csrf_token = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.HiddenWidget(),
        default=deferred_csrf_default,
        validator=deferred_csrf_validator,
    )


class LoginSchema(CSRFSchema):
    username = colander.SchemaNode(colander.String())
    came_from = colander.SchemaNode(colander.String(),
                    widget = deform.widget.HiddenWidget())
    password = colander.SchemaNode(
                    colander.String(),
                    validator=colander.Length(min=4, max=20),
                    widget=deform.widget.PasswordWidget(size=20),
                    description='Enter a password')

class UserSchema(CSRFSchema):
    username = colander.SchemaNode(colander.String(), 
                   description="Extension of the user")
    name = colander.SchemaNode(colander.String(), 
                   description='Full name')
    extension = colander.SchemaNode(colander.String(), 
                    description='Extension')
    pin = colander.SchemaNode(colander.String(), 
              description='PIN')
    role = colander.SchemaNode(
                    colander.String(),
                    widget=deferred_choices_widget,
                    missing = '',
                    )
