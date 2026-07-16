from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models.database import db
from sqlalchemy import text
from utils.roles import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@role_required('admin')  # SOLO ADMIN
def index():
    return redirect(url_for('admin.programas'))

@admin_bp.route('/programas')
@login_required
@role_required('admin')  # SOLO ADMIN
def programas():
    programas_list = db.session.execute(
        text("SELECT id, nombre, abreviatura, creditos, duracion, activo FROM programas ORDER BY nombre")
    ).fetchall()
    return render_template('admin/programas.html', programas=programas_list)

@admin_bp.route('/programas/crear', methods=['POST'])
@login_required
@role_required('admin')  # SOLO ADMIN
def crear_programa():
    nombre = request.form.get('nombre')
    abreviatura = request.form.get('abreviatura').upper()
    creditos = request.form.get('creditos', '120 horas')
    duracion = request.form.get('duracion', '6 meses')
    
    try:
        db.session.execute(
            text("""INSERT INTO programas (nombre, abreviatura, creditos, duracion, activo) 
                    VALUES (:nombre, :abreviatura, :creditos, :duracion, TRUE)"""),
            {"nombre": nombre, "abreviatura": abreviatura, "creditos": creditos, "duracion": duracion}
        )
        result = db.session.execute(
            text("SELECT id FROM programas WHERE abreviatura = :abreviatura"), 
            {"abreviatura": abreviatura}
        )
        programa_id = result.fetchone()[0]
        
        db.session.execute(
            text("INSERT INTO contadores (programa_id, ultimo_numero, año_actual) VALUES (:pid, 0, 2026)"),
            {"pid": programa_id}
        )
        db.session.commit()
        flash('Programa creado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear el programa: {str(e)}', 'danger')
        
    return redirect(url_for('admin.programas'))

@admin_bp.route('/programas/toggle/<int:programa_id>')
@login_required
@role_required('admin')  # SOLO ADMIN
def toggle_programa(programa_id):
    """Activar/Desactivar programa"""
    db.session.execute(
        text("UPDATE programas SET activo = NOT activo WHERE id = :pid"),
        {"pid": programa_id}
    )
    db.session.commit()
    flash('Estado del programa actualizado', 'success')
    return redirect(url_for('admin.programas'))
