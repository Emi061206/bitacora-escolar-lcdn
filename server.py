"""
Servidor Backend para Bitácora Escolar
Incluye:
- Base de datos local SQLite (bitacora.db)
- API REST para tareas, materias, promedios, correos y configuración SMTP
- Envío de correos de recordatorios (inmediatos y programados diarios)
- Plantillas HTML profesionales para notificaciones de clases y tareas
- Servidor de archivos estáticos para la interfaz web con soporte multi-hilo
"""

import http.server
import socketserver
import json
import sqlite3
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse, parse_qs
import os
import threading
import time
from datetime import datetime, date, timedelta

PORT = 8000
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bitacora.db')
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Horario base de clases para cálculos y recordatorios
SCHEDULE = [
    {'day': 'Lunes', 'start': 13, 'end': 15, 'name': 'Fundamentos de la Criptografía', 'virtual': False},
    {'day': 'Lunes', 'start': 15, 'end': 17, 'name': 'Base de Datos NoSQL', 'virtual': False},
    {'day': 'Lunes', 'start': 17, 'end': 19, 'name': 'Inteligencia Artificial', 'virtual': False},
    {'day': 'Martes', 'start': 15, 'end': 17, 'name': 'Laboratorio de Innovación Social', 'virtual': False},
    {'day': 'Martes', 'start': 17, 'end': 19, 'name': 'Ecuaciones Diferenciales Aplicadas', 'virtual': False},
    {'day': 'Miércoles', 'start': 15, 'end': 17, 'name': 'Estadística Multivariada', 'virtual': False},
    {'day': 'Miércoles', 'start': 17, 'end': 19, 'name': 'Finanzas Corporativas', 'virtual': False},
    {'day': 'Jueves', 'start': 13, 'end': 15, 'name': 'Laboratorio de Innovación Social', 'virtual': True},
    {'day': 'Jueves', 'start': 15, 'end': 17, 'name': 'Fundamentos de la Criptografía', 'virtual': True},
    {'day': 'Viernes', 'start': 15, 'end': 17, 'name': 'Ecuaciones Diferenciales Aplicadas', 'virtual': True},
    {'day': 'Viernes', 'start': 17, 'end': 19, 'name': 'Finanzas Corporativas', 'virtual': True},
    {'day': 'Sábado', 'start': 9, 'end': 11, 'name': 'Estadística Multivariada', 'virtual': True},
    {'day': 'Sábado', 'start': 11, 'end': 13, 'name': 'Base de Datos NoSQL', 'virtual': True},
    {'day': 'Sábado', 'start': 13, 'end': 15, 'name': 'Inteligencia Artificial', 'virtual': True},
]

