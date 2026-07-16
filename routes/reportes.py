from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models.database import db
from sqlalchemy import text
from datetime import datetime
from utils.roles import role_required

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

@reportes_bp.route('/')
@login_required
def dashboard():
    año_actual = datetime.now().year
    
    # 1. Totales Generales
    total_activos = db.session.execute(text("SELECT COUNT(*) FROM diplomas WHERE estado = 'ACTIVO'")).scalar()
    total_anulados = db.session.execute(text("SELECT COUNT(*) FROM diplomas WHERE estado = 'ANULADO'")).scalar()
    total_programas = db.session.execute(text("SELECT COUNT(*) FROM programas WHERE activo = TRUE")).scalar()
    
    # 2. Emisiones por Programa (Año Actual)
    emisiones_anio = db.session.execute(
        text("""SELECT p.nombre, p.abreviatura, COUNT(d.id) as total
                FROM programas p
                LEFT JOIN diplomas d ON p.id = d.programa_id AND EXTRACT(YEAR FROM d.fecha_emision) = :año
                WHERE p.activo = TRUE
                GROUP BY p.id, p.nombre, p.abreviatura
                ORDER BY total DESC"""),
        {"año": año_actual}
    ).fetchall()
    
    # 3. Últimos 5 movimientos de auditoría (SOLO si es auditor)
    auditoria_reciente = []
    if current_user.rol == 'auditor':
        auditoria_reciente = db.session.execute(
            text("""SELECT d.consecutivo, d.nombre_alumno, a.campo_modificado, 
                           a.valor_anterior, a.valor_nuevo, a.fecha_modificacion, u.username
                    FROM diplomas_auditoria a
                    JOIN diplomas d ON a.diploma_id = d.id
                    JOIN usuarios u ON a.usuario_id = u.id
                    ORDER BY a.fecha_modificacion DESC LIMIT 5""")
        ).fetchall()

    return render_template('reportes/dashboard.html', 
                           total_activos=total_activos,
                           total_anulados=total_anulados,
                           total_programas=total_programas,
                           emisiones_anio=emisiones_anio,
                           auditoria_reciente=auditoria_reciente,
                           año_actual=año_actual)

@reportes_bp.route('/auditoria')
@login_required
@role_required('auditor')  # <-- SOLO AUDITORES
def auditoria_completa():
    """Reporte completo de auditoría (SOLO para rol auditor)"""
    movimientos = db.session.execute(
        text("""SELECT 
                    CASE 
                        WHEN da.id IS NOT NULL THEN 'ANULACIÓN'
                        ELSE 'EDICIÓN'
                    END as tipo,
                    d.consecutivo, 
                    d.nombre_alumno,
                    COALESCE(da.motivo, aud.campo_modificado || ': ' || aud.valor_anterior || ' -> ' || aud.valor_nuevo) as detalle,
                    u.username,
                    COALESCE(da.fecha_anulacion, aud.fecha_modificacion) as fecha
                FROM diplomas d
                LEFT JOIN diplomas_anulacion da ON d.id = da.diploma_id
                LEFT JOIN diplomas_auditoria aud ON d.id = aud.diploma_id
                JOIN usuarios u ON (da.usuario_id = u.id OR aud.usuario_id = u.id)
                WHERE da.id IS NOT NULL OR aud.id IS NOT NULL
                ORDER BY fecha DESC""")
    ).fetchall()
    
    return render_template('reportes/auditoria.html', movimientos=movimientos)
