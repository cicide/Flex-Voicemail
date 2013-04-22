# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function,
    unicode_literals)
from pyramid.security   import unauthenticated_userid
from .models.models import (
    User,
    DBSession,
    )

def get_user(request):
    userid = unauthenticated_userid(request)

    if userid is not None:
        return DBSession.query(User).filter(User.id == userid).first()

    return None

