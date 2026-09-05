import urllib.request
import json
import sqlite3

def run_tests():
    print("=== Iniciando Verificacion de Endpoints y Base de Datos ===")
    
    # 1. Test GET /api/status
    res = urllib.request.urlopen('http://localhost:8000/api/status')
    status_data = json.loads(res.read().decode('utf-8'))
    print("1. Status:", status_data)
    assert status_data['status'] == 'online', "El servidor debe reportar estado online"
    
    # 2. Test POST /api/tasks (Agregar tarea)
    task_payload = json.dumps({
        'id': 't_test_01',
        'title': 'Investigacion de Criptografia de Curva Eliptica',
        'subject': 'Fundamentos de la Criptografía',
        'due': '2026-09-08',
        'heavy': True
    }).encode('utf-8')
    req = urllib.request.Request('http://localhost:8000/api/tasks', data=task_payload, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    print("2. POST /api/tasks:", json.loads(res.read().decode('utf-8')))
    
    # 3. Test GET /api/tasks
    res = urllib.request.urlopen('http://localhost:8000/api/tasks')
    tasks_data = json.loads(res.read().decode('utf-8'))
    print("3. GET /api/tasks (conteo):", len(tasks_data['tareas']))
    assert any(t['id'] == 't_test_01' for t in tasks_data['tareas']), "La tarea agregada debe estar en la lista"

    # 4. Test POST /api/emails (Guardar correos)
    emails_payload = json.dumps({
        'emails': ['estudiante1@alumno.mx', 'estudiante2@alumno.mx']
    }).encode('utf-8')
    req = urllib.request.Request('http://localhost:8000/api/emails', data=emails_payload, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    print("4. POST /api/emails:", json.loads(res.read().decode('utf-8')))
    
    # 5. Test GET /api/emails
    res = urllib.request.urlopen('http://localhost:8000/api/emails')
    emails_data = json.loads(res.read().decode('utf-8'))
    print("5. GET /api/emails:", emails_data['correos'])
    assert len(emails_data['correos']) == 2, "Deben existir 2 correos registrados"
    
    # 6. Test Base de Datos SQLite Directamente
    conn = sqlite3.connect('bitacora.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM tasks')
    tasks_count_db = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM emails')
    emails_count_db = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM smtp_config')
    smtp_count_db = cursor.fetchone()[0]
    conn.close()
    
    print(f"6. Verificacion SQLite directa: {tasks_count_db} tareas, {emails_count_db} correos, {smtp_count_db} fila smtp_config")
    assert tasks_count_db >= 1, "Debe haber al menos 1 tarea en la base de datos"
    assert emails_count_db == 2, "Debe haber 2 correos en la base de datos"
    assert smtp_count_db == 1, "Debe existir la configuracion smtp en la base de datos"
    
    # 7. Test Servidor de Archivos Estaticos (horarios.html)
    res_html = urllib.request.urlopen('http://localhost:8000/horarios.html')
    html_content = res_html.read().decode('utf-8')
    assert 'Bitácora del semestre' in html_content or 'Bitacora' in html_content, "horarios.html debe cargarse correctamente"
    print("7. Servidor estatico: horarios.html cargado con exito (", len(html_content), "bytes )")
    
    print("\n[OK] TODAS LAS PRUEBAS AUTOMATIZADAS PASARON EXITOSAMENTE.")

if __name__ == '__main__':
    run_tests()
