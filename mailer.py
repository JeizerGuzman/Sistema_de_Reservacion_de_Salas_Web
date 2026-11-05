import os
import json
import base64
import urllib.request
from flask import current_app
from models import db, Notificacion
from dotenv import load_dotenv

load_dotenv()

# Pega aquí la URL que te dio Google Apps Script (terminada en /exec)
GAS_WEBHOOK_URL = os.getenv("GAS_WEBHOOK_URL", "https://script.google.com/macros/s/AKfycbxWKyNt4kACmbk6rggOENSx1Nu73AuSyIbPgGwrV9qNHrnLsU-MCqU_IrFfH_K_dvRzyw/exec")

def enviar_y_registrar(id_reservacion, destinatario, tipo, asunto, html_content, plain_content="", pdf_bytes=None, pdf_filename="comprobante.pdf"):
    # 1. Registro en Base de Datos
    try:
        if current_app:
            nueva_notif = Notificacion(
                id_reservacion=id_reservacion,
                destinatario=destinatario,
                tipo=tipo,
                asunto=asunto,
                mensaje=plain_content if plain_content else asunto
            )
            db.session.add(nueva_notif)
            db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"Aviso BD: {e}")

    # 2. Despacho HTTP mediante Google Apps Script Webhook (Puerto 443 HTTPS)
    payload = {
        "to": destinatario,
        "subject": asunto,
        "text": plain_content if plain_content else asunto,
        "html": html_content,
        "name": "ReservaSalas ITTG"
    }

    if pdf_bytes:
        payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode('utf-8')
        payload["pdf_filename"] = pdf_filename

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            GAS_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        # Google redirige 302 hacia el servicio de ejecución
        with urllib.request.urlopen(req, timeout=20) as response:
            res_body = response.read().decode('utf-8')
            print(f"✓ Correo enviado vía Google Apps Script a {destinatario} | Respuesta: {res_body}")
            return True
    except Exception as e:
        print(f"✗ Falló el envío con Google Apps Script: {e}")
        return False

def generar_plantilla_confirmacion(codigo, area, responsable, sala, edificio, capacidad, fecha, hora_inicio, hora_fin, url_comprobante=""):
    boton_descarga = ""
    if url_comprobante:
        boton_descarga = f"""
        <tr>
          <td align="center" style="padding: 10px 30px 25px 30px;">
            <a href="{url_comprobante}" target="_blank" style="display: inline-block; background-color: #1e40af; color: #ffffff; text-decoration: none; font-weight: 700; font-size: 13px; padding: 12px 24px; border-radius: 8px;">
              Descargar Comprobante Oficial (PDF)
            </a>
          </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Confirmación de Reservación</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f1f5f9; padding: 25px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 580px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
          <tr>
            <td style="background-color: #0f172a; padding: 22px 25px; text-align: left; border-bottom: 3px solid #1e40af;">
              <span style="background-color: #1e3a8a; color: #93c5fd; font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 3px 8px; border-radius: 4px;">Instituto Tecnológico de Tuxtla Gutiérrez</span>
              <h1 style="color: #ffffff; font-size: 18px; font-weight: 700; margin: 6px 0 0 0;">Comprobante de Reservación</h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 25px 12px 25px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 10px 14px;">
                <tr>
                  <td>
                    <span style="font-size: 12px; font-weight: 700; color: #065f46;">ESTADO: ACTIVA</span>
                  </td>
                  <td align="right">
                    <span style="background-color: #059669; color: #ffffff; font-family: monospace; font-size: 14px; font-weight: 700; padding: 4px 10px; border-radius: 5px;">{codigo}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 25px 12px 25px; font-size: 13.5px; color: #334155;">
              Estimado(a) <strong>{responsable}</strong>, su espacio académico ha sido registrado exitosamente. Adjunto encontrará su comprobante formal en PDF.
            </td>
          </tr>
          <tr>
            <td style="padding: 0 25px 15px 25px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse: collapse; border: 1px solid #e2e8f0; font-size: 12.5px;">
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 8px 12px; color: #64748b; font-weight: 600; width: 35%;">Área Solicitante</td>
                  <td style="padding: 8px 12px; color: #0f172a; font-weight: 700;">{area}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 8px 12px; color: #64748b; font-weight: 600;">Sala</td>
                  <td style="padding: 8px 12px; color: #1e40af; font-weight: 700;">{sala}</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 8px 12px; color: #64748b; font-weight: 600;">Ubicación</td>
                  <td style="padding: 8px 12px; color: #0f172a;">Edificio {edificio} • Capacidad: {capacidad} personas</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 8px 12px; color: #64748b; font-weight: 600;">Fecha</td>
                  <td style="padding: 8px 12px; color: #0f172a; font-weight: 600;">{fecha}</td>
                </tr>
                <tr>
                  <td style="padding: 8px 12px; color: #64748b; font-weight: 600;">Horario</td>
                  <td style="padding: 8px 12px; color: #0f172a; font-weight: 700;">{hora_inicio} a {hora_fin} hrs</td>
                </tr>
              </table>
            </td>
          </tr>
          {boton_descarga}
          <tr>
            <td style="background-color: #f8fafc; padding: 12px 25px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
              Sistema Institucional de Gestión de Espacios ITTG.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    plain = (
        f"COMPROBANTE DE RESERVACIÓN DE SALA WEB\n"
        f"Código: {codigo}\n"
        f"Estado: ACTIVA\n\n"
        f"Responsable: {responsable}\n"
        f"Área: {area}\n"
        f"Sala: {sala} (Edificio {edificio}, Cap: {capacidad})\n"
        f"Fecha: {fecha}\n"
        f"Horario: {hora_inicio} a {hora_fin} hrs\n"
    )
    return html, plain

def generar_plantilla_cancelacion(codigo, area, responsable, sala, fecha, hora_inicio, hora_fin):
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Cancelación de Reservación</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f1f5f9; padding: 25px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 580px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
          <tr style="background-color: #0f172a; border-bottom: 3px solid #dc2626;">
            <td style="padding: 22px 25px; text-align: left;">
              <span style="background-color: #450a0a; color: #fca5a5; font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 3px 8px; border-radius: 4px;">Aviso Administrativo</span>
              <h1 style="color: #ffffff; font-size: 18px; font-weight: 700; margin: 6px 0 0 0;">Cancelación de Reservación</h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 25px 12px 25px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 10px 14px;">
                <tr>
                  <td>
                    <span style="font-size: 12px; font-weight: 700; color: #991b1b;">ESTADO: CANCELADA</span>
                  </td>
                  <td align="right">
                    <span style="background-color: #dc2626; color: #ffffff; font-family: monospace; font-size: 14px; font-weight: 700; padding: 4px 10px; border-radius: 5px;">{codigo}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 25px 12px 25px; font-size: 13.5px; color: #334155;">
              Estimado(a) <strong>{responsable}</strong>, la reservación para la sala <strong>{sala}</strong> agendada el día {fecha} ({hora_inicio} a {hora_fin}) ha sido cancelada.
            </td>
          </tr>
          <tr>
            <td style="background-color: #f8fafc; padding: 12px 25px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
              El horario ha sido liberado en el tablero institucional.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    plain = (
        f"AVISO DE CANCELACIÓN DE RESERVACIÓN\n"
        f"Código: {codigo}\n"
        f"Estado: CANCELADA\n\n"
        f"Estimado(a) {responsable},\n"
        f"La reservación para la sala {sala} el día {fecha} ({hora_inicio} a {hora_fin}) ha sido cancelada.\n"
    )
    return html, plain