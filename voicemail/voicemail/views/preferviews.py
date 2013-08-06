import os
import ConfigParser
import deform
import logging
log = logging.getLogger(__name__)

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound, HTTPNotFound

from ..models.models import (
    DBSession,
    UserVmPref,
    )

from ..schemas import (
    VMPrefSchema,
    )

class VMPrefView(object):
    
    def __init__(self, request):
        self.request = request
    
    def create_vmpref(self,user):
        dirname = os.path.dirname
        SITE_ROOT = dirname(dirname(dirname(dirname(__file__))))
        path = os.path.join(SITE_ROOT,'app/etc/flexvmail.conf')
        config = ConfigParser.ConfigParser()
        config.read(path)
        vm_dir = config.get("sounds", 'vm_dir')
        directory = os.path.join(vm_dir,str(user.id))
        if not os.path.exists(directory):
            os.makedirs(directory)
        vmpref = DBSession.query(UserVmPref).filter_by(id=user.id).first()
        if vmpref is None:
            vmpref = UserVmPref(user_id=user.id, folder=directory)
            DBSession.add(vmpref)
            DBSession.flush()
        
    
    @view_config(route_name='edit_own_vmpref', renderer='vmpref_edit.mako')
    @view_config(route_name='edit_vmpref', permission='admin', renderer='vmpref_edit.mako')
    def edit_vmpref(self):
        userid = self.request.matchdict.get('userid',None)
        route_url = 'edit_vmpref'
        cancel_url = 'list_users'
        type = 'vmusers'
        if userid is None:
            userid = self.request.user.id
            route_url = 'edit_own_vmpref'
            cancel_url = 'view_vmpref'
            type = None
        vmpref = DBSession.query(UserVmPref).filter_by(user_id=userid).first()
        schema = VMPrefSchema().bind(request=self.request)
        form = deform.Form(schema, action=self.request.route_url(route_url, userid=userid), buttons=('Save','Cancel'))
        
        if 'Cancel' in self.request.params:
            return HTTPFound(location = self.request.route_url(cancel_url,type=type))
        
        if 'Save' in self.request.params:
            appstruct = None
            try:
                appstruct = form.validate(self.request.POST.items())
            except deform.ValidationFailure, e:
                log.exception('in form validated')
                return {'form':e.render()}
            
            vmpref.folder = appstruct['folder']
            vmpref.deliver_vm = appstruct['deliver_vm']
            vmpref.attach_vm = appstruct['attach_vm']
            vmpref.email = appstruct['email']
            vmpref.sms_addr = appstruct['sms_addr']
            vmpref.vm_greeting = appstruct['vm_greeting']
            vmpref.vm_name_recording = appstruct['vm_name_recording']
            DBSession.add(vmpref)
            DBSession.flush()
            return HTTPFound(location = self.request.route_url(cancel_url,type=type))
        return dict(form=form.render(appstruct=vmpref.__dict__))
    
    
    @view_config(route_name='view_vmpref', renderer='vmpref_detail.mako')
    def show_vmpref(self):
        userid = self.request.user.id
        vmpref = DBSession.query(UserVmPref).filter_by(user_id=userid).first()
        return dict(vmpref=vmpref.__dict__)
        
            
    