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
    UserList,
    UserRole,
    UserVmPref,
    )

from ..schemas import (
    ListSchema, 
    list_DoesExist,
    VMPrefSchema,
    ListUserAddSchema,
    )

from .preferviews import VMPrefView

class ListsView(object):
    
    def __init__(self, request):
        self.request = request
    
    @view_config(route_name='add_list', permission='admin', renderer='add_list.mako')
    def add_list(self):
        schema = ListSchema(validator = list_DoesExist).bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('add_list'), buttons=('Add List','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url('home'))
        
        if 'Add_List' in self.request.params:
            appstruct = None
            try:
                appstruct = form.validate(self.request.POST.items())
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}

            newlist = User(username=appstruct['username'] if appstruct['username'] and appstruct['username'] != 'None' else None, 
                           name=appstruct['name'], 
                           extension=appstruct['extension'], 
                           pin=appstruct['pin'], 
                           status=1)

            newlist.is_list = True
            DBSession.add(newlist)
            DBSession.flush()
            pref = VMPrefView(self.request)
            pref.create_vmpref(newlist)
            return dict(form=form.render(appstruct={}), success=True, msg='List %s created successfully' % newlist.name)
        return dict(form=form.render(appstruct={}), success=False)
    
    @view_config(route_name='edit_list', permission='admin', renderer='edit_list.mako')
    def edit_list(self):
        listid = self.request.matchdict['listid']
        mylist = DBSession.query(User).filter_by(id=listid).first()
        list_role = DBSession.query(UserRole).filter_by(user_id=listid, role_name='Admin').first()
        
        schema = ListSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('edit_list', listid=listid), buttons=('Save','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url('list_lists'))
        
        if 'Save' in self.request.params:
            appstruct = None
            try:
                if mylist.extension != self.request.POST['extension']:
                    schema.validator = list_DoesExist
                appstruct = form.validate(self.request.POST.items())
                
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}
            
            mylist.username = appstruct['username'] if appstruct['username'] and appstruct['username'] != 'None' else None
            mylist.name = appstruct['name']
            mylist.extension = appstruct['extension']
            mylist.pin = appstruct['pin']
            DBSession.add(mylist) 
            self.request.session.flash("success;Save Preferences")
            return HTTPFound(location =self.request.route_url('list_lists'))
        return dict(form=form.render(appstruct=mylist.__dict__))
    
    @view_config(route_name='list_lists', permission='admin',renderer = 'list_list.mako')
    def list_lists(self):
        return dict(lists = self.get_lists())
        

    def get_lists(self):
        return DBSession.query(User).filter_by(is_list=1).all()
    
       
    @view_config(route_name='delete_list', permission='admin', renderer='json')
    def delete_list(self):
        listid = self.request.POST.get('listid',None)
        mylist = DBSession.query(User).get(listid)
        if mylist.id == self.request.user.id:
            return {
                    'success': False, 'msg': 'Unable to remove %s ' % self.request.user.extension,
                    'html': render('list_list.mako', {'lists': self.get_lists()}, self.request),
                }
        list_vm = DBSession.query(UserVmPref).filter_by(user_id=listid).first()
        DBSession.query(UserList).filter_by(list_id=listid).delete()
        DBSession.query(UserRole).filter_by(user_id=listid).delete()
        DBSession.delete(list_vm)
        DBSession.delete(mylist)
        #shutil.rmtree(user_vm.folder) #As it gives error : OSError: [Errno 2] No such file or directory: 'file://var/spool/asterisk/appvm/24' 
        #shutil.rmtree(user_vm.folder.split(':/')[1])
        return {
                    'success': True, 'msg': 'Deleted %s ' % mylist.extension,
                    'html': render('list_list.mako', {'lists': self.get_lists()}, self.request),
                }


    @view_config(route_name='users_list_remove', permission='admin', renderer='list_users.mako')
    def users_list_remove(self):
        listid = self.request.matchdict['listid']
        mylist = DBSession.query(User).get(listid)
        userid = self.request.matchdict['userid']
        ulist = DBSession.query(UserList).filter_by(list_id=listid, user_id=userid).first()
        if ulist:
            DBSession.delete(ulist)
            DBSession.flush()
            DBSession.refresh(mylist)
            self.request.session.flash("warning;User removed")
        schema = ListUserAddSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('users_list_add', listid=listid), buttons=('Add User',))
        return dict(mylist=mylist, form=form.render())


    @view_config(route_name='users_list_add', permission='admin', renderer='list_users.mako')
    def users_list_add(self):
        listid = self.request.matchdict['listid']
        mylist = DBSession.query(User).get(listid)
        userid = self.request.POST.get('sext', None)
        userid = userid.split(" ")[0]
        user = DBSession.query(User).filter_by(extension=userid).first()
        msg = None
        for i in mylist.members:
            if i.extension == userid:
                msg = "warning;User Already Exists in the list"
                self.request.session.flash(msg)

        if not user:
            msg="danger;Invalid Extension %s" % userid
            self.request.session.flash(msg)
        if not msg:
            userlist = UserList()
            userlist.user_id = user.id
            userlist.list_id = mylist.id
            DBSession.add(userlist)
            DBSession.flush()
            DBSession.refresh(mylist)
            msg="success;%s added" % user.name
            self.request.session.flash(msg)

        schema = ListUserAddSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('users_list_add', listid=listid), buttons=('Add User',))
        return dict(mylist=mylist, form=form.render())
            
    @view_config(route_name='auto_complete_users', permission='admin', renderer='json')
    def auto_complete_users(self):
        text = self.request.params.get('term', None)
        users = []
        if text:
            users = DBSession.query(User).filter(User.extension.like('%' + text + '%')).all()
        ret = []
        for i in users:
            if i.is_list == 0:
                ret.append("%s %s" % (i.extension, i.name))
        return ret

    @view_config(route_name='users_list', permission='admin', renderer='list_users.mako')
    def users_list(self):
        listid = self.request.matchdict['listid']
        mylist = DBSession.query(User).get(listid)
        schema = ListUserAddSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url('users_list_add', listid=listid), buttons=('Add User',))
        return dict(mylist=mylist, form=form.render(appstruct=mylist.__dict__))
