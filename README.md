# Sistema de Reservación de Salas Web — TecNM / Instituto Tecnológico de Tuxtla Gutiérrez

> **Proyecto Oficial:** Sistema de Gestión y Reservación Concurrente de Espacios Académicos  
> **Equipo Consultor:** Nexum Solutions  
> **Fecha:** Noviembre 2026  
> **Cliente:** TecNM / ITTG  
> **Stack Tecnológico:** Python 3 (Flask), MySQL (InnoDB), SQLAlchemy ORM, ReportLab, Tailwind CSS, JavaScript Vanilla, SMTP (Gmail API / App Passwords).

---

## 1. Descripción General del Proyecto

Plataforma web institucional concebida para administrar de forma íntegra y transparente la disponibilidad, asignación, reporte y control de 4 espacios académicos y administrativos base del Instituto Tecnológico de Tuxtla Gutiérrez:
- **Audiovisual 1** (Edificio A, Capacidad: 50 personas)
- **Audiovisual 2** (Edificio B, Capacidad: 40 personas)
- **Audiovisual 3** (Edificio C, Capacidad: 60 personas)
- **Biblioteca** (Edificio Central, Capacidad: 30 personas)

El sistema erradica traslapes de horario mediante validaciones matemáticas en memoria y bloqueos pesimistas a nivel de motor transaccional, integrando selección interactiva continua (08:00 a 21:00 hrs de lunes a viernes), emisión automática de comprobantes individuales en PDF adjuntos vía correo electrónico institucional y control de acceso basado en roles.

---

## 2. Arquitectura de Software y Control de Concurrencia

Para resolver escenarios de alta demanda simultánea (donde dos o más solicitantes intentan apartar la misma aula en el mismo intervalo), el sistema implementa un modelo de mitigación en **3 capas independientes**:

```
[ Navegador Web ]
       │
       ▼  (Paso 1: Selección en Tablero)
┌────────────────────────────────────────────────────────┐
│ 1. Bloqueo Temporal (Seat Lock / Hold)                 │
│    • Endpoint: /api/bloquear-horario                   │
│    • Tabla: `bloqueos_temporales`                      │
│    • Vigencia: 5 minutos con token de sesión única     │
│    • Tablero: El slot se marca en gris como "Apartando"│
└────────────────────────────────────────────────────────┘
       │
       ▼  (Paso 2: Confirmación de Formulario)
┌────────────────────────────────────────────────────────┐
│ 2. Exclusión Mutua en Backend (Mutex)                  │
│    • Variable de cerrojo: `reserva_lock`               │
│    • Módulo: `threading.Lock()` de Python              │
│    • Garantiza que solo un hilo evalúe la asignación   │
└────────────────────────────────────────────────────────┘
       │
       ▼  (Paso 3: Transacción Transaccional ACID)
┌────────────────────────────────────────────────────────┐
│ 3. Bloqueo Pesimista en Base de Datos (InnoDB)         │
│    • Sentencia: `SELECT ... FOR UPDATE`                │
│    • Ejecutada mediante: `query.with_for_update()`     │
│    • Aislamiento contra lecturas sucias y fantasmas    │
│    • Purga automática del Hold + Inserción Definitiva  │
└────────────────────────────────────────────────────────┘
```

Adicionalmente, un hilo demonio (*daemon thread*) se ejecuta en segundo plano purgando registros caducados en `bloqueos_temporales` cada 30 segundos para evitar bloqueos huérfanos.

---

## 3. Modelo de Roles y Permisos

| Módulo / Acción | Solicitante (`USUARIO`) | Administrador (`ADMIN`) |
| :--- | :---: | :---: |
| Consulta del Tablero Interactivo (08:00 - 21:00 hrs) | Sí | Sí |
| Selección y bloqueo multi-hora consecutiva | Sí | Sí |
| Registro de Reservación | Sí (Datos fijos inmutables según cuenta) | Sí (Puede asignar a cualquier área) |
| Recepción de correo SMTP con PDF oficial adjunto | Sí | Sí |
| Consulta de "Mis Reservaciones" | Sí (Historial propio) | Sí (Historial global) |
| Auto-cancelación de reservaciones propias vigentes | Sí | Sí |
| Cancelación administrativa y liberación forzosa | No | Sí (Cualquier reservación) |
| CRUD de Salas (Crear, editar, eliminar, aforo) | No | Sí |
| CRUD de Áreas Académicas y Departamentos | No | Sí |
| Generación e impresión de Reportes filtrables en PDF | No | Sí |

---

## 4. Requisitos del Sistema e Instalación

### Requisitos Previos
- **Python:** 3.10 o superior (verificado en Python 3.13)
- **Base de Datos:** MySQL Server 8.0+ / MariaDB 10.4+ (vía XAMPP, WampServer o servicio local)
- **Navegador Web:** Chrome, Edge, Brave o Firefox con soporte ECMAScript 6

### Clonación e Instalación de Dependencias

```bash
# 1. Clonar el repositorio y entrar al directorio
git clone https://github.com/JeizerGuzman/Sistema_de_Reservacion_de_Salas_Web.git
cd Sistema_de_Reservacion_de_Salas_Web

# 2. Cambiarse a la rama de concurrencia y autenticación
git checkout feature-auth-concurrency

# 3. Crear y activar entorno virtual (Opcional pero recomendado)
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

# 4. Instalar librerías oficiales
pip install -r requirements.txt
```