SPANISH_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        
        # Tabla de tareas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                due_date TEXT NOT NULL,
                heavy INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Tabla de correos destinatarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Tabla de calificaciones y configuración de materias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grades (
                subject TEXT PRIMARY KEY,
                num_parciales INTEGER DEFAULT 2,
                passing REAL DEFAULT 6.0,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Configuración SMTP para envío de correos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS smtp_config (
                id INTEGER PRIMARY KEY,
                smtp_server TEXT DEFAULT 'smtp.gmail.com',
                smtp_port INTEGER DEFAULT 587,
                sender_email TEXT DEFAULT '',
                sender_password TEXT DEFAULT '',
                use_tls INTEGER DEFAULT 1,
                use_ssl INTEGER DEFAULT 0,
                schedule_hour INTEGER DEFAULT 8,
                schedule_minute INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Insertar fila de configuración inicial si no existe
        cursor.execute('SELECT COUNT(*) as count FROM smtp_config WHERE id = 1')
        if cursor.fetchone()['count'] == 0:
            cursor.execute('''
                INSERT INTO smtp_config (id, smtp_server, smtp_port, sender_email, sender_password, use_tls, use_ssl, schedule_hour, schedule_minute, is_active)
                VALUES (1, 'smtp.gmail.com', 587, '', '', 1, 0, 8, 0, 1)
            ''')
            
        # Tabla de bitácora/logs de envíos de correos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT
            )
        ''')
        
        conn.commit()
    print("[DB] Base de datos SQLite lista:", DB_PATH)


def send_email_message(to_address, subject, html_content, text_content=None):
    """Envía un correo electrónico utilizando la configuración SMTP guardada en SQLite."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM smtp_config WHERE id = 1')
        cfg = cursor.fetchone()
        
    if not cfg or not cfg['sender_email'] or not cfg['sender_password']:
        raise ValueError("La configuración de correo remitente no está completa. Configura el correo y la contraseña en la pestaña Correos.")
        
    sender_email = cfg['sender_email']
    sender_password = cfg['sender_password'].strip()
    smtp_server = cfg['smtp_server']
    smtp_port = int(cfg['smtp_port'])
    use_tls = bool(cfg['use_tls'])
    use_ssl = bool(cfg['use_ssl'])
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"Bitácora Semestre 4 <{sender_email}>"
    msg['To'] = to_address
    
    if text_content:
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    status = 'EXITO'
    error_detail = ''
    
    try:
        if use_ssl or smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=15) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_address, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_address, msg.as_string())
    except Exception as e:
        status = 'ERROR'
        error_detail = str(e)
        raise e
    finally:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO email_logs (sent_at, recipient, subject, status, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), to_address, subject, status, error_detail))
            conn.commit()


def build_reminder_email_html(tasks_info, virtual_classes, target_date=None):
    """Construye un correo HTML con diseño visual premium adaptado a la estética de la Bitácora."""
    if not target_date:
        target_date = date.today()
        
    date_str = target_date.strftime('%d/%m/%Y')
    day_name = SPANISH_DAYS[target_date.weekday()]
    
    # Render clases virtuales
    if virtual_classes:
        classes_html = "".join([f"""
            <div style="background:#F0F7F6;border-left:4px solid #2F6F6B;border-radius:6px;padding:12px 14px;margin-bottom:10px;">
                <div style="font-weight:600;font-size:15px;color:#1E2A28;">{c['name']}</div>
                <div style="font-family:monospace;font-size:13px;color:#2F6F6B;margin-top:3px;">
                    Horario: {c['start']:02d}:00 – {c['end']:02d}:00 (Virtual concurrente)
                </div>
            </div>
        """ for c in virtual_classes])
    else:
        classes_html = """
            <div style="background:#F7F8F5;border:1px dashed #D7DBD0;border-radius:6px;padding:12px;font-size:13.5px;color:#5B6660;text-align:center;">
                No hay clases virtuales programadas para hoy.
            </div>
        """
        
    # Render tareas
    if tasks_info:
        tasks_html = "".join([f"""
            <div style="background:{'#FDF3F3' if t['days_left'] <= 0 else '#FCF7ED' if t['heavy'] or t['days_left'] <= 1 else '#FFFFFF'};border:1px solid {'#E8B4B4' if t['days_left'] <= 0 else '#E8D5A5' if t['heavy'] or t['days_left'] <= 1 else '#D7DBD0'};border-radius:8px;padding:12px 14px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <span style="font-weight:600;font-size:14.5px;color:#1E2A28;">{t['title']}</span>
                        {f'<span style="background:#A63D40;color:#FFFFFF;font-family:monospace;font-size:10px;text-transform:uppercase;padding:2px 6px;border-radius:4px;margin-left:6px;font-weight:bold;">Pesada</span>' if t['heavy'] else ''}
                        <div style="font-size:12.5px;color:#5B6660;margin-top:2px;">Materia: {t['subject']}</div>
                    </div>
                    <div style="font-family:monospace;font-size:12.5px;font-weight:bold;color:{'#A63D40' if t['days_left'] <= 0 else '#B98B2A' if t['days_left'] <= 2 else '#2F6F6B'};">
                        {t['due_badge']}
                    </div>
                </div>
                <div style="font-size:12px;color:#7A8780;margin-top:4px;">
                    Fecha límite: {t['due_date']}
                </div>
            </div>
        """ for t in tasks_info])
    else:
        tasks_html = """
            <div style="background:#F0F7F6;border:1px dashed #B8D5D2;border-radius:6px;padding:16px;font-size:14px;color:#2F6F6B;text-align:center;font-weight:500;">
                No tienes tareas con vencimiento próximo pendiente.
            </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:20px;background-color:#EEF0EA;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1E2A28;">
        <div style="max-width:600px;margin:0 auto;background:#FFFFFF;border:1px solid #D7DBD0;border-radius:12px;overflow:hidden;box-shadow:0 4px 14px rgba(0,0,0,0.05);">
            <!-- Header -->
            <div style="background:#1E2A28;color:#FFFFFF;padding:24px 24px 20px;">
                <div style="font-family:monospace;font-size:11px;letter-spacing:0.05em;color:#A8B5B0;text-transform:uppercase;">LCDN · Semestre 4 · GAM</div>
                <h1 style="margin:6px 0 0;font-size:24px;font-weight:700;letter-spacing:-0.02em;">Recordatorio Diario de Bitácora</h1>
                <p style="margin:4px 0 0;font-size:13.5px;color:#DCEBE9;">{day_name}, {date_str}</p>
            </div>

            <!-- Contenido -->
            <div style="padding:22px 24px;">
                
                <!-- Sección Clases Virtuales de Hoy -->
                <div style="margin-bottom:24px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;border-bottom:1px solid #EEF0EA;padding-bottom:8px;">
                        <h2 style="margin:0;font-size:16px;font-weight:700;color:#2F6F6B;">Clases Virtuales de Hoy ({day_name})</h2>
                    </div>
                    {classes_html}
                </div>

                <!-- Resumen Semanal de Clases Virtuales -->
                <div style="margin-bottom:24px;background:#F7FAF9;border:1px solid #DCEBE9;border-radius:8px;padding:14px;">
                    <h3 style="margin:0 0 8px;font-size:13.5px;font-weight:700;color:#2F6F6B;text-transform:uppercase;letter-spacing:0.03em;">Programa Semanal de Clases Virtuales:</h3>
                    <div style="font-size:12.5px;color:#1E2A28;line-height:1.6;">
                        <div><strong>Jueves:</strong> Laboratorio de Innovación Social (13:00–15:00) · Fundamentos de la Criptografía (15:00–17:00)</div>
                        <div><strong>Viernes:</strong> Ecuaciones Diferenciales Aplicadas (15:00–17:00) · Finanzas Corporativas (17:00–19:00)</div>
                        <div><strong>Sábado:</strong> Estadística Multivariada (09:00–11:00) · Base de Datos NoSQL (11:00–13:00) · Inteligencia Artificial (13:00–15:00)</div>
                    </div>
                </div>

                <!-- Sección Tareas Pendientes -->
                <div>
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;border-bottom:1px solid #EEF0EA;padding-bottom:8px;">
                        <h2 style="margin:0;font-size:16px;font-weight:700;color:#A63D40;">Tareas y Entregas Próximas</h2>
                    </div>
                    {tasks_html}
                </div>

                <!-- Footer -->
                <div style="margin-top:28px;padding-top:16px;border-top:1px solid #EEF0EA;text-align:center;font-size:12px;color:#7A8780;">
                    <p style="margin:0;">Generado automáticamente por tu <strong>Bitácora del Semestre</strong>.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def get_active_reminders_data(target_date=None):
    """Calcula las tareas próximas y clases virtuales para la fecha indicada."""
    if not target_date:
        target_date = date.today()
        
    day_name = SPANISH_DAYS[target_date.weekday()]
    
    # 1. Clases virtuales de hoy
    virtual_classes = [c for c in SCHEDULE if c['day'] == day_name and c['virtual']]
    
    # 2. Tareas pendientes y sus proximidades
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE completed = 0 ORDER BY due_date ASC')
        tasks_rows = cursor.fetchall()
        
    tasks_info = []
    for t in tasks_rows:
        try:
            due = datetime.strptime(t['due_date'], '%Y-%m-%d').date()
            diff = (due - target_date).days
            heavy = bool(t['heavy'])
            
            # Criterio: Mostrar si está vencida, vence hoy (0), o vence en los días de aviso
            should_include = (diff < 0) or (diff == 0) or (not heavy and diff <= 1) or (heavy and diff <= 3) or (diff <= 5)
            
            if should_include:
                if diff < 0:
                    badge = f"Venció hace {abs(diff)} d"
                elif diff == 0:
                    badge = "¡Vence hoy!"
                elif diff == 1:
                    badge = "Vence mañana"
                else:
                    badge = f"Faltan {diff} días"
                    
                tasks_info.append({
                    'id': t['id'],
                    'title': t['title'],
                    'subject': t['subject'],
                    'due_date': t['due_date'],
                    'heavy': heavy,
                    'days_left': diff,
                    'due_badge': badge
                })
        except Exception as e:
            print("Error procesando fecha de tarea:", e)
            
    return tasks_info, virtual_classes


def send_all_reminders():
    """Envía el recordatorio diario a todos los correos registrados en la base de datos."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT email FROM emails')
        email_rows = cursor.fetchall()
        
    recipients = [r['email'] for r in email_rows if r['email']]
    if not recipients:
        return {'success': False, 'message': 'No hay correos destinatarios registrados en la base de datos.'}
        
    today = date.today()
    tasks_info, virtual_classes = get_active_reminders_data(today)
    
    subject = f"Bitácora Semestre 4: Recordatorio {today.strftime('%d/%m/%Y')} — {SPANISH_DAYS[today.weekday()]}"
    html_content = build_reminder_email_html(tasks_info, virtual_classes, today)
    
    results = []
    errors = []
    for email in recipients:
        try:
            send_email_message(email, subject, html_content)
            results.append(email)
        except Exception as e:
            errors.append(f"{email}: {str(e)}")
            
    if errors and not results:
        return {'success': False, 'message': 'Falló el envío de correos: ' + '; '.join(errors)}
    elif errors:
        return {'success': True, 'message': f'Enviado a {len(results)} correos, pero hubo errores en: ' + '; '.join(errors), 'sent_to': results}
    else:
        return {'success': True, 'message': f'Recordatorio enviado con éxito a {len(results)} correo(s).', 'sent_to': results}


last_sent_date = None

def background_scheduler():
    """Hilo en segundo plano que revisa periódicamente si es hora de enviar el recordatorio diario."""
    global last_sent_date
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT schedule_hour, schedule_minute, is_active FROM smtp_config WHERE id = 1')
                cfg = cursor.fetchone()
                
            if cfg and cfg['is_active'] and last_sent_date != today_str:
                target_hour = cfg['schedule_hour'] if cfg['schedule_hour'] is not None else 8
                target_minute = cfg['schedule_minute'] if cfg['schedule_minute'] is not None else 0
                
                if now.hour == target_hour and now.minute >= target_minute:
                    print(f"[{now.strftime('%H:%M:%S')}] Ejecutando recordatorio automático diario programado...")
                    res = send_all_reminders()
                    print(f"Resultado del recordatorio automático: {res}")
                    last_sent_date = today_str
        except Exception as e:
            print("Error en el programador de fondo:", e)
            
        time.sleep(45)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class BitacoraRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Manejador HTTP para la API REST y servir la interfaz web."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode('utf-8')
        return json.loads(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Redireccionar raíz a horarios.html
        if path == '/' or path == '/index.html':
            self.path = '/horarios.html'
            return super().do_GET()
            
        # Endpoints API
        if path == '/api/status':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as tasks_count FROM tasks WHERE completed = 0')
                tasks_count = cursor.fetchone()['tasks_count']
                
                cursor.execute('SELECT COUNT(*) as emails_count FROM emails')
                emails_count = cursor.fetchone()['emails_count']
                
                cursor.execute('SELECT sender_email, smtp_server, is_active, schedule_hour, schedule_minute FROM smtp_config WHERE id = 1')
                smtp = cursor.fetchone()
                
            return self.send_json_response({
                'status': 'online',
                'database': 'SQLite Conectada',
                'tasks_count': tasks_count,
                'emails_count': emails_count,
                'smtp_configured': bool(smtp and smtp['sender_email']),
                'sender_email': smtp['sender_email'] if smtp else '',
                'schedule_hour': smtp['schedule_hour'] if smtp else 8,
                'schedule_minute': smtp['schedule_minute'] if smtp else 0,
                'is_active': bool(smtp['is_active']) if smtp else True,
                'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
        elif path == '/api/tasks':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tasks WHERE completed = 0 ORDER BY due_date ASC')
                rows = cursor.fetchall()
                tasks = [{
                    'id': r['id'],
                    'title': r['title'],
                    'subject': r['subject'],
                    'due': r['due_date'],
                    'heavy': bool(r['heavy'])
                } for r in rows]
            return self.send_json_response({'tareas': tasks})
            
        elif path == '/api/emails':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT email FROM emails ORDER BY id ASC')
                rows = cursor.fetchall()
                emails = [r['email'] for r in rows]
            return self.send_json_response({'correos': emails})
            
        elif path == '/api/grades':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM grades')
                rows = cursor.fetchall()
                grades = {}
                for r in rows:
                    grades[r['subject']] = {
                        'numParciales': r['num_parciales'],
                        'passing': r['passing'],
                        'parciales': json.loads(r['data_json'])
                    }
            return self.send_json_response({'grades': grades})
            
        elif path == '/api/smtp':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT smtp_server, smtp_port, sender_email, use_tls, use_ssl, schedule_hour, schedule_minute, is_active FROM smtp_config WHERE id = 1')
                cfg = cursor.fetchone()
                if cfg:
                    return self.send_json_response({
                        'smtp_server': cfg['smtp_server'],
                        'smtp_port': cfg['smtp_port'],
                        'sender_email': cfg['sender_email'],
                        'has_password': True,
                        'use_tls': bool(cfg['use_tls']),
                        'use_ssl': bool(cfg['use_ssl']),
                        'schedule_hour': cfg['schedule_hour'],
                        'schedule_minute': cfg['schedule_minute'],
                        'is_active': bool(cfg['is_active'])
                    })
                return self.send_json_response({})
                
        elif path == '/api/logs':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM email_logs ORDER BY id DESC LIMIT 15')
                rows = cursor.fetchall()
                logs = [{
                    'id': r['id'],
                    'sent_at': r['sent_at'],
                    'recipient': r['recipient'],
                    'subject': r['subject'],
                    'status': r['status'],
                    'details': r['details']
                } for r in rows]
            return self.send_json_response({'logs': logs})
            
        # Archivos estáticos normales
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            body = self.read_json_body()
        except Exception:
            body = {}
            
        if path == '/api/sync':
            with get_db() as conn:
                cursor = conn.cursor()
                if 'tasks' in body:
                    cursor.execute('DELETE FROM tasks')
                    for t in body['tasks']:
                        cursor.execute('''
                            INSERT OR REPLACE INTO tasks (id, title, subject, due_date, heavy, completed, created_at)
                            VALUES (?, ?, ?, ?, ?, 0, ?)
                        ''', (t['id'], t['title'], t['subject'], t['due'], 1 if t.get('heavy') else 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                if 'emails' in body:
                    cursor.execute('DELETE FROM emails')
                    for em in body['emails']:
                        if em and em.strip():
                            cursor.execute('INSERT OR IGNORE INTO emails (email, created_at) VALUES (?, ?)', (em.strip(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                if 'grades' in body:
                    for subj, g in body['grades'].items():
                        cursor.execute('''
                            INSERT OR REPLACE INTO grades (subject, num_parciales, passing, data_json, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (subj, g.get('numParciales', 2), g.get('passing', 6.0), json.dumps(g.get('parciales', [])), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
            return self.send_json_response({'success': True, 'message': 'Datos sincronizados exitosamente con la base de datos.'})

        elif path == '/api/tasks':
            t = body
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO tasks (id, title, subject, due_date, heavy, completed, created_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                ''', (t['id'], t['title'], t['subject'], t['due'], 1 if t.get('heavy') else 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
            return self.send_json_response({'success': True, 'message': 'Tarea guardada.'})

        elif path == '/api/tasks/delete':
            task_id = body.get('id')
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
                conn.commit()
            return self.send_json_response({'success': True, 'message': 'Tarea eliminada.'})

        elif path == '/api/emails':
            emails = body.get('emails', [])
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM emails')
                for em in emails:
                    if em and em.strip():
                        cursor.execute('INSERT OR IGNORE INTO emails (email, created_at) VALUES (?, ?)', (em.strip(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
            return self.send_json_response({'success': True, 'message': 'Lista de correos actualizada.'})

        elif path == '/api/grades':
            grades = body.get('grades', {})
            with get_db() as conn:
                cursor = conn.cursor()
                for subj, g in grades.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO grades (subject, num_parciales, passing, data_json, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (subj, g.get('numParciales', 2), g.get('passing', 6.0), json.dumps(g.get('parciales', [])), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
            return self.send_json_response({'success': True, 'message': 'Calificaciones guardadas en la base de datos.'})

        elif path == '/api/smtp':
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT sender_password FROM smtp_config WHERE id = 1')
                current = cursor.fetchone()
                current_pwd = current['sender_password'] if current else ''
                
                new_pwd = body.get('sender_password', '')
                password_to_save = new_pwd if new_pwd and new_pwd.strip() else current_pwd
                
                cursor.execute('''
                    UPDATE smtp_config SET
                        smtp_server = ?,
                        smtp_port = ?,
                        sender_email = ?,
                        sender_password = ?,
                        use_tls = ?,
                        use_ssl = ?,
                        schedule_hour = ?,
                        schedule_minute = ?,
                        is_active = ?
                    WHERE id = 1
                ''', (
                    body.get('smtp_server', 'smtp.gmail.com'),
                    int(body.get('smtp_port', 587)),
                    body.get('sender_email', '').strip(),
                    password_to_save,
                    1 if body.get('use_tls', True) else 0,
                    1 if body.get('use_ssl', False) else 0,
                    int(body.get('schedule_hour', 8)),
                    int(body.get('schedule_minute', 0)),
                    1 if body.get('is_active', True) else 0
                ))
                conn.commit()
            return self.send_json_response({'success': True, 'message': 'Configuración de correo guardada con éxito.'})

        elif path == '/api/send-test':
            target_email = body.get('target_email')
            if not target_email:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT email FROM emails LIMIT 1')
                    row = cursor.fetchone()
                    if row:
                        target_email = row['email']
                    else:
                        cursor.execute('SELECT sender_email FROM smtp_config WHERE id = 1')
                        row_smtp = cursor.fetchone()
                        if row_smtp and row_smtp['sender_email']:
                            target_email = row_smtp['sender_email']
                            
            if not target_email:
                return self.send_json_response({'success': False, 'message': 'No hay un correo destinatario especificado.'}, status_code=400)
                
            test_html = f"""
            <div style="font-family:sans-serif;max-width:550px;margin:20px auto;border:1px solid #D7DBD0;border-radius:10px;padding:24px;background:#FFFFFF;">
                <div style="color:#2F6F6B;font-weight:bold;font-size:18px;margin-bottom:8px;">[OK] Conexión SMTP Exitosa</div>
                <p style="color:#1E2A28;font-size:14px;line-height:1.6;">
                    ¡Hola! Este es un correo de prueba enviado desde tu <strong>Bitácora del Semestre</strong> conectada a la base de datos local SQLite.
                </p>
                <div style="background:#EEF0EA;padding:12px;border-radius:6px;font-size:13px;color:#5B6660;margin:16px 0;">
                    Fecha y hora de prueba: <strong>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</strong><br>
                    Servidor: <strong>Activo y listo para enviar recordatorios</strong>
                </div>
                <p style="font-size:12px;color:#7A8780;margin:0;">Todo está configurado correctamente para recibir las alertas de tareas y clases virtuales.</p>
            </div>
            """
            try:
                send_email_message(target_email, "Prueba de conexión: Bitácora Escolar", test_html)
                return self.send_json_response({'success': True, 'message': f'Correo de prueba enviado exitosamente a {target_email}.'})
            except Exception as e:
                return self.send_json_response({'success': False, 'message': f'Error al enviar correo de prueba: {str(e)}'}, status_code=500)

        elif path == '/api/send-reminders':
            try:
                res = send_all_reminders()
                return self.send_json_response(res, status_code=200 if res['success'] else 400)
            except Exception as e:
                return self.send_json_response({'success': False, 'message': f'Error al enviar recordatorios: {str(e)}'}, status_code=500)

        else:
            return self.send_json_response({'error': 'Ruta no encontrada'}, status_code=404)


def run_server():
    init_db()
    
    # Iniciar hilo de programación en segundo plano
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()
    
    with ThreadedTCPServer(("", PORT), BitacoraRequestHandler) as httpd:
        print("=====================================================")
        print("  Servidor Bitacora Escolar iniciado con exito")
        print(f"  URL Local: http://localhost:{PORT}/horarios.html")
        print(f"  Base de datos: {DB_PATH}")
        print("=====================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


if __name__ == '__main__':
    run_server()
