import os
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import FileResponse, Response

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
        voice_mails = DBSession.query(Voicemail).filter_by(user_id=logged_user.id)
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
        return FileResponse(vm.path, self.request)
    
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
            os.remove(vm.path)
            os.remove(vm.path.replace('.wav','.txt'))
            DBSession.delete(vm)
            DBSession.flush()
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
        if keyword.isdigit():
            if self.request.user.role and self.request.user.role[0].role_name=='Admin':
                voice_mails = DBSession.query(Voicemail).filter_by(cid_number=int(keyword)).all()
            else:
                voice_mails = DBSession.query(Voicemail).filter_by(user_id=self.request.user.id, cid_number=int(keyword)).all()
        else:
            if self.request.user.role and self.request.user.role[0].role_name=='Admin':
                voice_mails = DBSession.query(Voicemail).filter_by(cid_name=keyword).all()
            else:
                voice_mails = DBSession.query(Voicemail).filter_by(user_id=self.request.user.id, cid_name=keyword).all()
        return dict(voicemails=voice_mails)
    