---

## 5. Configuración de Base de Datos

1. Inicia tu motor MySQL (puerto `3306`).
2. Abre tu gestor preferido (phpMyAdmin, MySQL Workbench o consola CLI).
3. Crea la base de datos dedicada:
   ```sql
   CREATE DATABASE IF NOT EXISTS `sistema_reservaciones_v2` 
   DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
4. Verifica en `app.py` que la cadena de conexión coincida con tus credenciales locales:
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:TU_PASSWORD@localhost/sistema_reservaciones_v2'
   ```

### Poblado Automático de Datos Semilla
Ejecuta el script de inicialización para crear las salas oficiales, las áreas institucionales y los usuarios preconfigurados:
```bash
python seed.py
```

---

## 6. Credenciales de Acceso por Defecto

| Rol | Correo Electrónico | Contraseña | Departamento / Área |
| :--- | :--- | :--- | :--- |
| **Administrador** | `admin@ittg.edu.mx` | `admin123` | Dirección General |
| **Usuario 1** | `carlos.vazquez@ittg.edu.mx` | `usuario123` | Sistemas y Computación |
| **Usuario 2** | `elena.ramos@ittg.edu.mx` | `usuario123` | Ciencias Básicas |

*Nota:* También es posible registrar nuevas cuentas desde `/registro`, asignándolas a cualquiera de las áreas existentes en la base de datos.

---

## 7. Ejecución y Despliegue Local

Para iniciar el servidor de desarrollo en modo red local:

```bash
python app.py
```

La consola confirmará el arranque:
```text
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://[TU_IP_LOCAL]:5000
```

- **Acceso en la computadora anfitriona:** `http://localhost:5000`
- **Acceso desde dispositivos móviles / red local:** `http://[TU_IP_LOCAL]:5000` (ejemplo: `http://192.168.1.75:5000`)

---

## 8. Estructura del Proyecto

```text
Sistema_de_Reservacion_de_Salas_Web/
├── app.py                     # Controlador central Flask, rutas protegidas y sección crítica
├── models.py                  # Modelos SQLAlchemy (Usuario, Sala, Area, Reservacion, BloqueoTemporal)
├── mailer.py                  # Despachador SMTP multipart (HTML enriquecido + PDF adjunto)
├── seed.py                    # Poblador inicial de la base de datos
├── requirements.txt           # Manifiesto de dependencias exactas
├── README.md                  # Manual técnico y operativo
├── static/
│   ├── css/
│   │   └── styles.css         # Paleta institucional azul marino (#0f172a) y reglas @media print
│   └── img/
│       └── logo_ittg.png      # Escudo institucional del Instituto Tecnológico de Tuxtla Gutiérrez
└── templates/
    ├── base.html              # Layout maestro con navegación condicional por rol
    ├── login.html             # Acceso de usuarios y administradores
    ├── registro.html          # Alta de solicitantes vinculados a un área
    ├── tablero.html           # Matriz visual horizontal interactiva con Seat Lock
    ├── reservar.html          # Formulario de reservación con validación anti-pasados
    ├── mis_reservaciones.html # Módulo personal para consultar y cancelar reservas propias
    ├── admin.html             # Panel administrador (CRUD de salas, áreas y liberación)
    └── reportes.html          # Filtros dinámicos y exportación PDF/impresión
```

---

## 9. Pruebas de Calidad Realizadas (QA)

1. **Prueba de Inmutabilidad:** Los usuarios comunes no pueden adulterar su nombre, correo ni área de adscripción al momento de enviar una solicitud; la sesión autenticada prevalece en el backend.
2. **Prueba de Fechas Pasadas:** El selector HTML restringe fechas anteriores a hoy mediante `min="{{ hoy_str }}"`, y el controlador backend en Python rechaza peticiones manipuladas con fechas previas.
3. **Prueba de Doble Reserva (Stress Test):** Con dos sesiones abiertas simultáneamente intentando seleccionar el mismo bloque de 10:00 a 11:00, la primera obtiene el bloqueo temporal (*Hold* de 5 minutos con cuenta regresiva), mientras la segunda visualiza el slot inhabilitado como "Apartando...". Si ambas intentan confirmar a la fuerza, el bloqueo pesimista en base de datos deniega la segunda transacción.
4. **Prueba de Envío Postal:** Generación del documento ReportLab en memoria y adjunto en correo sin intermediación de enlaces `localhost` vulnerables en redes externas.

---

## 10. Licencia y Créditos

Proyecto desarrollado bajo el marco del maratón de desarrollo institucional TecNM 2026.  
**Desarrollado por:** Nexum Solutions  
- *Project Manager:* Ballinas Santibáñez Omar Alejandro  
- *Analista de Sistemas:* Moguel Jiménez Adriana  
- *Backend 1:* Guzman Chable Jeizer Oswaldo  
- *Backend 2:* Sarmiento Valencia Abner Moisés  
- *Frontend:* Pérez Hernández Christian Yahir  