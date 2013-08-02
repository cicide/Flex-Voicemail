from pyramid_beaker import session_factory_from_settings
from pyramid.config import Configurator
from sqlalchemy import engine_from_config
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from voicemail.security import groupfinder
from voicemail.lib import get_user

from .models.models import (
    DBSession,
    Base,
    )

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    session_factory = session_factory_from_settings(settings)
    authn_policy = AuthTktAuthenticationPolicy( 'sosecret', callback=groupfinder, hashalg='sha512')
    authz_policy = ACLAuthorizationPolicy()
    config = Configurator(settings=settings, root_factory='voicemail.models.models.RootFactory')
    config.set_request_property(get_user, str('user'), reify=True)
    config.include('bag.web.pyramid.flash_msg')
    config.set_session_factory(session_factory)
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.add_static_view('static', 'static', cache_max_age=3600)
    # Adding the static resources from Deform
    config.add_static_view('deform_static', 'deform:static', cache_max_age=3600)
    config.add_static_view('deform_bootstrap_static', 'deform_bootstrap:static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('add_user', '/user/add')
    config.add_route('edit_user', '/user/edit/{userid}')
    config.add_route('list_users', '/users/list/{type}')
    config.add_route('delete_user', '/user/delete/{userid}')
    config.add_route('edit_vmpref', '/vmpref/edit/{userid}')
    config.add_route('edit_admin', '/admin/edit')
    config.add_route('view_vm', '/vm/view')
    config.add_route('play_vm', '/vm/play/{vmid}')
    config.add_route('download_vm', '/vm/download/{vmid}')
    config.add_route('delete_vm', '/vm/delete/{vmid}')
    config.add_route('startcall', '/startcall')
    config.add_route('savemessage', '/savemessage')
    config.add_route('handlekey', '/handlekey')
    config.add_route('invalidmessage', '/invalidmessage')
    config.scan()
    return config.make_wsgi_app()

