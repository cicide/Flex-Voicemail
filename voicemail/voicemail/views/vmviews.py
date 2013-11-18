import os
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import FileResponse, Response

import datetime
import sqlalchemy

from ..models.models import (
    DBSession,
    User,
    Voicemail,
    )

class VoicemailView(object):
    
    def __init__(self, request):
        self.request = request
        
    @view_config(route_name='view_vm', renderer='vm_list.mako')
    def vm_list(self):
        logged_user = self.request.user
        voice_mails = DBSession.query(Voicemail).filter_by(user_id=logged_user.id).filter_by(status=0).order_by(Voicemail.is_read, Voicemail.create_date.desc())
        return dict(voicemails = voice_mails)
    

    @view_config(route_name='play_vm', renderer='vm_list.mako')
    def vm_play(self):
        logged_user = self.request.user
        vm_id = self.request.matchdict['vmid']
        vm = None
        try:
            vm = DBSession.query(Voicemail).filter_by(id=vm_id, user_id=logged_user.id).first()
        except:
            pass
        finally:
            if vm is None:
                return HTTPNotFound()
        # putting a hack here 
        # remove the file:/ from the file name
        path = vm.path.replace('file:/', '')
        if not os.path.exists(path):
            return 
        return FileResponse(path, self.request)

    
    @view_config(route_name='download_vm')
    def vm_download(self):
        logged_user = self.request.user
        vm_id = self.request.matchdict['vmid']
        vm = None
        try:
            vm = DBSession.query(Voicemail).filter_by(id=vm_id, user_id=logged_user.id).first()
        except:
            pass
        finally:
            if vm is None:
                return HTTPNotFound()
        filename = vm.path.split('/')[len(vm.path.split('/'))-1:].pop()
        response = Response(
                             content_disposition='attachment; filename=%s' % (filename),
                             content_encoding='binary',
                             body_file = open(vm.path)
                             )
        return response
    

    @view_config(route_name='delete_vm')
    def vm_delete(self):
        logged_user = self.request.user
        vm_id = self.request.matchdict['vmid']
        vm = None
        try:
            vm = DBSession.query(Voicemail).filter_by(id=vm_id, user_id=logged_user.id).first()
            vm.status = 1
            vm.deleted_on = datetime.datetime.utcnow()
            DBSession.add(vm)
        except:
            pass
        finally:
            if vm is None:
                return HTTPNotFound()
        return HTTPFound(location = self.request.route_url('view_vm'))

    
    @view_config(route_name='search_vm', renderer='vm_list.mako')
    def search_vm(self):
        voice_mails = None
        keyword = self.request.POST.get('search',None)
        query = DBSession.query(Voicemail).filter_by(status = 0)
        if not self.request.user.role or self.request.user.role[0].role_name!='Admin':
            query = query.filter_by(user_id=self.request.user.id)
        query = query.filter(sqlalchemy.or_(Voicemail.cid_number.like('%' + keyword + '%'), Voicemail.cid_number.like('%' + keyword + '%')))
        query = query.order_by(Voicemail.is_read, Voicemail.create_date.desc())
        voice_mails = query.all()
        return dict(voicemails=voice_mails)
    
