import uuid
import re
from flask import Blueprint, render_template, request
from models.database import db
from sqlalchemy import text

validador_bp = Blueprint('validador', __name__)

# Patrón regex para validar formato: 4 letras mayúsculas + guion + 5 dígitos
PATRON_CONSECUTIVO = r'^[A-Z]{4}-\d{5}$'

@validador_bp.route('/validar', methods=['GET'])
def validar_formulario():
    """Página pública de búsqueda manual de diplomas"""
    codigo = request.args.get('codigo', '').strip().upper()
    
    if not codigo:
        return render_template('validador/validar.html', diploma=None, error=None, codigo='', error_formato=False)
    
    # Validar formato del consecutivo
    if not re.match(PATRON_CONSECUTIVO, codigo) and not es_uuid_valido(codigo):
        return render_template(
            'validador/validar.html', 
            diploma=None, 
            error='Formato inválido', 
            codigo=codigo,
            error_formato=True
        )
    
    return buscar_diploma(codigo)

@validador_bp.route('/validar/<codigo>')
def validar_diploma(codigo):
    """Valida un diploma por código (UUID o consecutivo)"""
    return buscar_diploma(codigo.upper())

def es_uuid_valido(codigo):
    """Verifica si el código es un UUID válido"""
    try:
        uuid.UUID(codigo)
        return True
    except ValueError:
        return False

def buscar_diploma(codigo):
    """Función auxiliar para buscar diploma por UUID o consecutivo"""
    diploma = None
    error = None
    
    # Detectar si es UUID o consecutivo
    es_uuid = es_uuid_valido(codigo)
    
    try:
        if es_uuid:
            # Búsqueda por código de verificación (QR)
            result = db.session.execute(
                text("""SELECT d.consecutivo, d.nombre_alumno, d.estado, d.fecha_emision,
                               p.nombre as programa_nombre, p.creditos, p.duracion, d.codigo_verif
                        FROM diplomas d
                        JOIN programas p ON d.programa_id = p.id
                        WHERE d.codigo_verif = :codigo"""),
                {"codigo": codigo}
            ).fetchone()
        else:
            # Búsqueda por consecutivo (ej: INSI-00002)
            result = db.session.execute(
                text("""SELECT d.consecutivo, d.nombre_alumno, d.estado, d.fecha_emision,
                               p.nombre as programa_nombre, p.creditos, p.duracion, d.codigo_verif
                        FROM diplomas d
                        JOIN programas p ON d.programa_id = p.id
                        WHERE d.consecutivo = :codigo"""),
                {"codigo": codigo}
            ).fetchone()
        
        if result:
            diploma = {
                'consecutivo': result.consecutivo,
                'nombre_alumno': result.nombre_alumno,
                'estado': result.estado,
                'fecha_emision': result.fecha_emision.strftime('%d de %B de %Y') if result.fecha_emision else '',
                'programa_nombre': result.programa_nombre,
                'creditos': result.creditos,
                'duracion': result.duracion,
                'codigo_verif': result.codigo_verif
            }
        else:
            error = "No se encontró ningún diploma con ese código."
            
    except Exception as e:
        error = f"Error al validar: {str(e)}"
    
    return render_template('validador/validar.html', diploma=diploma, error=error, codigo=codigo, error_formato=False)
