import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfo

# Zona horaria oficial de Tuxtla Gutiérrez / Centro de México
TZ_MEXICO = ZoneInfo("America/Mexico_City")

def obtener_ahora():
    """Retorna datetime actual consciente de la zona horaria de México."""
    return datetime.datetime.now(TZ_MEXICO)

# Cargar variables de entorno
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from models import db, Sala, Area, Reservacion, Usuario, BloqueoTemporal
from sqlalchemy import not_, or_
from functools import wraps
import uuid
import datetime
import io
import threading
import mailer
from werkzeug.middleware.proxy_fix import ProxyFix

# ReportLab para PDFs
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "hackathon_ittg_secret_key_v2_ultra_secure")

# Soporte de Proxy para Railway (fuerza detección de HTTPS y cabeceras de proxy)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Conexión flexible (Railway o Local)
database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
if database_url:
    if database_url.startswith("mysql://"):
        database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    db_user = os.getenv("DB_USER", "root")
    db_pass = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "sistema_reservaciones_v2")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Mutex global para sincronización de sección crítica
reserva_lock = threading.Lock()

BLOQUES_HORARIOS = [
    ("08:00", "09:00"), ("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
    ("12:00", "13:00"), ("13:00", "14:00"), ("14:00", "15:00"), ("15:00", "16:00"),
    ("16:00", "17:00"), ("17:00", "18:00"), ("18:00", "19:00"), ("19:00", "20:00"),
    ("20:00", "21:00")
]

# --- FUNCIONES AUXILIARES ---

def actualizar_reservaciones_vencidas():
    """Actualiza en BD a 'CONCLUIDA' cualquier reserva activa cuya fecha u hora ya concluyó en México."""
    try:
        ahora = obtener_ahora()
        hoy = ahora.date()
        hora_actual = ahora.time()

        Reservacion.query.filter(
            Reservacion.estado == 'ACTIVA',
            Reservacion.fecha_reservacion < hoy
        ).update({'estado': 'CONCLUIDA'}, synchronize_session=False)

        Reservacion.query.filter(
            Reservacion.estado == 'ACTIVA',
            Reservacion.fecha_reservacion == hoy,
            Reservacion.hora_fin <= hora_actual
        ).update({'estado': 'CONCLUIDA'}, synchronize_session=False)

        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        
        
def generar_pdf_buffer(reserva):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    titulo = ParagraphStyle('T1', parent=styles['Heading1'], fontSize=15, leading=19, textColor=colors.HexColor('#0f172a'), alignment=1)
    sub = ParagraphStyle('T2', parent=styles['Normal'], fontSize=9.5, leading=13, textColor=colors.HexColor('#475569'), alignment=1)
    badge = ParagraphStyle('T3', parent=styles['Normal'], fontSize=11, leading=15, textColor=colors.HexColor('#1e40af'), alignment=1)

    story.append(Paragraph("INSTITUTO TECNOLÓGICO DE TUXTLA GUTIÉRREZ", titulo))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Sistema Institucional de Gestión y Reservación de Espacios", sub))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>COMPROBANTE OFICIAL DE RESERVACIÓN: {reserva.codigo_unico}</b>", badge))
    story.append(Spacer(1, 15))

    data = [
        ["Identificador Único", reserva.codigo_unico],
        ["Estado", reserva.estado],
        ["Área Solicitante", reserva.area_rel.nombre_area],
        ["Responsable", reserva.responsable],
        ["Correo Electrónico", reserva.correo_responsable],
        ["Sala Reservada", reserva.sala_rel.nombre],
        ["Ubicación", f"Edificio {reserva.sala_rel.edificio}"],
        ["Capacidad de la Sala", f"{reserva.sala_rel.capacidad} personas"],
        ["Fecha de Uso", reserva.fecha_reservacion.strftime('%d/%m/%Y')],
        ["Horario Autorizado", f"{reserva.hora_inicio.strftime('%H:%M')} a {reserva.hora_fin.strftime('%H:%M')} hrs"],
        ["Fecha de Registro", reserva.creado_en.strftime('%d/%m/%Y %H:%M:%S')]
    ]

    t = Table(data, colWidths=[170, 330])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0f172a')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9.5),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t)
    story.append(Spacer(1, 25))

    nota = ParagraphStyle('Nota', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#64748b'), alignment=1)
    story.append(Paragraph("Presente este comprobante digital o impreso al ingresar a la sala. Avala la exclusividad del uso en el bloque horario indicado.", nota))

    doc.build(story)
    buffer.seek(0)
    return buffer

def despachar_correo_async(app_instancia, id_reserva, destinatario, tipo, asunto, html_msg, plain_msg, pdf_bytes=None, pdf_filename="comprobante.pdf"):
    def tarea():
        with app_instancia.app_context():
            try:
                mailer.enviar_y_registrar(
                    id_reservacion=id_reserva,
                    destinatario=destinatario,
                    tipo=tipo,
                    asunto=asunto,
                    html_content=html_msg,
                    plain_content=plain_msg,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=pdf_filename
                )
            except Exception as ex:
                print(f"Error asíncrono en correo: {ex}")
            finally:
                db.session.remove()

    t = threading.Thread(target=tarea, daemon=True)
    t.start()

# --- DECORADORES ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Debes iniciar sesión para ingresar al sistema.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Debes iniciar sesión.", "error")
            return redirect(url_for('login'))
        if session.get('rol') != 'ADMIN':
            flash("Acceso denegado: Se requieren permisos de Administrador.", "error")
            return redirect(url_for('tablero'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE SESIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('tablero'))

    if request.method == 'POST':
        correo = request.form['correo'].strip().lower()
        password = request.form['password']

        user = Usuario.query.filter_by(correo=correo).first()
        if user and user.check_password(password):
            session['usuario_id'] = user.id_usuario
            session['nombre'] = user.nombre
            session['correo'] = user.correo
            session['rol'] = user.rol
            session['id_area'] = user.id_area
            session['nombre_area'] = user.area_rel.nombre_area
            flash(f"¡Bienvenido(a), {user.nombre}!", "success")
            return redirect(url_for('tablero'))
        else:
            flash("Correo o contraseña incorrectos.", "error")

    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'usuario_id' in session:
        return redirect(url_for('tablero'))

    areas = Area.query.order_by(Area.nombre_area.asc()).all()

    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        correo = request.form['correo'].strip().lower()
        id_area = int(request.form['id_area'])
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
            return render_template('registro.html', areas=areas)

        if Usuario.query.filter_by(correo=correo).first():
            flash("El correo electrónico ya está registrado.", "error")
            return render_template('registro.html', areas=areas)

        nuevo_user = Usuario(
            nombre=nombre,
            correo=correo,
            id_area=id_area,
            rol='USUARIO'
        )
        nuevo_user.set_password(password)
        db.session.add(nuevo_user)
        db.session.commit()

        flash("Registro completado exitosamente. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for('login'))

    return render_template('registro.html', areas=areas)

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('login'))

# --- TABLERO INTERACTIVO (CON HORAS PASADAS BLOQUEADAS) ---

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('tablero'))
    return redirect(url_for('login'))

@app.route('/tablero')
@login_required
def tablero():
    actualizar_reservaciones_vencidas()
    
    # Hora y fecha real en México
    ahora_dt = obtener_ahora()
    hoy = ahora_dt.date()
    hora_actual = ahora_dt.time()

    fecha_str = request.args.get('fecha', hoy.strftime('%Y-%m-%d'))
    
    try:
        fecha_dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_dt = hoy
        fecha_str = hoy.strftime('%Y-%m-%d')

    if fecha_dt < hoy:
        flash("No puedes seleccionar fechas anteriores a la actual.", "error")
        return redirect(url_for('tablero', fecha=hoy.strftime('%Y-%m-%d')))

    es_laborable = (fecha_dt.weekday() < 5)
    es_hoy = (fecha_dt == hoy)

    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    reservas = Reservacion.query.filter_by(fecha_reservacion=fecha_dt, estado='ACTIVA').all()
    
    # Limpiar bloqueos expirados automáticamente (Seat Lock)
    BloqueoTemporal.query.filter(BloqueoTemporal.expira_en < ahora_dt.replace(tzinfo=None)).delete()
    db.session.commit()

    bloqueos_activos = BloqueoTemporal.query.filter_by(fecha=fecha_dt).all()
    token_actual = str(session.get('usuario_id', 'anon'))

    tablero_filas = []
    for s in salas:
        celdas_sala = []
        for inicio_str, fin_str in BLOQUES_HORARIOS:
            t_ini = datetime.datetime.strptime(inicio_str, "%H:%M").time()
            t_fin = datetime.datetime.strptime(fin_str, "%H:%M").time()

            # 1. ¿El horario ya pasó hoy en México? Bloqueo automático del día en curso
            if es_hoy and t_ini <= hora_actual:
                celdas_sala.append({
                    'estado_slot': 'PASADO',
                    'hora_inicio': inicio_str,
                    'hora_fin': fin_str,
                    'mensaje': 'Horario concluido'
                })
                continue

            # 2. Verificar si está reservado
            reserva_encontrada = next(
                (r for r in reservas if r.id_sala == s.id_sala and (r.hora_inicio <= t_ini and r.hora_fin >= t_fin)),
                None
            )

            # 3. Verificar si está bloqueado por otro usuario (Seat Lock)
            bloqueo_encontrado = next(
                (b for b in bloqueos_activos if b.id_sala == s.id_sala and (b.hora_inicio <= t_ini and b.hora_fin >= t_fin)),
                None
            )

            if reserva_encontrada:
                celdas_sala.append({
                    'estado_slot': 'OCUPADO',
                    'area': reserva_encontrada.area_rel.nombre_area,
                    'responsable': reserva_encontrada.responsable,
                    'codigo': reserva_encontrada.codigo_unico,
                    'id_reservacion': reserva_encontrada.id_reservacion,
                    'horario': f"{reserva_encontrada.hora_inicio.strftime('%H:%M')}-{reserva_encontrada.hora_fin.strftime('%H:%M')}"
                })
            elif bloqueo_encontrado and str(bloqueo_encontrado.token_sesion) != token_actual:
                celdas_sala.append({
                    'estado_slot': 'BLOQUEADO',
                    'mensaje': 'En proceso de compra'
                })
            else:
                celdas_sala.append({
                    'estado_slot': 'LIBRE',
                    'hora_inicio': inicio_str,
                    'hora_fin': fin_str,
                    'id_sala': s.id_sala,
                    'nombre_sala': s.nombre
                })

        tablero_filas.append({
            'sala': s,
            'celdas': celdas_sala
        })

    return render_template(
        'tablero.html',
        fecha=fecha_str,
        hoy_str=hoy.strftime('%Y-%m-%d'),
        es_laborable=es_laborable,
        bloques=BLOQUES_HORARIOS,
        tablero=tablero_filas,
        salas=salas,
        total_reservas=len(reservas)
    )

# --- APIS DE SEAT HOLD ---

@app.route('/api/bloquear-horario', methods=['POST'])
@login_required
def api_bloquear_horario():
    data = request.get_json() or {}
    id_sala = int(data.get('id_sala', 0))
    fecha_str = data.get('fecha', '')
    h_ini_str = data.get('hora_inicio', '')
    h_fin_str = data.get('hora_fin', '')
    
    fecha_dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
    t_ini = datetime.datetime.strptime(h_ini_str, "%H:%M").time()
    t_fin = datetime.datetime.strptime(h_fin_str, "%H:%M").time()

    token = str(session.get('usuario_id'))

    with reserva_lock:
        ahora = datetime.datetime.now()
        BloqueoTemporal.query.filter(BloqueoTemporal.expira_en < ahora).delete()

        # Validación: No permitir bloquear horas que ya pasaron hoy
        if fecha_dt == ahora.date() and t_ini <= ahora.time():
            return jsonify({'success': False, 'message': 'Este horario ya ha concluido.'}), 400

        traslape_res = Reservacion.query.filter(
            Reservacion.id_sala == id_sala,
            Reservacion.fecha_reservacion == fecha_dt,
            Reservacion.estado == 'ACTIVA',
            not_(or_(Reservacion.hora_fin <= t_ini, Reservacion.hora_inicio >= t_fin))
        ).first()

        if traslape_res:
            return jsonify({'success': False, 'message': 'El horario ya fue reservado por otro usuario.'}), 409

        traslape_lock = BloqueoTemporal.query.filter(
            BloqueoTemporal.id_sala == id_sala,
            BloqueoTemporal.fecha == fecha_dt,
            BloqueoTemporal.token_sesion != token,
            BloqueoTemporal.expira_en > ahora,
            not_(or_(BloqueoTemporal.hora_fin <= t_ini, BloqueoTemporal.hora_inicio >= t_fin))
        ).first()

        if traslape_lock:
            return jsonify({'success': False, 'message': 'Otro usuario está apartando este horario en este momento.'}), 409

        expiracion = ahora + datetime.timedelta(minutes=5)
        nuevo_hold = BloqueoTemporal(
            id_sala=id_sala,
            fecha=fecha_dt,
            hora_inicio=t_ini,
            hora_fin=t_fin,
            token_sesion=token,
            expira_en=expiracion
        )
        db.session.add(nuevo_hold)
        db.session.commit()

        return jsonify({'success': True, 'expires_in': 300})

@app.route('/api/liberar-bloqueo', methods=['POST'])
@login_required
def api_liberar_bloqueo():
    data = request.get_json() or {}
    id_sala = int(data.get('id_sala', 0))
    token = str(session.get('usuario_id'))

    with reserva_lock:
        try:
            query = BloqueoTemporal.query.filter_by(token_sesion=token)
            if id_sala:
                query = query.filter_by(id_sala=id_sala)
            query.delete()
            db.session.commit()
            return jsonify({'success': True})
        except Exception:
            db.session.rollback()
            return jsonify({'success': False}), 500

# --- RESERVACIÓN ATÓMICA ---


@app.route('/reservar', methods=['GET', 'POST'])
@login_required
def reservar():
    if request.method == 'POST':
        id_sala = int(request.form['id_sala'])
        fecha_str = request.form['fecha']
        h_ini_str = request.form['hora_inicio']
        h_fin_str = request.form['hora_fin']

        if session.get('rol') == 'ADMIN':
            id_area = int(request.form['id_area'])
            responsable = request.form['responsable'].strip()
            correo = request.form['correo'].strip()
            id_user_rel = None
        else:
            id_area = session['id_area']
            responsable = session['nombre']
            correo = session['correo']
            id_user_rel = session['usuario_id']

        ahora_mexico = obtener_ahora()
        hoy = ahora_mexico.date()
        fecha_dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # Validación 1: Fechas pasadas
        if fecha_dt < hoy:
            flash("No puedes realizar reservaciones en fechas pasadas.", "error")
            return redirect(url_for('tablero', fecha=hoy.strftime('%Y-%m-%d')))

        # Validación 2: Lunes a viernes
        if fecha_dt.weekday() >= 5:
            flash("Error: Solo se permiten reservaciones de lunes a viernes.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        try:
            h_ini_dt = datetime.datetime.strptime(h_ini_str, '%H:%M').time()
            h_fin_dt = datetime.datetime.strptime(h_fin_str, '%H:%M').time()
        except ValueError:
            flash("Error: Formato de horario inválido.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        # Validación 3: Horario ya transcurrido hoy
        if fecha_dt == hoy and h_ini_dt <= ahora_mexico.time():
            flash("Error: No puedes reservar un horario que ya transcurrió en el día.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        if h_ini_dt.minute != 0 or h_fin_dt.minute != 0 or h_ini_dt.hour < 8 or h_fin_dt.hour > 21 or h_ini_dt >= h_fin_dt:
            flash("Error: Horario permitido de 08:00 a 21:00 en bloques cerrados consecutivos.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        # SECCIÓN CRÍTICA ATÓMICA CON MUTEX + PESSIMISTIC LOCKING
        with reserva_lock:
            try:
                traslape = Reservacion.query.with_for_update().filter(
                    Reservacion.id_sala == id_sala,
                    Reservacion.fecha_reservacion == fecha_dt,
                    Reservacion.estado == 'ACTIVA',
                    not_(or_(
                        Reservacion.hora_fin <= h_ini_dt,
                        Reservacion.hora_inicio >= h_fin_dt
                    ))
                ).first()

                if traslape:
                    db.session.rollback()
                    flash(f"Conflicto de Horario: La sala ya está ocupada entre {traslape.hora_inicio.strftime('%H:%M')} y {traslape.hora_fin.strftime('%H:%M')} por {traslape.area_rel.nombre_area}.", "error")
                    return redirect(url_for('tablero', fecha=fecha_str))

                codigo = f"RES-{uuid.uuid4().hex[:4].upper()}"
                nueva_reserva = Reservacion(
                    codigo_unico=codigo,
                    id_sala=id_sala,
                    id_area=id_area,
                    id_usuario=id_user_rel,
                    responsable=responsable,
                    correo_responsable=correo,
                    fecha_reservacion=fecha_dt,
                    hora_inicio=h_ini_dt,
                    hora_fin=h_fin_dt,
                    estado='ACTIVA'
                )
                db.session.add(nueva_reserva)

                # Liberar bloqueo temporal si existía
                BloqueoTemporal.query.filter_by(
                    id_sala=id_sala,
                    fecha=fecha_dt,
                    token_sesion=str(session.get('usuario_id'))
                ).delete()

                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Error al procesar la reservación: {e}", "error")
                return redirect(url_for('tablero', fecha=fecha_str))

        sala_obj = db.session.get(Sala, id_sala)
        area_obj = db.session.get(Area, id_area)

        # Generar comprobante PDF en memoria
        pdf_buffer = generar_pdf_buffer(nueva_reserva)
        pdf_bytes = pdf_buffer.getvalue()

        # Detección de HTTPS para evitar descarga insegura en Brave/Chrome
        esquema = 'https' if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https' or os.getenv('RAILWAY_ENVIRONMENT') else 'http'
        url_comprobante = url_for('descargar_comprobante_individual', codigo=codigo, _external=True, _scheme=esquema)

        asunto = f"Confirmación de Reservación - {codigo}"
        html_msg, plain_msg = mailer.generar_plantilla_confirmacion(
            codigo=codigo,
            area=area_obj.nombre_area,
            responsable=responsable,
            sala=sala_obj.nombre,
            edificio=sala_obj.edificio,
            capacidad=sala_obj.capacidad,
            fecha=fecha_str,
            hora_inicio=h_ini_str,
            hora_fin=h_fin_str,
            url_comprobante=url_comprobante
        )

        # Despacho asíncrono con Resend
        despachar_correo_async(
            app,
            nueva_reserva.id_reservacion,
            correo,
            'CONFIRMACION',
            asunto,
            html_msg,
            plain_msg,
            pdf_bytes,
            f"Comprobante_{codigo}.pdf"
        )

        flash(f"¡Reservación exitosa! Código: {codigo}. <a href='{url_comprobante}' class='underline font-bold ml-2' target='_blank'>Descargar Comprobante PDF</a>", "success")
        return redirect(url_for('tablero', fecha=fecha_str))

    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    areas = Area.query.order_by(Area.nombre_area.asc()).all()
    sel_sala = request.args.get('sala', '')
    sel_fecha = request.args.get('fecha', obtener_ahora().strftime('%Y-%m-%d'))
    sel_inicio = request.args.get('inicio', '08:00')
    sel_fin = request.args.get('fin', '09:00')

    return render_template(
        'reservar.html',
        salas=salas,
        areas=areas,
        sel_sala=sel_sala,
        sel_fecha=sel_fecha,
        sel_inicio=sel_inicio,
        sel_fin=sel_fin,
        hoy_str=obtener_ahora().strftime('%Y-%m-%d')
    )

# --- PANEL DE ADMINISTRACIÓN ---

@app.route('/admin')
@admin_required
def admin():
    actualizar_reservaciones_vencidas()
    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    areas = Area.query.order_by(Area.nombre_area.asc()).all()
    reservaciones = Reservacion.query.order_by(
        Reservacion.fecha_reservacion.desc(),
        Reservacion.hora_inicio.asc()
    ).all()
    return render_template('admin.html', salas=salas, areas=areas, reservaciones=reservaciones)

@app.route('/salas/crear', methods=['POST'])
@admin_required
def crear_sala():
    nombre = request.form['nombre'].strip()
    edificio = request.form['edificio'].strip()
    capacidad = int(request.form['capacidad'])
    encargado = request.form['encargado'].strip()

    if Sala.query.filter_by(nombre=nombre).first():
        flash(f"Error: Ya existe la sala '{nombre}'.", "error")
        return redirect(url_for('admin'))

    nueva_sala = Sala(nombre=nombre, edificio=edificio, capacidad=capacidad, encargado=encargado)
    db.session.add(nueva_sala)
    db.session.commit()
    flash(f"Sala '{nombre}' registrada.", "success")
    return redirect(url_for('admin'))

@app.route('/salas/editar/<int:id_sala>', methods=['POST'])
@admin_required
def editar_sala(id_sala):
    sala = db.session.get(Sala, id_sala)
    if sala:
        sala.nombre = request.form['nombre'].strip()
        sala.edificio = request.form['edificio'].strip()
        sala.capacidad = int(request.form['capacidad'])
        sala.encargado = request.form['encargado'].strip()
        db.session.commit()
        flash(f"Sala '{sala.nombre}' modificada con éxito.", "success")
    return redirect(url_for('admin'))

@app.route('/salas/eliminar/<int:id_sala>', methods=['POST'])
@admin_required
def eliminar_sala(id_sala):
    sala = db.session.get(Sala, id_sala)
    if sala:
        db.session.delete(sala)
        db.session.commit()
        flash(f"Sala '{sala.nombre}' eliminada.", "info")
    return redirect(url_for('admin'))

@app.route('/areas/crear', methods=['POST'])
@admin_required
def crear_area():
    nombre = request.form['nombre_area'].strip()
    if Area.query.filter_by(nombre_area=nombre).first():
        flash("Ya existe un área con ese nombre.", "error")
        return redirect(url_for('admin'))

    nueva_area = Area(nombre_area=nombre)
    db.session.add(nueva_area)
    db.session.commit()
    flash(f"Área '{nombre}' creada.", "success")
    return redirect(url_for('admin'))

@app.route('/areas/editar/<int:id_area>', methods=['POST'])
@admin_required
def editar_area(id_area):
    area = db.session.get(Area, id_area)
    if area:
        area.nombre_area = request.form['nombre_area'].strip()
        db.session.commit()
        flash("Área actualizada correctamente.", "success")
    return redirect(url_for('admin'))

@app.route('/areas/eliminar/<int:id_area>', methods=['POST'])
@admin_required
def eliminar_area(id_area):
    area = db.session.get(Area, id_area)
    if area:
        if area.usuarios or area.reservaciones:
            flash(f"No se puede eliminar el área '{area.nombre_area}' porque contiene usuarios o registros vinculados.", "error")
            return redirect(url_for('admin'))
        db.session.delete(area)
        db.session.commit()
        flash(f"Área eliminada.", "info")
    return redirect(url_for('admin'))

# --- CANCELACIÓN ---

@app.route('/cancelar/<int:id_reserva>', methods=['POST'])
@login_required
def cancelar(id_reserva):
    reserva = db.session.get(Reservacion, id_reserva)
    if not reserva:
        flash("La reservación indicada no existe.", "error")
        return redirect(url_for('tablero'))

    es_admin = (session.get('rol') == 'ADMIN')
    es_propietario = (
        (reserva.id_usuario and reserva.id_usuario == session.get('usuario_id')) or
        (reserva.correo_responsable == session.get('correo'))
    )

    if not (es_admin or es_propietario):
        flash("No tienes permisos para cancelar esta reservación.", "error")
        return redirect(url_for('mis_reservaciones'))

    if reserva.estado == 'CANCELADA':
        flash("Esta reservación ya había sido cancelada previamente.", "info")
        return redirect(request.referrer or url_for('tablero'))

    reserva.estado = 'CANCELADA'
    db.session.commit()

    asunto = f"Cancelación de Reservación - {reserva.codigo_unico}"
    html_msg, plain_msg = mailer.generar_plantilla_cancelacion(
        codigo=reserva.codigo_unico,
        area=reserva.area_rel.nombre_area,
        responsable=reserva.responsable,
        sala=reserva.sala_rel.nombre,
        fecha=reserva.fecha_reservacion.strftime('%Y-%m-%d'),
        hora_inicio=reserva.hora_inicio.strftime('%H:%M'),
        hora_fin=reserva.hora_fin.strftime('%H:%M')
    )

    despachar_correo_async(
        app,
        reserva.id_reservacion,
        reserva.correo_responsable,
        'CANCELACION',
        asunto,
        html_msg,
        plain_msg
    )

    flash(f"Reservación {reserva.codigo_unico} cancelada con éxito. Horario liberado.", "info")

    origen = request.referrer
    if origen and 'admin' in origen:
        return redirect(url_for('admin'))
    elif origen and 'mis-reservaciones' in origen:
        return redirect(url_for('mis_reservaciones'))
    return redirect(url_for('tablero'))

@app.route('/mis-reservaciones')
@login_required
def mis_reservaciones():
    actualizar_reservaciones_vencidas()
    user_id = session.get('usuario_id')
    user_correo = session.get('correo')

    mis_reservas = Reservacion.query.filter(
        or_(
            Reservacion.id_usuario == user_id,
            Reservacion.correo_responsable == user_correo
        )
    ).order_by(
        Reservacion.fecha_reservacion.desc(),
        Reservacion.hora_inicio.desc()
    ).all()

    return render_template('mis_reservaciones.html', reservaciones=mis_reservas, hoy=datetime.date.today())

# --- DESCARGA DE COMPROBANTE CON CABECERAS SEGURAS ---

@app.route('/reservacion/<codigo>/comprobante')
def descargar_comprobante_individual(codigo):
    reserva = Reservacion.query.filter_by(codigo_unico=codigo).first()
    if not reserva:
        flash("La reservación no existe.", "error")
        return redirect(url_for('tablero'))

    buffer = generar_pdf_buffer(reserva)
    pdf_data = buffer.getvalue()
    
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="Comprobante_{reserva.codigo_unico}.pdf"'
    response.headers['Content-Length'] = len(pdf_data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/reportes')
@admin_required
def reportes():
    actualizar_reservaciones_vencidas()
    tipo = request.args.get('tipo', 'sala')
    id_sala = request.args.get('id_sala')
    id_area = request.args.get('id_area')
    f_ini = request.args.get('fecha_inicio', '')
    f_fin = request.args.get('fecha_fin', '')

    query = Reservacion.query

    if tipo == 'sala' and id_sala:
        query = query.filter(Reservacion.id_sala == int(id_sala))
    elif tipo == 'area' and id_area:
        query = query.filter(Reservacion.id_area == int(id_area))

    if f_ini and f_fin:
        query = query.filter(Reservacion.fecha_reservacion.between(f_ini, f_fin))

    reservaciones = query.order_by(Reservacion.fecha_reservacion.asc(), Reservacion.hora_inicio.asc()).all()
    salas = Sala.query.all()
    areas = Area.query.all()

    return render_template(
        'reportes.html',
        reservaciones=reservaciones,
        salas=salas,
        areas=areas,
        tipo=tipo,
        sel_sala=id_sala,
        sel_area=id_area,
        f_ini=f_ini,
        f_fin=f_fin,
        generado_en=datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    )

@app.route('/reportes/pdf')
@admin_required
def descargar_reporte_pdf():
    tipo = request.args.get('tipo', 'sala')
    id_sala = request.args.get('id_sala')
    id_area = request.args.get('id_area')
    f_ini = request.args.get('fecha_inicio', '')
    f_fin = request.args.get('fecha_fin', '')

    query = Reservacion.query

    subtitulo_filtro = "Filtro: General"
    if tipo == 'sala' and id_sala:
        query = query.filter(Reservacion.id_sala == int(id_sala))
        s_obj = db.session.get(Sala, int(id_sala))
        if s_obj: subtitulo_filtro = f"Sala: {s_obj.nombre}"
    elif tipo == 'area' and id_area:
        query = query.filter(Reservacion.id_area == int(id_area))
        a_obj = db.session.get(Area, int(id_area))
        if a_obj: subtitulo_filtro = f"Área: {a_obj.nombre_area}"

    if f_ini and f_fin:
        query = query.filter(Reservacion.fecha_reservacion.between(f_ini, f_fin))
        subtitulo_filtro += f" | {f_ini} al {f_fin}"

    reservaciones = query.order_by(Reservacion.fecha_reservacion.asc(), Reservacion.hora_inicio.asc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0f172a'), alignment=1)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#475569'), alignment=1)

    story.append(Paragraph("SISTEMA DE RESERVACIÓN DE SALAS WEB - ITTG", title_style))
    story.append(Paragraph(f"Reporte Institucional de Ocupación • {subtitulo_filtro}", sub_style))
    story.append(Paragraph(f"Generado el: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", sub_style))
    story.append(Spacer(1, 15))

    data = [["Fecha", "Sala", "Área Solicitante", "Horario", "Responsable", "Código", "Estado"]]
    for r in reservaciones:
        data.append([
            r.fecha_reservacion.strftime('%d/%m/%Y'),
            r.sala_rel.nombre,
            r.area_rel.nombre_area,
            f"{r.hora_inicio.strftime('%H:%M')} - {r.hora_fin.strftime('%H:%M')}",
            r.responsable,
            r.codigo_unico,
            r.estado
        ])

    if len(data) == 1:
        data.append(["-", "-", "Sin reservaciones para este filtro", "-", "-", "-", "-"])

    t = Table(data, colWidths=[65, 110, 130, 80, 150, 75, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('FONTSIZE', (0,1), (-1,-1), 8),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)

    pdf_rep = buffer.getvalue()
    response = make_response(pdf_rep)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Reporte_Salas_{datetime.date.today().strftime("%Y%m%d")}.pdf'
    response.headers['Content-Length'] = len(pdf_rep)
    return response

# --- INICIALIZACIÓN AUTOMÁTICA EN GUNICORN Y LOCAL ---
def seed_admin_default():
    with app.app_context():
        db.create_all()
        area_sistemas = Area.query.first()
        if not area_sistemas:
            area_sistemas = Area(nombre_area="Sistemas y Computación")
            db.session.add(area_sistemas)
            db.session.commit()

        admin_user = Usuario.query.filter_by(correo="admin@ittg.edu.mx").first()
        if not admin_user:
            admin_user = Usuario(
                nombre="Administrador General ITTG",
                correo="admin@ittg.edu.mx",
                rol="ADMIN",
                id_area=area_sistemas.id_area
            )
            admin_user.set_password("admin123")
            db.session.add(admin_user)
            db.session.commit()
            print("✓ Usuario Admin inicial listo: admin@ittg.edu.mx / admin123")

try:
    seed_admin_default()
except Exception as e:
    print(f"Aviso de inicialización: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)