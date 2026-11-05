from app import app
from models import db, Area, Sala, Usuario, Reservacion
import datetime

def poblar_sistema():
    with app.app_context():
        print("Sincronizando base de datos...")
        db.create_all()

        # 1. ÁREAS
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
        print("✓ Áreas registradas.")

        # 2. SALAS
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
        print("✓ Salas registradas.")

        # 3. USUARIOS
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
        print("✓ Usuarios registrados.")

        # 4. RESERVACIONES DE PRUEBA (Para ver los 3 estados directamente)
        hoy = datetime.date.today()
        ayer = hoy - datetime.timedelta(days=1)
        if ayer.weekday() >= 5:
            ayer = hoy - datetime.timedelta(days=3)

        # Reserva 1: CONCLUIDA (Ayer)
        r_concluida = Reservacion.query.filter_by(codigo_unico='RES-HIST1').first()
        if not r_concluida:
            r_concluida = Reservacion(
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
            )
            db.session.add(r_concluida)

        # Reserva 2: CANCELADA
        r_cancelada = Reservacion.query.filter_by(codigo_unico='RES-CANC1').first()
        if not r_cancelada:
            r_cancelada = Reservacion(
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
            )
            db.session.add(r_cancelada)

        # Reserva 3: ACTIVA (Día laborable futuro)
        fecha_activa = hoy if hoy.weekday() < 5 else hoy + datetime.timedelta(days=(7 - hoy.weekday()))
        r_activa = Reservacion.query.filter_by(codigo_unico='RES-ACTV1').first()
        if not r_activa:
            r_activa = Reservacion(
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
            )
            db.session.add(r_activa)

        db.session.commit()
        print("✓ Reservaciones creadas:")
        print("   - RES-HIST1 -> CONCLUIDA")
        print("   - RES-CANC1 -> CANCELADA")
        print("   - RES-ACTV1 -> ACTIVA")
        print("\n¡Base de datos lista! Ahora inicia: python app.py")

if __name__ == '__main__':
    poblar_sistema()