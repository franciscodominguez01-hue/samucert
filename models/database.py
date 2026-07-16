from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default='admin')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS usuarios(
        id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, 
        password_hash VARCHAR(255) NOT NULL, rol VARCHAR(20) DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS programas(
        id SERIAL PRIMARY KEY, nombre VARCHAR(150) NOT NULL, abreviatura CHAR(4) UNIQUE NOT NULL, 
        creditos VARCHAR(50) NOT NULL DEFAULT '120 horas',
        duracion VARCHAR(50) NOT NULL DEFAULT '6 meses',
        activo BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS contadores(
        programa_id INTEGER PRIMARY KEY, ultimo_numero INTEGER DEFAULT 0, año_actual INTEGER DEFAULT 2026,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(programa_id) REFERENCES programas(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS diplomas(
        id SERIAL PRIMARY KEY, programa_id INTEGER NOT NULL, nombre_alumno VARCHAR(150) NOT NULL,
        consecutivo VARCHAR(20) UNIQUE NOT NULL, codigo_verif VARCHAR(36) UNIQUE NOT NULL,
        estado VARCHAR(20) DEFAULT 'ACTIVO', 
        fecha_emision DATE DEFAULT CURRENT_DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(programa_id) REFERENCES programas(id)
    );
    CREATE TABLE IF NOT EXISTS diplomas_anulacion(
        id SERIAL PRIMARY KEY, diploma_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL,
        motivo TEXT NOT NULL, fecha_anulacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(diploma_id) REFERENCES diplomas(id),
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    );
    CREATE TABLE IF NOT EXISTS diplomas_auditoria(
        id SERIAL PRIMARY KEY, diploma_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL,
        campo_modificado VARCHAR(50) NOT NULL, valor_anterior TEXT, valor_nuevo TEXT,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(diploma_id) REFERENCES diplomas(id),
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    );
    """
    db.session.execute(text(sql))
    db.session.commit()
    print("✅ Tablas de base de datos creadas/verificadas correctamente.")

def create_default_users():
    """Crea los usuarios por defecto con hashes válidos"""
    users_data = [
        {'username': 'admin', 'rol': 'admin', 'password': 'admin123'},
        {'username': 'operador', 'rol': 'operador', 'password': 'operador123'},
        {'username': 'auditor', 'rol': 'auditor', 'password': 'auditor123'}
    ]
    
    for data in users_data:
        if not User.query.filter_by(username=data['username']).first():
            user = User(username=data['username'], rol=data['rol'])
            user.set_password(data['password'])
            db.session.add(user)
            db.session.commit()
            print(f"✅ Usuario '{data['username']}' creado con rol '{data['rol']}'")
