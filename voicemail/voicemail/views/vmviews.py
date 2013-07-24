from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import FileResponse

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
        return FileResponse(vm.path, self.request) if vm else HTTPNotFound()
        
    