from flask import Blueprint, render_template
from models.database import db
from sqlalchemy import text

public_bp = Blueprint('public', __name__)

@public_bp.route('/validar/<codigo_verif>')
def validar(codigo_verif):
    """RF17: Validador público sin login"""
    # Buscar el diploma
    res = db.session.execute(
        text("""SELECT d.estado, d.nombre_alumno, d.consecutivo, d.fecha_emision, p.nombre as programa
                FROM diplomas d 
                JOIN programas p ON d.programa_id = p.id 
                WHERE d.codigo_verif = :cod"""),
        {"cod": codigo_verif}
    ).fetchone()

    if not res:
        # No existe (Posible fraude)
        return render_template('public/validar.html', 
                               status='not_found', codigo=codigo_verif)

    if res.estado == 'ANULADO':
        # Obtener motivo de anulación
        anula = db.session.execute(
            text("""SELECT motivo, fecha_anulacion FROM diplomas_anulacion 
                    WHERE diploma_id = (SELECT id FROM diplomas WHERE codigo_verif = :cod)"""),
            {"cod": codigo_verif}
        ).fetchone()
        
        motivo = anula.motivo if anula else "Sin motivo registrado en el sistema"
        fecha_anulacion = anula.fecha_anulacion if anula else None
        
        return render_template('public/validar.html', 
                               status='annulled', 
                               consecutivo=res.consecutivo, 
                               nombre=res.nombre_alumno, 
                               motivo=motivo, 
                               fecha_anulacion=fecha_anulacion)

    # Activo (Válido)
    return render_template('public/validar.html', 
                           status='active', 
                           consecutivo=res.consecutivo, 
                           nombre=res.nombre_alumno, 
                           programa=res.programa, 
                           fecha=res.fecha_emision)
