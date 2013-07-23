import deform
import datetime
from sqlalchemy.exc import DBAPIError
from pyramid.view import (
    view_config,
    forbidden_view_config,
    )

from pyramid.security import (
    remember,
    forget,
    authenticated_userid,
    )

from pyramid.httpexceptions import (
    HTTPFound,
    HTTPNotFound,
    )

from ..models.models import (
    DBSession,
    User,
    )

from ..schemas import (
    LoginSchema,
    UserSchema,
    )


from bag.web.pyramid.flash_msg import FlashMessage

import logging
log = logging.getLogger(__name__)


@view_config(route_name='home', renderer='home.mako')
def home(request):
    return dict(user= request.user,)


@view_config(route_name='login', renderer='login.mako')
@forbidden_view_config(renderer='login.mako')
def login(request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        referrer = '/' # never use the login form itself as came_from
    schema = LoginSchema().bind(request=request)
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

