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

from sqlalchemy import exc
from sqlalchemy import event
from sqlalchemy.pool import Pool

@event.listens_for(Pool, "checkout")
def ping_connection(dbapi_connection, connection_record, connection_proxy):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1") 
    except:
        # optional - dispose the whole pool
        # instead of invalidating one at a time
        # connection_proxy._pool.dispose()
        # raise DisconnectionError - pool will try 
        # connecting again up to three times before raising.
        raise exc.DisconnectionError()
    cursor.close()


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
    config.add_route('delete_user', '/user/delete')
    config.add_route('auto_complete_users', '/list/users')
    config.add_route('add_list', '/list/add')
    config.add_route('edit_list', '/list/edit/{listid}')
    config.add_route('users_list', '/list/users/{listid}')
    config.add_route('users_list_add', '/list/users/{listid}/add')
    config.add_route('users_list_remove', '/list/users/{listid}/remove/{userid}')
    config.add_route('list_lists', '/list/lists')
    config.add_route('delete_list', '/list/delete')
    config.add_route('edit_vmpref', '/vmpref/edit/{userid}')
    config.add_route('edit_own_vmpref', '/vmpref/edit')
    config.add_route('view_vmpref', '/user/pref')
    config.add_route('edit_admin', '/admin/edit')
    config.add_route('view_vm', '/vm/view')
    config.add_route('play_vm', '/vm/play/{vmid}')
    config.add_route('download_vm', '/vm/download/{vmid}')
    config.add_route('delete_vm', '/vm/delete/{vmid}')
    config.add_route('search_vm', '/search')
    config.add_route('startcall', '/startcall')
    config.add_route('savemessage', '/savemessage')
    config.add_route('handlekey', '/handlekey')
    config.add_route('handlelogin', '/handlelogin')
    config.add_route('invalidmessage', '/invalidmessage')
    config.scan()
    return config.make_wsgi_app()

