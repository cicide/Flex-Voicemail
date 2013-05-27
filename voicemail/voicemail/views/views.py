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
    username = colander.SchemaNode(colander.String(), description="Extension of the user")
    password = colander.SchemaNode(
                    colander.String(),
                    validator=colander.Length(min=4, max=20),
                    widget=deform.widget.CheckedPasswordWidget(),
                    description='Enter a password')
    email = colander.SchemaNode(colander.String(), title='Email',
                    widget=deform.widget.TextInputWidget(size=40, maxlength=260, type='email'),
                    description="The email address of the user. Example: joe@example.com")

@view_config(route_name='home', renderer='home.mako', permission='admin')
def home(request):
    return dict(user= request.user,)


@view_config(route_name='login', renderer='login.mako')
@forbidden_view_config(renderer='login.mako')
def login(request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        referrer = '/' # never use the login form itself as came_from
    schema = LoginSchema()
    form = deform.Form(schema, action=login_url, buttons=('Login',))
    defaults = {}
    defaults['came_from'] = request.params.get('came_from', referrer)
    if request.POST:
        appstruct = None
        try:
            appstruct = form.validate(request.POST.items())
        except deform.ValidationFailure, e:
            log.exception('in form validated')
            return {'form':e.render()}

        login = appstruct['username']
        password = appstruct['password']
        came_from = appstruct['came_from']
        user = DBSession.query(User).filter_by(username=login, pin = password).first()
        if user:
            headers = remember(request, user.id)
            user.last_login = datetime.datetime.utcnow()
            request.user = user
            return HTTPFound(location = came_from, headers = headers)
        FlashMessage(request, 'Invalid Username or password', kind='error')
        return dict( form= form.render(appstruct=appstruct),
                   )

    return dict(
            url = request.application_url + '/login',
            form = form.render(appstruct=defaults)
        )

@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    request.session.delete()
    return HTTPFound(location = request.route_url('login'),
        headers = headers)
