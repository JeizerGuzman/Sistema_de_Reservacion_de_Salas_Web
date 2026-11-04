from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Area(db.Model):
    __tablename__ = 'areas'

    id_area = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_area = db.Column(db.String(100), unique=True, nullable=False)
    reservaciones = db.relationship('Reservacion', backref='area_rel', cascade='all, delete')

class Sala(db.Model):
    __tablename__ = 'salas'

    id_sala = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    edificio = db.Column(db.String(50), nullable=False)
    capacidad = db.Column(db.Integer, nullable=False)
    encargado = db.Column(db.String(150), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    reservaciones = db.relationship('Reservacion', backref='sala_rel', cascade='all, delete')

class Reservacion(db.Model):
    __tablename__ = 'reservaciones'

    id_reservacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_unico = db.Column(db.String(36), unique=True, nullable=False)
    id_sala = db.Column(db.Integer, db.ForeignKey('salas.id_sala', ondelete='CASCADE'), nullable=False)
    id_area = db.Column(db.Integer, db.ForeignKey('areas.id_area', ondelete='CASCADE'), nullable=False)
    responsable = db.Column(db.String(150), nullable=False)
    correo_responsable = db.Column(db.String(150), nullable=False)
    fecha_reservacion = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    estado = db.Column(db.Enum('ACTIVA', 'CANCELADA'), default='ACTIVA')
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    notificaciones = db.relationship('Notificacion', backref='reservacion_rel', cascade='all, delete')

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'

    id_notificacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_reservacion = db.Column(db.Integer, db.ForeignKey('reservaciones.id_reservacion', ondelete='CASCADE'), nullable=False)
    destinatario = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.Enum('CONFIRMACION', 'CANCELACION'), nullable=False)
    asunto = db.Column(db.String(255), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    enviado_en = db.Column(db.DateTime, default=datetime.utcnow)