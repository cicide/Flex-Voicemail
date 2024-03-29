import shutil
import deform
import logging
log = logging.getLogger(__name__)

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.renderers import render

from ..models.models import (
    DBSession,
    User,
    UserRole,
    UserVmPref,
    )

from ..schemas import (
    UserSchema, 
    user_DoesExist,
    VMPrefSchema,
    )

from .preferviews import VMPrefView

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

            newuser = User(username=appstruct['username'] if appstruct.get('username') and appstruct.get('username') != 'None' else None, 
                           name=appstruct['name'], 
                           extension=appstruct['extension'], 
                           pin=appstruct['pin'], 
                           status=1)

            DBSession.add(newuser)
            DBSession.flush()

            is_admin = appstruct['admin']
            if is_admin:
                role = UserRole('Admin', newuser.id)
                DBSession.add(role)
            pref = VMPrefView(self.request)
            pref.create_vmpref(newuser)
            return dict(form=form.render(appstruct={'success':'User added successfully'}))
        return dict(form=form.render(appstruct={}))
    
    @view_config(route_name='edit_user', permission='admin', renderer='edit_user.mako')
    def edit_user(self):
        userid = self.request.matchdict['userid']
        user = DBSession.query(User).filter_by(id=userid).first()
        is_admin = False
        user_role = None
        for i in user.role:
            if i.role_name == 'Admin':
                is_admin = True
                user_role = i
        
        schema = UserSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('edit_user', userid=userid), buttons=('Save','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url('list_users',type='vmusers'))
        
        if 'Save' in self.request.params:
            appstruct = None
            try:
                if user.extension != self.request.POST['extension']:
                    schema.validator = user_DoesExist
                appstruct = form.validate(self.request.POST.items())
                
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}
            
            user.username = appstruct['username'] if appstruct.get('username') and appstruct.get('username') != 'None' else None
            user.name = appstruct['name']
            user.extension = appstruct['extension']
            user.pin = appstruct['pin']
            if appstruct['admin'] != is_admin and self.request.user.id != user.id:
                if is_admin:
                    DBSession.delete(user_role)
                else:
                    user_role = UserRole('Admin', user.id)
                    DBSession.add(user_role)
            DBSession.add(user) 
            return HTTPFound(location =self.request.route_url('list_users', type='vmusers'))
        appstruct = user.__dict__
        appstruct['admin'] = is_admin
        return dict(form=form.render(appstruct=user.__dict__))
    
    @view_config(route_name='list_users', permission='admin',renderer = 'user_list.mako')
    def list_users(self):
        type = self.request.matchdict.get('type',None)
        admins = False
        if type == 'vmusers':
            self.request.override_renderer = 'user_list.mako'
        elif type == 'admins':
            self.request.override_renderer = 'manage_roles.mako'
            admins = True
        else:
            return HTTPNotFound()
        
        return dict(users = self.get_users(admins=admins))
        
    def get_users(self, admins=False):
        if admins:
            l = DBSession.query(User).filter_by(is_list=0).all()
            ret_list = []
            for i in l:
                for j in i.role:
                    if j.role_name == "Admin":
                        ret_list.append(i)
            return ret_list
        return DBSession.query(User).filter_by(is_list=0).all()
    
    
    @view_config(route_name='delete_user', permission='admin', renderer='json')
    def delete_user(self):
        userid = self.request.POST.get('userid',None)
        user = DBSession.query(User).get(userid)
        if user.id == self.request.user.id:
            return {
                    'success': False, 'msg': 'Unable to remove %s ' % self.request.user.extension,
                    'html': render('user_list.mako', {'users': self.get_users()}, self.request),
                }
        DBSession.query(UserRole).filter_by(user_id=userid).delete()
        user_vm = DBSession.query(UserVmPref).filter_by(user_id=userid).first()
        DBSession.delete(user)
        DBSession.delete(user_vm)
        #shutil.rmtree(user_vm.folder) #As it gives error : OSError: [Errno 2] No such file or directory: 'file://var/spool/asterisk/appvm/24' 
        #shutil.rmtree(user_vm.folder.split(':/')[1])
        return {
                    'success': True, 'msg': 'Deleted %s ' % user.extension,
                    'html': render('user_list.mako', {'users': self.get_users()}, self.request),
                }
    
    @view_config(route_name='edit_admin', permission='admin', xhr=True, renderer='json')
    def toggle_admin(self):
        userid = self.request.POST.get('userid',None)
        do_admin = self.request.POST.get('admin',None)
        msg = None
        try:
            if do_admin == u'true':
                user_role = UserRole('Admin', userid)
                DBSession.add(user_role)
                msg = "Admin role added to user."
            else:
                if int(userid) == self.request.user.id:
                    raise ValueError('Invalid Action')
                user_role = DBSession.query(UserRole).filter_by(user_id=userid, role_name='Admin').first()
                DBSession.delete(user_role)
                msg = "Admin role removed from user."
            return {
                    'success': True, 'msg': msg,
                    'html': render('manage_roles.mako', {'users': self.get_users(admins=True)}, self.request),
                }
        except Exception, e:
            return {
                    'success': False, 'msg': e.message,
                    'html': render('manage_roles.mako', {'users': self.get_users(admins=True)}, self.request),
                }
        
        
