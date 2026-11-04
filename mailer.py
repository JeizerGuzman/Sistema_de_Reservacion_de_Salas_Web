import smtplib
from email.mime.text import MIMEText
from models import db, Notificacion

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
CORREO_EMISOR = "nexumssolutions@gmail.com"
PASSWORD_EMISOR = "x a limpez lujivz t r"

def enviar_y_registrar(id_reservacion, destinatario, tipo, asunto, mensaje):
    # 1. Registro obligatorio en la base de datos (tabla notificaciones)
    try:
        nueva_notif = Notificacion(
            id_reservacion=id_reservacion,
            destinatario=destinatario,
            tipo=tipo,
            asunto=asunto,
            mensaje=mensaje
        )
        db.session.add(nueva_notif)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error registrando en tabla notificaciones: {e}")

    # 2. Envío de correo electrónico vía SMTP
    try:
        msg = MIMEText(mensaje, "plain", "utf-8")
        msg["Subject"] = asunto
        msg["From"] = f"Sistema de Salas ITTG <{CORREO_EMISOR}>"
        msg["To"] = destinatario

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(CORREO_EMISOR, PASSWORD_EMISOR)
        server.sendmail(CORREO_EMISOR, destinatario, msg.as_string())
        server.quit()
        print(f"Correo enviado exitosamente a {destinatario}")
        return True
    except Exception as e:
        print(f"Aviso SMTP: Falló el envío externo ({e}). Quedó guardado en la base de datos.")
        return False

def generar_plantilla_confirmacion(codigo, area, responsable, sala, edificio, capacidad, fecha, hora_inicio, hora_fin):
    return (
        f"COMPROBANTE DE RESERVACIÓN DE ESPACIO ACADÉMICO\n"
        f"--------------------------------------------------\n\n"
        f"• Identificador de reservación : {codigo}\n"
        f"• Nombre del área solicitante   : {area}\n"
        f"• Nombre del responsable        : {responsable}\n"
        f"• Nombre de la sala             : {sala}\n"
        f"• Edificio y capacidad          : Edificio {edificio} | Capacidad: {capacidad} personas\n"
        f"• Fecha de reservación          : {fecha}\n"
        f"• Horario de uso                : {hora_inicio} a {hora_fin}\n"
        f"• Estado de la reservación      : ACTIVA\n\n"
        f"Por favor conserve este identificador para cualquier aclaración o control de acceso."
    )

def generar_plantilla_cancelacion(codigo, area, responsable, sala, fecha, hora_inicio, hora_fin):
    return (
        f"NOTIFICACIÓN DE CANCELACIÓN DE RESERVACIÓN\n"
        f"--------------------------------------------------\n\n"
        f"Estimado(a) {responsable},\n"
        f"Le informamos que la reservación con identificador {codigo} ha sido cancelada por la administración:\n\n"
        f"• Área solicitante : {area}\n"
        f"• Sala liberada    : {sala}\n"
        f"• Fecha agendada   : {fecha}\n"
        f"• Horario previo   : {hora_inicio} a {hora_fin}\n"
        f"• Estado actual    : CANCELADA\n\n"
        f"El horario ha sido liberado en el tablero del sistema."
    )