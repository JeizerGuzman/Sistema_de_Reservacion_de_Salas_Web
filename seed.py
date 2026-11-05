import os
import datetime
from dotenv import load_dotenv

# Cargar variables locales si existen (.env)
load_dotenv()

from app import app
from models import db, Area, Sala, Usuario, Reservacion

def poblar_sistema():
    with app.app_context():
        # Detección del entorno activo
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print("==================================================")
        print("  INICIALIZADOR DE BASE DE DATOS INSTITUCIONAL")
        print("==================================================")
        print(f"Destino: {'Railway / Cloud' if 'railway' in uri or os.getenv('RAILWAY_ENVIRONMENT') else 'Localhost'}")
        
        # 1. CREACIÓN AUTOMÁTICA DE TABLAS
        print("Sincronizando y creando tablas faltantes...")
        db.create_all()
        print("✓ Tablas verificadas / creadas exitosamente.")

        # 2. SEED DE ÁREAS INSTITUCIONALES
        areas_nombres = [
            'Sistemas y Computación',
            'Ciencias Básicas',
            'Desarrollo Académico',
            'Recursos Humanos',
            'Dirección General',
            'Vinculación y Extensión'
        ]
        
        areas_dict = {}
        for nom in areas_nombres:
            area = Area.query.filter_by(nombre_area=nom).first()
            if not area:
                area = Area(nombre_area=nom)
                db.session.add(area)
                db.session.flush()
            areas_dict[nom] = area
        db.session.commit()
        print("✓ Áreas institucionales registradas.")

        # 3. SEED DE SALAS BASE
        salas_data = [
            {'nombre': 'Audiovisual 1', 'edificio': 'A', 'capacidad': 50, 'encargado': 'Juan Pérez'},
            {'nombre': 'Audiovisual 2', 'edificio': 'B', 'capacidad': 40, 'encargado': 'María López'},
            {'nombre': 'Audiovisual 3', 'edificio': 'C', 'capacidad': 60, 'encargado': 'Pedro Ruiz'},
            {'nombre': 'Biblioteca', 'edificio': 'Biblioteca', 'capacidad': 30, 'encargado': 'Ana Gómez'}
        ]

        salas_dict = {}
        for s in salas_data:
            sala = Sala.query.filter_by(nombre=s['nombre']).first()
            if not sala:
                sala = Sala(
                    nombre=s['nombre'],
                    edificio=s['edificio'],
                    capacidad=s['capacidad'],
                    encargado=s['encargado']
                )
                db.session.add(sala)
                db.session.flush()
            salas_dict[s['nombre']] = sala
        db.session.commit()
        print("✓ Salas base registradas.")

        # 4. SEED DE USUARIOS BASE
        usuarios_seed = [
            {
                'nombre': 'Administrador General ITTG',
                'correo': 'admin@ittg.edu.mx',
                'password': 'admin123',
                'rol': 'ADMIN',
                'area': 'Dirección General'
            },
            {
                'nombre': 'Jeizer Guzman',
                'correo': 'jeizerguzchable@gmail.com',
                'password': 'usuario123',
                'rol': 'USUARIO',
                'area': 'Sistemas y Computación'
            },
            {
                'nombre': 'Ing. Carlos Vázquez',
                'correo': 'carlos.vazquez@ittg.edu.mx',
                'password': 'usuario123',
                'rol': 'USUARIO',
                'area': 'Sistemas y Computación'
            },
            {
                'nombre': 'Dra. Elena Ramos',
                'correo': 'elena.ramos@ittg.edu.mx',
                'password': 'usuario123',
                'rol': 'USUARIO',
                'area': 'Ciencias Básicas'
            }
        ]

        users_dict = {}
        for u in usuarios_seed:
            user = Usuario.query.filter_by(correo=u['correo']).first()
            if not user:
                user = Usuario(
                    nombre=u['nombre'],
                    correo=u['correo'],
                    rol=u['rol'],
                    id_area=areas_dict[u['area']].id_area
                )
                user.set_password(u['password'])
                db.session.add(user)
                db.session.flush()
            users_dict[u['correo']] = user
        db.session.commit()
        print("✓ Cuentas de usuario configuradas.")

        # 5. RESERVACIONES DE PRUEBA (ACTIVA, CONCLUIDA, CANCELADA)
        hoy = datetime.date.today()
        ayer = hoy - datetime.timedelta(days=1)
        if ayer.weekday() >= 5:
            ayer = hoy - datetime.timedelta(days=3)

        fecha_activa = hoy if hoy.weekday() < 5 else hoy + datetime.timedelta(days=(7 - hoy.weekday()))

        # Reserva CONCLUIDA
        if not Reservacion.query.filter_by(codigo_unico='RES-HIST1').first():
            db.session.add(Reservacion(
                codigo_unico='RES-HIST1',
                id_sala=salas_dict['Audiovisual 1'].id_sala,
                id_area=areas_dict['Sistemas y Computación'].id_area,
                id_usuario=users_dict['jeizerguzchable@gmail.com'].id_usuario,
                responsable='Jeizer Guzman',
                correo_responsable='jeizerguzchable@gmail.com',
                fecha_reservacion=ayer,
                hora_inicio=datetime.time(8, 0),
                hora_fin=datetime.time(10, 0),
                estado='CONCLUIDA'
            ))

        # Reserva CANCELADA
        if not Reservacion.query.filter_by(codigo_unico='RES-CANC1').first():
            db.session.add(Reservacion(
                codigo_unico='RES-CANC1',
                id_sala=salas_dict['Audiovisual 2'].id_sala,
                id_area=areas_dict['Ciencias Básicas'].id_area,
                id_usuario=users_dict['admin@ittg.edu.mx'].id_usuario,
                responsable='Administrador General ITTG',
                correo_responsable='admin@ittg.edu.mx',
                fecha_reservacion=ayer,
                hora_inicio=datetime.time(12, 0),
                hora_fin=datetime.time(13, 0),
                estado='CANCELADA'
            ))

        # Reserva ACTIVA
        if not Reservacion.query.filter_by(codigo_unico='RES-ACTV1').first():
            db.session.add(Reservacion(
                codigo_unico='RES-ACTV1',
                id_sala=salas_dict['Biblioteca'].id_sala,
                id_area=areas_dict['Sistemas y Computación'].id_area,
                id_usuario=users_dict['jeizerguzchable@gmail.com'].id_usuario,
                responsable='Jeizer Guzman',
                correo_responsable='jeizerguzchable@gmail.com',
                fecha_reservacion=fecha_activa,
                hora_inicio=datetime.time(18, 0),
                hora_fin=datetime.time(20, 0),
                estado='ACTIVA'
            ))

        db.session.commit()
        print("✓ Reservaciones de prueba inicializadas.")
        print("==================================================")
        print("  PROCESO COMPLETADO EXITOSAMENTE")
        print("==================================================")

if __name__ == '__main__':
    poblar_sistema()