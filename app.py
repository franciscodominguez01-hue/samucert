from flask import Flask, redirect, url_for, session
from flask_login import LoginManager
from config import Config
from models.database import db, init_db, create_default_users, User
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.diplomas import diplomas_bp
from routes.public import public_bp
from routes.reportes import reportes_bp  # <-- NUEVO

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config['SECRET_KEY']
    
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    with app.app_context():
        init_db()
        create_default_users()
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(diplomas_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(reportes_bp)  # <-- NUEVO
    
    @app.route('/')
    def index():
        return redirect(url_for('reportes.dashboard'))  # <-- Cambiado a Dashboard
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
