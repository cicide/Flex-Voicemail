import deform
import logging
log = logging.getLogger(__name__)

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound



from ..models.models import (
    DBSession,
    User,
    UserRole,
    UserVmPref,
    )

from ..schemas import UserSchema, user_DoesExist

class UsersView(object):
    
    def __init__(self, request):
        self.request = request
    
    
    def save_vmpref(self, user):
        pass
        
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

            DBSession.add(newuser)
            DBSession.flush()
            if appstruct['role'] == 'admin':
                 user_role = UserRole('Admin', newuser.id)
                 DBSession.add(user_role)
                 DBSession.flush()
            self.save_vmpref(newuser);
            return dict(form=form.render(appstruct={'success':'User added successfully'}))
        return dict(form=form.render(appstruct={}))
    
    @view_config(route_name='edit_user', permission='admin', renderer='edit_user.mako')
    def edit_user(self):
        userid = self.request.matchdict['userid']
        user = DBSession.query(User).filter_by(id=userid).first()
        user_role = DBSession.query(UserRole).filter_by(user_id=userid).first()
        
        schema = UserSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('edit_user', userid=userid), buttons=('Save','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url('list_users'))
        
        if 'Save' in self.request.params:
            appstruct = None
            try:
                if user.username != self.request.POST['username']:
                    schema.validator = user_DoesExist
                appstruct = form.validate(self.request.POST.items())
                
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}
            
            user.username = appstruct['username']
            user.name = appstruct['name']
            user.extension = appstruct['extension']
            user.pin = appstruct['pin']
            DBSession.add(user) 
            if 'admin' in appstruct['role'] and user_role is None:
                user_role = UserRole('Admin', userid)
                DBSession.add(user_role)
            elif user_role:
                DBSession.delete(user_role)
            DBSession.flush()
            return HTTPFound(location =self.request.route_url('list_users'))
        return dict(form=form.render(appstruct=user.__dict__))
    
    @view_config(route_name='list_users', permission='admin', renderer='user_list.mako')
    def list_users(self):
        users = DBSession.query(User).all()
        return dict(users = users)
        
       
    
    @view_config(route_name='delete_user', permission='admin')
    def delete_user(self):
        userid = self.request.matchdict['userid']
        DBSession.query(User).filter_by(id=userid).delete()
        DBSession.query(UserRole).filter_by(user_id=userid).delete()
        DBSession.flush()
        return HTTPFound(location = self.request.route_url('list_users'))
        
        