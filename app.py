from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Sala, Area, Reservacion
from sqlalchemy import not_, or_
import uuid
import datetime
import mailer

app = Flask(__name__)
app.secret_key = "hackathon_ittg_secret_key"

# Conexión local a MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:davidlaid@localhost/sistema_reservaciones'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Lista oficial de los 13 bloques horarios del reto (08:00 a 21:00)
BLOQUES_HORARIOS = [
    ("08:00", "09:00"), ("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
    ("12:00", "13:00"), ("13:00", "14:00"), ("14:00", "15:00"), ("15:00", "16:00"),
    ("16:00", "17:00"), ("17:00", "18:00"), ("18:00", "19:00"), ("19:00", "20:00"),
    ("20:00", "21:00")
]

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

    es_laborable = (fecha_dt.weekday() < 5)  # 0 = Lunes, 4 = Viernes

    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    reservas = Reservacion.query.filter_by(fecha_reservacion=fecha_dt, estado='ACTIVA').all()
    areas = Area.query.order_by(Area.nombre_area.asc()).all()

    # Estructura del tablero: 1 fila por sala, con sus 13 columnas de horarios
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
            return redirect(url_for('reservar'))

        # Validación 2: Horarios permitidos (08:00 a 21:00) y horas en punto
        try:
            h_ini_dt = datetime.datetime.strptime(h_ini_str, '%H:%M').time()
            h_fin_dt = datetime.datetime.strptime(h_fin_str, '%H:%M').time()
        except ValueError:
            flash("Error: Formato de hora no válido.", "error")
            return redirect(url_for('reservar'))

        if h_ini_dt.minute != 0 or h_fin_dt.minute != 0:
            flash("Error: Las reservaciones deben ser por bloques de hora completa (ej. 08:00, 09:00).", "error")
            return redirect(url_for('reservar'))

        if h_ini_dt.hour < 8 or h_fin_dt.hour > 21 or h_ini_dt >= h_fin_dt:
            flash("Error: El horario permitido es de 08:00 a 21:00 hrs.", "error")
            return redirect(url_for('reservar'))

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
            flash(f"Conflicto de Horario: La sala ya está ocupada entre {traslape.hora_inicio.strftime('%H:%M')} y {traslape.hora_fin.strftime('%H:%M')} por el área de {traslape.area_rel.nombre_area}.", "error")
            return redirect(url_for('reservar'))

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

        # Disparar notificación por correo
        asunto = f"Confirmación de Reservación - {codigo}"
        mensaje = mailer.generar_plantilla_confirmacion(
            codigo=codigo,
            area=area_obj.nombre_area,
            responsable=responsable,
            sala=sala_obj.nombre,
            edificio=sala_obj.edificio,
            capacidad=sala_obj.capacidad,
            fecha=fecha_str,
            hora_inicio=h_ini_str,
            hora_fin=h_fin_str
        )
        mailer.enviar_y_registrar(nueva_reserva.id_reservacion, correo, 'CONFIRMACION', asunto, mensaje)

        flash(f"¡Reservación {codigo} registrada exitosamente!", "success")
        return redirect(url_for('tablero', fecha=fecha_str))

    salas = Sala.query.order_by(Sala.id_sala.asc()).all()
    areas = Area.query.order_by(Area.nombre_area.asc()).all()
    
    # Preselecciones si viene del tablero
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
    return render_template('admin_salas.html', salas=salas, reservaciones=reservaciones)

@app.route('/cancelar/<int:id_reserva>', methods=['POST'])
def cancelar(id_reserva):
    reserva = db.session.get(Reservacion, id_reserva)
    if reserva:
        reserva.estado = 'CANCELADA'
        db.session.commit()

        asunto = f"Cancelación de Reservación - {reserva.codigo_unico}"
        mensaje = mailer.generar_plantilla_cancelacion(
            codigo=reserva.codigo_unico,
            area=reserva.area_rel.nombre_area,
            responsable=reserva.responsable,
            sala=reserva.sala_rel.nombre,
            fecha=reserva.fecha_reservacion.strftime('%Y-%m-%d'),
            hora_inicio=reserva.hora_inicio.strftime('%H:%M'),
            hora_fin=reserva.hora_fin.strftime('%H:%M')
        )
        mailer.enviar_y_registrar(reserva.id_reservacion, reserva.correo_responsable, 'CANCELACION', asunto, mensaje)
        flash(f"Reservación {reserva.codigo_unico} cancelada. El horario fue liberado.", "info")

    origen = request.referrer
    if origen and 'admin' in origen:
        return redirect(url_for('admin'))
    return redirect(url_for('tablero'))

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)