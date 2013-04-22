from .models.models import User, UserRole, DBSession

def groupfinder(userid, request):
    roles = DBSession.query(UserRole).filter_by(user_id = userid).all()

    if roles is not None and len(roles) != 0:
        principals = []
        for role in roles:
            if role.role_name == "Admin":
                principals.append('g:admin')
        return principals
