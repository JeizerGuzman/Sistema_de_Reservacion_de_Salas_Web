from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Area(db.Model):
    __tablename__ = 'areas'

    id_area = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_area = db.Column(db.String(100), unique=True, nullable=False)
    
    usuarios = db.relationship('Usuario', backref='area_rel', lazy=True)
    reservaciones = db.relationship('Reservacion', backref='area_rel', cascade='all, delete')

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(150), nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('ADMIN', 'USUARIO'), default='USUARIO', nullable=False)
    id_area = db.Column(db.Integer, db.ForeignKey('areas.id_area', ondelete='RESTRICT'), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    reservaciones = db.relationship('Reservacion', backref='usuario_rel', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Sala(db.Model):
    __tablename__ = 'salas'

    id_sala = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    edificio = db.Column(db.String(50), nullable=False)
    capacidad = db.Column(db.Integer, nullable=False)
    encargado = db.Column(db.String(150), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    
    reservaciones = db.relationship('Reservacion', backref='sala_rel', cascade='all, delete')
    bloqueos = db.relationship('BloqueoTemporal', backref='sala_rel', cascade='all, delete')

class BloqueoTemporal(db.Model):
    __tablename__ = 'bloqueos_temporales'

    id_bloqueo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_sala = db.Column(db.Integer, db.ForeignKey('salas.id_sala', ondelete='CASCADE'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    token_sesion = db.Column(db.String(100), nullable=False)
    expira_en = db.Column(db.DateTime, nullable=False)

class Reservacion(db.Model):
    __tablename__ = 'reservaciones'

    id_reservacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_unico = db.Column(db.String(36), unique=True, nullable=False)
    id_sala = db.Column(db.Integer, db.ForeignKey('salas.id_sala', ondelete='CASCADE'), nullable=False)
    id_area = db.Column(db.Integer, db.ForeignKey('areas.id_area', ondelete='CASCADE'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
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