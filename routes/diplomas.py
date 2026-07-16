import io
import uuid
import zipfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session, jsonify
from flask_login import login_required, current_user
from models.database import db
from sqlalchemy import text
import qrcode
import pandas as pd
from utils.roles import role_required

diplomas_bp = Blueprint('diplomas', __name__, url_prefix='/diplomas')

def obtener_siguiente_consecutivo(programa_id):
    result = db.session.execute(
        text("SELECT ultimo_numero FROM contadores WHERE programa_id = :pid FOR UPDATE"),
        {"pid": programa_id}
    ).fetchone()
    if not result: raise Exception("No existe contador para este programa")
    
    nuevo_numero = result[0] + 1
    db.session.execute(
        text("UPDATE contadores SET ultimo_numero = :nuevo, updated_at = CURRENT_TIMESTAMP WHERE programa_id = :pid"),
        {"nuevo": nuevo_numero, "pid": programa_id}
    )
    prog = db.session.execute(text("SELECT abreviatura FROM programas WHERE id = :pid"), {"pid": programa_id}).fetchone()
    return f"{prog[0]}-{nuevo_numero:05d}"

def generar_qr(codigo_verif, consecutivo=None):
    """Genera el QR en memoria con el consecutivo visible debajo"""
    from PIL import Image, ImageDraw, ImageFont
    import io
    
    # Generar el QR
    url_validacion = f"{request.host_url.rstrip('/')}/validar/{codigo_verif}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url_validacion)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a imagen PIL
    qr_pil = qr_img.convert('RGB')
    
    # Si tenemos el consecutivo, crear imagen compuesta con texto
    if consecutivo:
        # Dimensiones
        qr_width, qr_height = qr_pil.size
        text_height = 80  # Espacio generoso para texto de 48px  # Más espacio para texto grande  # Espacio para el texto
        total_height = qr_height + text_height
        
        # Crear imagen blanca más grande
        img_compuesta = Image.new('RGB', (qr_width, total_height), 'white')
        
        # Pegar el QR en la parte superior
        img_compuesta.paste(qr_pil, (0, 0))
        
        # Agregar el texto del consecutivo debajo
        draw = ImageDraw.Draw(img_compuesta)
        
        # Intentar usar una fuente más grande, si no, usar la default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except:
            font = ImageFont.load_default()
        
        # Centrar el texto
        text_bbox = draw.textbbox((0, 0), consecutivo, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (qr_width - text_width) // 2
        text_y = qr_height + 16  # Centrado vertical  # Centrado vertical en el espacio adicional
        
        # Dibujar el texto en negro
        draw.text((text_x, text_y), consecutivo, fill='black', font=font)
        
        # Guardar en memoria
        img_io = io.BytesIO()
        img_compuesta.save(img_io, 'PNG')
        img_io.seek(0)
        return img_io
    else:
        # Si no hay consecutivo, devolver solo el QR
        img_io = io.BytesIO()
        qr_pil.save(img_io, 'PNG')
        img_io.seek(0)
        return img_io

def alumno_existe_en_programa(programa_id, nombre_alumno, exclude_id=None):
    query = "SELECT id FROM diplomas WHERE programa_id = :pid AND LOWER(nombre_alumno) = LOWER(:nombre) AND estado = 'ACTIVO'"
    params = {"pid": programa_id, "nombre": nombre_alumno.strip()}
    if exclude_id:
        query += " AND id != :eid"
        params["eid"] = exclude_id
    return db.session.execute(text(query), params).fetchone() is not None

@diplomas_bp.route('/')
@login_required
def index():
    return redirect(url_for('diplomas.activos'))

@diplomas_bp.route('/activos')
@login_required
def activos():
    return render_template('diplomas/activos.html')

@diplomas_bp.route('/generar', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'operador')
def generar():
    if request.method == 'POST':
        programa_id = request.form.get('programa_id')
        nombre_alumno = request.form.get('nombre_alumno').strip().title()
        
        try:
            if alumno_existe_en_programa(programa_id, nombre_alumno):
                flash(f'⚠️ El alumno "{nombre_alumno}" YA TIENE un diploma activo en este programa.', 'warning')
                return redirect(url_for('diplomas.generar'))
            
            consecutivo = obtener_siguiente_consecutivo(programa_id)
            codigo_verif = str(uuid.uuid4())
            
            # STATELESS: Solo guardamos en BD, NO generamos ni guardamos el QR en disco aún
            db.session.execute(
                text("""INSERT INTO diplomas (programa_id, nombre_alumno, consecutivo, codigo_verif, estado)
                        VALUES (:pid, :nombre, :consec, :codigo, 'ACTIVO')"""),
                {"pid": programa_id, "nombre": nombre_alumno, "consec": consecutivo, "codigo": codigo_verif}
            )
            db.session.commit()
            
            flash(f'Diploma generado. Consecutivo: {consecutivo}', 'success')
            return redirect(url_for('diplomas.generar'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    programas = db.session.execute(
        text("SELECT id, nombre, abreviatura, creditos, duracion FROM programas WHERE activo = TRUE ORDER BY nombre")
    ).fetchall()
    return render_template('diplomas/generar.html', programas=programas)

@diplomas_bp.route('/editar/<int:diploma_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'operador')
def editar(diploma_id):
    diploma = db.session.execute(text("SELECT * FROM diplomas WHERE id = :id"), {"id": diploma_id}).fetchone()
    if not diploma:
        flash('Diploma no encontrado', 'danger')
        return redirect(url_for('diplomas.activos'))
    
    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre_alumno').strip().title()
        if nuevo_nombre == diploma.nombre_alumno:
            flash('No se realizaron cambios', 'info')
            return redirect(url_for('diplomas.activos'))
        
        try:
            if alumno_existe_en_programa(diploma.programa_id, nuevo_nombre, exclude_id=diploma_id):
                flash(f'⚠️ Ya existe otro diploma activo para "{nuevo_nombre}" en este programa.', 'warning')
                return redirect(url_for('diplomas.editar', diploma_id=diploma_id))
            
            db.session.execute(
                text("UPDATE diplomas SET nombre_alumno = :nombre, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"nombre": nuevo_nombre, "id": diploma_id}
            )
            db.session.execute(
                text("""INSERT INTO diplomas_auditoria (diploma_id, usuario_id, campo_modificado, valor_anterior, valor_nuevo)
                        VALUES (:did, :uid, 'nombre_alumno', :anterior, :nuevo)"""),
                {"did": diploma_id, "uid": current_user.id, "anterior": diploma.nombre_alumno, "nuevo": nuevo_nombre}
            )
            db.session.commit()
            flash(f'Nombre actualizado correctamente', 'success')
            return redirect(url_for('diplomas.activos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al editar: {str(e)}', 'danger')
    
    programa = db.session.execute(
        text("SELECT nombre, creditos, duracion FROM programas WHERE id = :pid"),
        {"pid": diploma.programa_id}
    ).fetchone()
    return render_template('diplomas/editar.html', diploma=diploma, programa=programa)

@diplomas_bp.route('/anular/<int:diploma_id>', methods=['POST'])
@login_required
@role_required('admin', 'operador')
def anular(diploma_id):
    motivo = request.form.get('motivo', '').strip()
    if len(motivo) < 10:
        flash('El motivo debe tener al menos 10 caracteres', 'danger')
        return redirect(url_for('diplomas.activos'))
    try:
        db.session.execute(text("UPDATE diplomas SET estado = 'ANULADO', updated_at = CURRENT_TIMESTAMP WHERE id = :did"), {"did": diploma_id})
        db.session.execute(
            text("INSERT INTO diplomas_anulacion (diploma_id, usuario_id, motivo, fecha_anulacion) VALUES (:did, :uid, :motivo, CURRENT_TIMESTAMP)"),
            {"did": diploma_id, "uid": current_user.id, "motivo": motivo}
        )
        db.session.commit()
        flash('Diploma anulado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('diplomas.activos'))

@diplomas_bp.route('/generar-masivo', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'operador')
def generar_masivo():
    if request.method == 'POST':
        programa_id = request.form.get('programa_id')
        archivo = request.files.get('archivo_excel')
        if not archivo or not archivo.filename.endswith(('.xlsx', '.xls')):
            flash('Archivo Excel inválido', 'danger')
            return redirect(url_for('diplomas.generar_masivo'))
        
        try:
            df = pd.read_excel(archivo)
            if 'nombre_alumno' not in df.columns:
                raise Exception("El archivo debe tener la columna 'nombre_alumno'")
            
            diplomas_generados = []
            consecutivos_generados = []
            
            for _, row in df.iterrows():
                nombre = str(row['nombre_alumno']).strip().title()
                if not nombre: continue
                if alumno_existe_en_programa(programa_id, nombre): continue
                
                consecutivo = obtener_siguiente_consecutivo(programa_id)
                codigo_verif = str(uuid.uuid4())
                
                # STATELESS: Solo BD, sin escritura en disco
                db.session.execute(
                    text("""INSERT INTO diplomas (programa_id, nombre_alumno, consecutivo, codigo_verif, estado)
                            VALUES (:pid, :nombre, :consec, :codigo, 'ACTIVO')"""),
                    {"pid": programa_id, "nombre": nombre, "consec": consecutivo, "codigo": codigo_verif}
                )
                diplomas_generados.append({
                    'consecutivo': consecutivo,
                    'codigo_verif': codigo_verif
                })
                consecutivos_generados.append(consecutivo)
            
            db.session.commit()
            
            # GENERAR Y DESCARGAR ZIP AUTOMÁTICAMENTE (STATELESS)
            if diplomas_generados:
                memory_file = io.BytesIO()
                with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for d in diplomas_generados:
                        qr_img = generar_qr(d['codigo_verif'])
                        zf.writestr(f"{d['consecutivo']}.png", qr_img.read())
                
                memory_file.seek(0)
                flash(f'{len(diplomas_generados)} diplomas generados exitosamente. Descargando QRs...', 'success')
                
                return send_file(
                    memory_file,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f'samucert_{len(diplomas_generados)}_diplomas.zip'
                )
            else:
                flash('No se generaron diplomas (posibles duplicados)', 'warning')
                return redirect(url_for('diplomas.generar_masivo'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    programas = db.session.execute(
        text("SELECT id, nombre, creditos, duracion FROM programas WHERE activo = TRUE ORDER BY nombre")
    ).fetchall()
    return render_template('diplomas/generar_masivo.html', programas=programas)

@diplomas_bp.route('/descargar-seleccionados', methods=['POST'])
@login_required
@role_required('admin', 'operador')
def descargar_seleccionados():
    """Genera ZIP en memoria SOLO con los diplomas seleccionados (Máx 50)"""
    diploma_ids = request.form.getlist('diploma_ids')
    
    if not diploma_ids:
        flash('No has seleccionado ningún diploma', 'warning')
        return redirect(url_for('diplomas.activos'))
    
    if len(diploma_ids) > 50:
        flash('⚠️ Límite excedido: Puedes descargar un máximo de 50 diplomas a la vez para optimizar el servidor.', 'danger')
        return redirect(url_for('diplomas.activos'))
    
    # Construir consulta dinámica segura
    placeholders = ','.join([f':id{i}' for i in range(len(diploma_ids))])
    params = {f'id{i}': int(d_id) for i, d_id in enumerate(diploma_ids)}
    
    query = f"SELECT consecutivo, codigo_verif FROM diplomas WHERE id IN ({placeholders}) AND estado = 'ACTIVO'"
    diplomas = db.session.execute(text(query), params).fetchall()
    
    if not diplomas:
        flash('No se encontraron diplomas activos en la selección', 'warning')
        return redirect(url_for('diplomas.activos'))
    
    # Generar ZIP en memoria (STATELESS)
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d in diplomas:
            qr_img = generar_qr(d.codigo_verif, d.consecutivo) # Se genera al vuelo con la URL real del servidor
            zf.writestr(f"{d.consecutivo}.png", qr_img.read())
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'samucert_{len(diplomas)}_diplomas.zip'
    )

@login_required
@role_required('admin', 'operador')
def anulados():
    anulados_list = db.session.execute(
        text("""SELECT d.consecutivo, d.nombre_alumno, d.fecha_emision, da.motivo, da.fecha_anulacion, u.username
                FROM diplomas_anulacion da JOIN diplomas d ON da.diploma_id = d.id JOIN usuarios u ON da.usuario_id = u.id
                ORDER BY da.fecha_anulacion DESC""")
    ).fetchall()
    return render_template('diplomas/anulados.html', anulados=anulados_list)

@diplomas_bp.route('/api/activos')
@login_required
def api_activos():
    result = db.session.execute(
        text("""SELECT d.id, d.consecutivo, d.nombre_alumno, d.fecha_emision, p.nombre as programa_nombre
                FROM diplomas d JOIN programas p ON d.programa_id = p.id WHERE d.estado = 'ACTIVO'""")
    )
    diplomas_list = []
    for row in result:
        diplomas_list.append({
            'id': row.id,
            'consecutivo': row.consecutivo,
            'nombre_alumno': row.nombre_alumno,
            'fecha_emision': row.fecha_emision.strftime('%Y-%m-%d') if row.fecha_emision else '',
            'programa_nombre': row.programa_nombre
        })
    return jsonify(diplomas_list)

@diplomas_bp.route('/descargar-plantilla')
@login_required
@role_required('admin', 'operador')
def descargar_plantilla():
    """Descarga plantilla de Excel simplificada (solo nombre_alumno)"""
    df = pd.DataFrame(columns=['nombre_alumno'])
    df.loc[0] = ['Juan Carlos Pérez García']
    df.loc[1] = ['María Fernanda López']
    df.loc[2] = ['Roberto Sánchez Hernández']
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Diplomas', index=False)
    output.seek(0)
    return send_file(
        output, 
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
        as_attachment=True, 
        download_name='plantilla_diplomas.xlsx'
    )

@diplomas_bp.route('/anulados')
@login_required
@role_required('admin', 'operador')
def anulados():
    """Lista de diplomas anulados con auditoría"""
    anulados_list = db.session.execute(
        text("""SELECT d.consecutivo, d.nombre_alumno, d.fecha_emision, da.motivo, da.fecha_anulacion, u.username
                FROM diplomas_anulacion da 
                JOIN diplomas d ON da.diploma_id = d.id 
                JOIN usuarios u ON da.usuario_id = u.id
                ORDER BY da.fecha_anulacion DESC""")
    ).fetchall()
    return render_template('diplomas/anulados.html', anulados=anulados_list)

@diplomas_bp.route('/descargar-zip')
@login_required
@role_required('admin')  # SOLO ADMIN por seguridad
def descargar_zip():
    """
    Descarga ZIP de los últimos 100 activos (SOLO para emergencias)
    LÍMITE: 100 diplomas máx para no saturar RAM
    """
    flash('⚠️ Función limitada: Solo se descargarán los últimos 100 diplomas activos. Usa "Descargar Seleccionados" para más control.', 'warning')
    
    diplomas = db.session.execute(
        text("SELECT consecutivo, codigo_verif FROM diplomas WHERE estado = 'ACTIVO' ORDER BY id DESC LIMIT 100")
    ).fetchall()
    
    if not diplomas:
        flash('No hay diplomas activos', 'warning')
        return redirect(url_for('diplomas.activos'))
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d in diplomas:
            qr_img = generar_qr(d.codigo_verif, d.consecutivo)
            zf.writestr(f"{d.consecutivo}.png", qr_img.read())
    
    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name='diplomas_recientes.zip')
