import deform
import logging
log = logging.getLogger(__name__)

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound




from ..models.models import (
    DBSession,
    User,
    )

from .views import UserSchema

class UsersView(object):
    
    def __init__(self, request):
        self.request = request
    
    @view_config(route_name='add_user', permission='admin', renderer='add_user.mako')
    def add_user(self):
        schema = UserSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('add_user'), buttons=('Add User','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url('home'))
        
        if 'Add_User' in self.request.params:
            appstruct = None
            try:
                appstruct = form.validate(self.request.POST.items())
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}

            newuser = User(username=appstruct['username'], 
                           name=appstruct['name'], 
                           extension=appstruct['extension'], 
                           pin=appstruct['pin'], 
                           status=1)
            DBSession.add(newuser)
            DBSession.flush()
            return dict(form=form.render(appstruct={'success':'User added successfully'}))
        return dict(form=form.render(appstruct={}))
        
        