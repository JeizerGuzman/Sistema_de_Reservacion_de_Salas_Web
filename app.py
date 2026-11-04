from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from models import db, Sala, Area, Reservacion
from sqlalchemy import not_, or_
import uuid
import datetime
import io
import mailer

# Importaciones para generar PDF formal en memoria
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "hackathon_ittg_secret_key"

# Conexión MySQL local
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:davidlaid@localhost/sistema_reservaciones'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# 13 bloques horarios requeridos (08:00 a 21:00)
BLOQUES_HORARIOS = [
    ("08:00", "09:00"), ("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
    ("12:00", "13:00"), ("13:00", "14:00"), ("14:00", "15:00"), ("15:00", "16:00"),
    ("16:00", "17:00"), ("17:00", "18:00"), ("18:00", "19:00"), ("19:00", "20:00"),
    ("20:00", "21:00")
]

# --- FUNCIÓN GENERADORA DEL COMPROBANTE INDIVIDUAL EN PDF ---
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

@app.route('/')
def index():
    hoy = datetime.date.today().strftime('%Y-%m-%d')
    return redirect(url_for('tablero', fecha=hoy))

@app.route('/tablero')
def tablero():
    fecha_str = request.args.get('fecha', datetime.date.today().strftime('%Y-%m-%d'))
    try:
        fecha_dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_dt = datetime.date.today()
        fecha_str = fecha_dt.strftime('%Y-%m-%d')

    es_laborable = (fecha_dt.weekday() < 5)

    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    reservas = Reservacion.query.filter_by(fecha_reservacion=fecha_dt, estado='ACTIVA').all()
    areas = Area.query.order_by(Area.nombre_area.asc()).all()

    tablero_filas = []
    for s in salas:
        celdas_sala = []
        for inicio_str, fin_str in BLOQUES_HORARIOS:
            t_ini = datetime.datetime.strptime(inicio_str, "%H:%M").time()
            t_fin = datetime.datetime.strptime(fin_str, "%H:%M").time()

            reserva_encontrada = None
            for r in reservas:
                if r.id_sala == s.id_sala and (r.hora_inicio <= t_ini and r.hora_fin >= t_fin):
                    reserva_encontrada = r
                    break

            if reserva_encontrada:
                celdas_sala.append({
                    'ocupado': True,
                    'area': reserva_encontrada.area_rel.nombre_area,
                    'responsable': reserva_encontrada.responsable,
                    'codigo': reserva_encontrada.codigo_unico,
                    'id_reservacion': reserva_encontrada.id_reservacion,
                    'horario': f"{reserva_encontrada.hora_inicio.strftime('%H:%M')}-{reserva_encontrada.hora_fin.strftime('%H:%M')}"
                })
            else:
                celdas_sala.append({
                    'ocupado': False,
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
        es_laborable=es_laborable,
        bloques=BLOQUES_HORARIOS,
        tablero=tablero_filas,
        salas=salas,
        areas=areas,
        total_reservas=len(reservas)
    )

@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    if request.method == 'POST':
        id_sala = int(request.form['id_sala'])
        id_area = int(request.form['id_area'])
        responsable = request.form['responsable'].strip()
        correo = request.form['correo'].strip()
        fecha_str = request.form['fecha']
        h_ini_str = request.form['hora_inicio']
        h_fin_str = request.form['hora_fin']

        # Validación 1: Lunes a viernes
        fecha_dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        if fecha_dt.weekday() >= 5:
            flash("Error: Solo se permiten reservaciones de lunes a viernes.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        # Validación 2: Horarios y formato
        try:
            h_ini_dt = datetime.datetime.strptime(h_ini_str, '%H:%M').time()
            h_fin_dt = datetime.datetime.strptime(h_fin_str, '%H:%M').time()
        except ValueError:
            flash("Error: Formato de horario no válido.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        if h_ini_dt.minute != 0 or h_fin_dt.minute != 0:
            flash("Error: Las reservaciones deben ser por bloques de hora completa (ej. 08:00, 09:00).", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        if h_ini_dt.hour < 8 or h_fin_dt.hour > 21 or h_ini_dt >= h_fin_dt:
            flash("Error: El horario permitido es de 08:00 a 21:00 hrs.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        # Validación 3: Anti-traslapes
        traslape = Reservacion.query.filter(
            Reservacion.id_sala == id_sala,
            Reservacion.fecha_reservacion == fecha_dt,
            Reservacion.estado == 'ACTIVA',
            not_(or_(
                Reservacion.hora_fin <= h_ini_dt,
                Reservacion.hora_inicio >= h_fin_dt
            ))
        ).first()

        if traslape:
            flash(f"Conflicto de Horario: La sala ya está ocupada entre {traslape.hora_inicio.strftime('%H:%M')} y {traslape.hora_fin.strftime('%H:%M')} por {traslape.area_rel.nombre_area}.", "error")
            return redirect(url_for('tablero', fecha=fecha_str))

        codigo = f"RES-{uuid.uuid4().hex[:4].upper()}"
        nueva_reserva = Reservacion(
            codigo_unico=codigo,
            id_sala=id_sala,
            id_area=id_area,
            responsable=responsable,
            correo_responsable=correo,
            fecha_reservacion=fecha_dt,
            hora_inicio=h_ini_dt,
            hora_fin=h_fin_dt,
            estado='ACTIVA'
        )
        db.session.add(nueva_reserva)
        db.session.commit()

        sala_obj = db.session.get(Sala, id_sala)
        area_obj = db.session.get(Area, id_area)

        # Generar comprobante PDF individual en memoria
        pdf_buffer = generar_pdf_buffer(nueva_reserva)
        pdf_bytes = pdf_buffer.getvalue()

        # Enlace opcional de descarga web
        url_comprobante = url_for('descargar_comprobante_individual', codigo=codigo, _external=True)

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

        # Envío único con el comprobante PDF adjunto
        mailer.enviar_y_registrar(
            id_reservacion=nueva_reserva.id_reservacion,
            destinatario=correo,
            tipo='CONFIRMACION',
            asunto=asunto,
            html_content=html_msg,
            plain_content=plain_msg,
            pdf_bytes=pdf_bytes,
            pdf_filename=f"Comprobante_{codigo}.pdf"
        )

        flash(f"¡Reservación exitosa! Código: {codigo}", "success")
        return redirect(url_for('tablero', fecha=fecha_str))

    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    areas = Area.query.order_by(Area.nombre_area.asc()).all()
    
    sel_sala = request.args.get('sala', '')
    sel_fecha = request.args.get('fecha', datetime.date.today().strftime('%Y-%m-%d'))
    sel_inicio = request.args.get('inicio', '08:00')
    sel_fin = request.args.get('fin', '09:00')

    return render_template('reservar.html', salas=salas, areas=areas,
                           sel_sala=sel_sala, sel_fecha=sel_fecha,
                           sel_inicio=sel_inicio, sel_fin=sel_fin)

@app.route('/admin')
def admin():
    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    reservaciones = Reservacion.query.filter_by(estado='ACTIVA').order_by(
        Reservacion.fecha_reservacion.desc(),
        Reservacion.hora_inicio.asc()
    ).all()
    return render_template('admin.html', salas=salas, reservaciones=reservaciones)

# --- RUTAS DE GESTIÓN (CRUD) DE SALAS ---

@app.route('/salas/crear', methods=['POST'])
def crear_sala():
    nombre = request.form['nombre'].strip()
    edificio = request.form['edificio'].strip()
    capacidad = int(request.form['capacidad'])
    encargado = request.form['encargado'].strip()

    if not nombre or not edificio or capacidad <= 0:
        flash("Error: Verifica que los datos de la sala sean válidos.", "error")
        return redirect(url_for('admin'))

    existe = Sala.query.filter_by(nombre=nombre).first()
    if existe:
        flash(f"Error: Ya existe una sala registrada con el nombre '{nombre}'.", "error")
        return redirect(url_for('admin'))

    nueva_sala = Sala(nombre=nombre, edificio=edificio, capacidad=capacidad, encargado=encargado)
    db.session.add(nueva_sala)
    db.session.commit()

    flash(f"Sala '{nombre}' creada exitosamente.", "success")
    return redirect(url_for('admin'))

@app.route('/salas/editar/<int:id_sala>', methods=['POST'])
def editar_sala(id_sala):
    sala = db.session.get(Sala, id_sala)
    if not sala:
        flash("Error: Sala no encontrada.", "error")
        return redirect(url_for('admin'))

    nombre = request.form['nombre'].strip()
    edificio = request.form['edificio'].strip()
    capacidad = int(request.form['capacidad'])
    encargado = request.form['encargado'].strip()

    sala.nombre = nombre
    sala.edificio = edificio
    sala.capacidad = capacidad
    sala.encargado = encargado
    db.session.commit()

    flash(f"Sala '{nombre}' actualizada correctamente.", "success")
    return redirect(url_for('admin'))

@app.route('/salas/eliminar/<int:id_sala>', methods=['POST'])
def eliminar_sala(id_sala):
    sala = db.session.get(Sala, id_sala)
    if sala:
        nombre = sala.nombre
        db.session.delete(sala)
        db.session.commit()
        flash(f"Sala '{nombre}' y sus reservaciones asociadas fueron eliminadas.", "info")
    return redirect(url_for('admin'))

# --- CANCELACIÓN DE RESERVACIONES ---

@app.route('/cancelar/<int:id_reserva>', methods=['POST'])
def cancelar(id_reserva):
    reserva = db.session.get(Reservacion, id_reserva)
    if reserva:
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
        mailer.enviar_y_registrar(
            id_reservacion=reserva.id_reservacion,
            destinatario=reserva.correo_responsable,
            tipo='CANCELACION',
            asunto=asunto,
            html_content=html_msg,
            plain_content=plain_msg
        )
        flash(f"Reservación {reserva.codigo_unico} cancelada. Horario liberado.", "info")

    origen = request.referrer
    if origen and 'admin' in origen:
        return redirect(url_for('admin'))
    return redirect(url_for('tablero'))

# --- DESCARGA WEB DE COMPROBANTE INDIVIDUAL ---

@app.route('/reservacion/<codigo>/comprobante')
def descargar_comprobante_individual(codigo):
    reserva = Reservacion.query.filter_by(codigo_unico=codigo).first()
    if not reserva:
        flash("La reservación no existe.", "error")
        return redirect(url_for('tablero'))

    buffer = generar_pdf_buffer(reserva)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Comprobante_{reserva.codigo_unico}.pdf'
    return response

# --- REPORTES Y EXPORTACIÓN A PDF REAL ---

@app.route('/reportes')
def reportes():
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
def descargar_reporte_pdf():
    tipo = request.args.get('tipo', 'sala')
    id_sala = request.args.get('id_sala')
    id_area = request.args.get('id_area')
    f_ini = request.args.get('fecha_inicio', '')
    f_fin = request.args.get('fecha_fin', '')

    query = Reservacion.query

    subtitulo_filtro = "Filtro: Todos los registros"
    if tipo == 'sala' and id_sala:
        query = query.filter(Reservacion.id_sala == int(id_sala))
        s_obj = db.session.get(Sala, int(id_sala))
        if s_obj: subtitulo_filtro = f"Filtrado por Sala: {s_obj.nombre}"
    elif tipo == 'area' and id_area:
        query = query.filter(Reservacion.id_area == int(id_area))
        a_obj = db.session.get(Area, int(id_area))
        if a_obj: subtitulo_filtro = f"Filtrado por Área: {a_obj.nombre_area}"

    if f_ini and f_fin:
        query = query.filter(Reservacion.fecha_reservacion.between(f_ini, f_fin))
        subtitulo_filtro += f" | Periodo: {f_ini} al {f_fin}"

    reservaciones = query.order_by(Reservacion.fecha_reservacion.asc(), Reservacion.hora_inicio.asc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#1e1b4b'), alignment=1)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#475569'), alignment=1)

    story.append(Paragraph("SISTEMA DE RESERVACIÓN DE SALAS WEB", title_style))
    story.append(Paragraph(f"Reporte Institucional de Disponibilidad y Uso • {subtitulo_filtro}", sub_style))
    story.append(Paragraph(f"Fecha de emisión: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", sub_style))
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
        data.append(["-", "-", "Sin reservaciones registradas para este filtro", "-", "-", "-", "-"])

    t = Table(data, colWidths=[65, 110, 130, 80, 150, 75, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#312e81')),
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

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Reporte_Salas_{datetime.date.today().strftime("%Y%m%d")}.pdf'
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)