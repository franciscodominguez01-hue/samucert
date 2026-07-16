from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def role_required(*required_roles):
    """
    Decorador para restringir acceso por rol(es)
    Uso: 
      @role_required('admin')  # Solo admin
      @role_required('admin', 'operador')  # Admin u operador
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if current_user.rol not in required_roles:
                flash('No tienes permisos para acceder a esta sección', 'danger')
                return redirect(url_for('reportes.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
