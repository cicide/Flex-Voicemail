
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

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
        
    
    