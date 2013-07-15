import deform
import logging
log = logging.getLogger(__name__)

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound




from ..models.models import (
    DBSession,
    User,
    UserRole,
    )

from .views import UserSchema, user_DoesExist, user_DoesNotExist

class UsersView(object):
    
    def __init__(self, request):
        self.request = request
    
    @view_config(route_name='add_user', permission='admin', renderer='add_user.mako')
    def add_user(self):
        schema = UserSchema(validator = user_DoesExist).bind(request=self.request)
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

            if appstruct['role'] == 'admin':
                newuser.role = [DBSession.query(UserRole).filter_by(role_name= appstruct['role']).first()]
                
            DBSession.add(newuser)
            DBSession.flush()
            return dict(form=form.render(appstruct={'success':'User added successfully'}))
        return dict(form=form.render(appstruct={}))
    
    @view_config(route_name='edit_user', permission='admin', renderer='edit_user.mako')
    def edit_user(self):
        schema = UserSchema(validator = user_DoesNotExist).bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('edit_user'), buttons=('Save','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url('home'))
        
        if 'Save' in self.request.params:
            appstruct = None
            try:
                appstruct = form.validate(self.request.POST.items())
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}

            DBSession.query(User).filter_by(username=appstruct['username']).update({'name':appstruct['name'], 
                                          'extension':appstruct['extension'],
                                          'pin':appstruct['pin']})
            
            user = DBSession.query(User).filter_by(username=appstruct['username']).first()
            if appstruct['role'] == 'admin':
                user.role = [DBSession.query(UserRole).filter_by(role_name= appstruct['role']).first()]
                
            DBSession.flush()
            return dict(form=form.render(appstruct={'success':'User edited successfully'}))
        return dict(form=form.render(appstruct={}))
    
    @view_config(route_name='list_users', permission='admin', renderer='delete_user.mako')
    def list_users(self):
        users = DBSession.query(User).all()
        return dict(users = users)
    
    @view_config(route_name='delete_user', permission='admin')
    def delete_user(self):
        username = self.request.matchdict['username']
        DBSession.query(User).filter_by(username=username).delete()
        DBSession.flush()
        return HTTPFound(location = self.request.route_url('list_users'))
        
        