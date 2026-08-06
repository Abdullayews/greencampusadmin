import os
from flask import Flask, request, jsonify, session, render_template_string
from functools import wraps
from config import get_db_connection
from flasgger import Swagger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "kampus-secret-key-2026")
app.config['JSON_AS_ASCII'] = False

Swagger(app)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({"success": False, "message": "İcazə yoxdur!"}), 403
        return f(*args, **kwargs)
    return decorated

def serve_html(filename, **context):
    filepath = os.path.join(TEMPLATES_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if context:
            return render_template_string(content, **context)
        return content
    except FileNotFoundError:
        return jsonify({"success": False, "message": f"{filename} tapılmadı (axtarılan yer: {filepath})"}), 404

@app.route('/')
def index():
    """Tələbə görünüşü səhifəsi"""
    return serve_html('index.html',
        user_name="Tələbə", user_ixtisas="", user_kurs="", user_otaq="",
        is_logged_in=False, name_first="Tələbə", user_initials="T",
        name_short="Tələbə", current_year=2026
    )

@app.route('/admin')
def admin_panel():
    """Admin panel səhifəsi"""
    return serve_html('admin_panel.html')

@app.route('/login', methods=['POST'])
def login():
    """
    Admin girişi
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              example: admin
            sifre:
              type: string
              example: "123"
    responses:
      200:
        description: Giriş nəticəsi
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    data = request.get_json()
    email = data.get('email', '')
    sifre = data.get('sifre', '')
    if email == 'admin' and sifre == '123':
        session['admin_logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Admin məlumatları yanlışdır!"})

@app.route('/logout')
def logout():
    """
    Admin çıxışı
    ---
    tags:
      - Auth
    responses:
      200:
        description: Çıxış nəticəsi
        schema:
          type: object
          properties:
            success:
              type: boolean
            redirect:
              type: string
    """
    session.clear()
    return jsonify({"success": True, "redirect": "/admin"})

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """
    Dashboard statistikası
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Dashboard rəqəmləri
        schema:
          type: object
          properties:
            success:
              type: boolean
            stats:
              type: object
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM students")
            students = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM applications WHERE status='Gözləmədə'")
            apps = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM penalties WHERE status='Ödənilməmiş'")
            penalties = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM rooms")
            rooms = cur.fetchone()['c']
        return jsonify({"success": True, "stats": {"students": students, "apps": apps, "penalties": penalties, "rooms": rooms}})
    finally:
        conn.close()

@app.route('/api/admin/get_students', methods=['GET'])
@admin_required
def get_students():
    """
    Tələbə siyahısı
    ---
    tags:
      - Tələbələr
    responses:
      200:
        description: Tələbə siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, ad_soyad, email, ixtisas, kurs, api_key, universitet, ev_deyisme_isteyi FROM students ORDER BY id ASC")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/get_student_full', methods=['POST'])
@admin_required
def get_student_full():
    """
    Tələbə tam məlumatları
    ---
    tags:
      - Tələbələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Tələbə məlumatları
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("SELECT id, ad_soyad, email, sifre, ixtisas, kurs, api_key, universitet, ev_deyisme_isteyi FROM students WHERE id=%s", [data.get('id')])
            student = cur.fetchone()
            return jsonify({"success": True, "data": student})
    finally:
        conn.close()

@app.route('/api/admin/save_student', methods=['POST'])
@admin_required
def save_student():
    """
    Tələbə yarat / yenilə
    ---
    tags:
      - Tələbələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            ad_soyad:
              type: string
            email:
              type: string
            ixtisas:
              type: string
            kurs:
              type: integer
            universitet:
              type: string
            ev_deyisme_isteyi:
              type: integer
            sifre:
              type: string
            api_key:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            if data.get('id'):
                fields = ["ad_soyad=%s", "email=%s", "ixtisas=%s", "kurs=%s", "universitet=%s", "ev_deyisme_isteyi=%s"]
                vals = [data['ad_soyad'], data['email'], data['ixtisas'], data['kurs'], data.get('universitet','Qarabağ Universiteti'), data.get('ev_deyisme_isteyi',0)]
                if data.get('sifre'):
                    fields.append("sifre=%s")
                    vals.append(data['sifre'])
                if data.get('api_key') is not None:
                    fields.append("api_key=%s")
                    vals.append(data['api_key'])
                vals.append(data['id'])
                cur.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=%s", vals)
            else:
                cur.execute("INSERT INTO students (ad_soyad, email, sifre, ixtisas, kurs, api_key, universitet, ev_deyisme_isteyi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                           [data['ad_soyad'], data['email'], data.get('sifre','12345'), data['ixtisas'], data['kurs'], data.get('api_key'), data.get('universitet','Qarabağ Universiteti'), data.get('ev_deyisme_isteyi',0)])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_student', methods=['POST'])
@admin_required
def delete_student():
    """
    Tələbə sil
    ---
    tags:
      - Tələbələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_rooms', methods=['GET'])
@admin_required
def get_rooms():
    """
    Otaq siyahısı
    ---
    tags:
      - Otaqlar
    responses:
      200:
        description: Otaq siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM rooms ORDER BY id ASC")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_room', methods=['POST'])
@admin_required
def save_room():
    """
    Otaq yarat / yenilə
    ---
    tags:
      - Otaqlar
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: string
            t1..t6:
              type: string
            y1..y6:
              type: string
            s1..s6:
              type: string
            o1..o6:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        for i in range(1,7):
            k = f't{i}'
            if data.get(k) == '':
                data[k] = None
        with conn.cursor() as cur:
            if data.get('id'):
                cur.execute("""UPDATE rooms SET telebe_1_id=%s, yataq_1_status=%s, skaf_1_status=%s, oturacaq_1_status=%s,
                              telebe_2_id=%s, yataq_2_status=%s, skaf_2_status=%s, oturacaq_2_status=%s,
                              telebe_3_id=%s, yataq_3_status=%s, skaf_3_status=%s, oturacaq_3_status=%s,
                              telebe_4_id=%s, yataq_4_status=%s, skaf_4_status=%s, oturacaq_4_status=%s,
                              telebe_5_id=%s, yataq_5_status=%s, skaf_5_status=%s, oturacaq_5_status=%s,
                              telebe_6_id=%s, yataq_6_status=%s, skaf_6_status=%s, oturacaq_6_status=%s
                              WHERE id=%s""",
                           [data['t1'], data['y1'], data['s1'], data['o1'],
                            data['t2'], data['y2'], data['s2'], data['o2'],
                            data['t3'], data['y3'], data['s3'], data['o3'],
                            data['t4'], data['y4'], data['s4'], data['o4'],
                            data['t5'], data['y5'], data['s5'], data['o5'],
                            data['t6'], data['y6'], data['s6'], data['o6'],
                            data['id']])
            else:
                cur.execute("""INSERT INTO rooms (id, telebe_1_id, yataq_1_status, skaf_1_status, oturacaq_1_status,
                              telebe_2_id, yataq_2_status, skaf_2_status, oturacaq_2_status,
                              telebe_3_id, yataq_3_status, skaf_3_status, oturacaq_3_status,
                              telebe_4_id, yataq_4_status, skaf_4_status, oturacaq_4_status,
                              telebe_5_id, yataq_5_status, skaf_5_status, oturacaq_5_status,
                              telebe_6_id, yataq_6_status, skaf_6_status, oturacaq_6_status)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                           [data['id'], data['t1'], data['y1'], data['s1'], data['o1'],
                            data['t2'], data['y2'], data['s2'], data['o2'],
                            data['t3'], data['y3'], data['s3'], data['o3'],
                            data['t4'], data['y4'], data['s4'], data['o4'],
                            data['t5'], data['y5'], data['s5'], data['o5'],
                            data['t6'], data['y6'], data['s6'], data['o6']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_room', methods=['POST'])
@admin_required
def delete_room():
    """
    Otaq sil
    ---
    tags:
      - Otaqlar
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rooms WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_applications', methods=['GET'])
@admin_required
def get_applications():
    """
    Ərizə siyahısı
    ---
    tags:
      - Ərizələr
    responses:
      200:
        description: Ərizə siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT a.id, a.student_id, a.basliq, a.muraciet, a.priority, a.status,
                          DATE_FORMAT(a.created_at, '%d.%m.%Y') as tarix, s.ad_soyad
                          FROM applications a JOIN students s ON a.student_id = s.id
                          ORDER BY a.created_at DESC""")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_application', methods=['POST'])
@admin_required
def save_application():
    """
    Ərizə yarat / yenilə
    ---
    tags:
      - Ərizələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            student_id:
              type: integer
            basliq:
              type: string
            muraciet:
              type: string
            priority:
              type: integer
            status:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        if data.get('student_id') == '':
            return jsonify({"success": False, "message": "Telebe secilmedi"})
        with conn.cursor() as cur:
            if data.get('id'):
                cur.execute("UPDATE applications SET student_id=%s, basliq=%s, muraciet=%s, priority=%s, status=%s WHERE id=%s",
                           [data['student_id'], data['basliq'], data['muraciet'], data['priority'], data['status'], data['id']])
            else:
                cur.execute("INSERT INTO applications (student_id, basliq, muraciet, priority, status) VALUES (%s, %s, %s, %s, %s)",
                           [data['student_id'], data['basliq'], data['muraciet'], data['priority'], data.get('status','Gözləmədə')])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_application', methods=['POST'])
@admin_required
def delete_application():
    """
    Ərizə sil
    ---
    tags:
      - Ərizələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM applications WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/update_app_status', methods=['POST'])
@admin_required
def update_app_status():
    """
    Ərizə statusunu yenilə
    ---
    tags:
      - Ərizələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            status:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("UPDATE applications SET status = %s WHERE id = %s", [data['status'], data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_announcements', methods=['GET'])
@admin_required
def get_announcements():
    """
    Elan siyahısı
    ---
    tags:
      - Elanlar
    responses:
      200:
        description: Elan siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, description, priority, status FROM contents WHERE type='announcement' ORDER BY created_at DESC")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_announcement', methods=['POST'])
@admin_required
def save_announcement():
    """
    Elan yarat / yenilə
    ---
    tags:
      - Elanlar
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            description:
              type: string
            priority:
              type: integer
            status:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            if data.get('id'):
                cur.execute("UPDATE contents SET title=%s, description=%s, priority=%s, status=%s WHERE id=%s",
                           [data['title'], data['description'], data['priority'], data['status'], data['id']])
            else:
                cur.execute("INSERT INTO contents (type, title, description, priority, status) VALUES ('announcement', %s, %s, %s, %s)",
                           [data['title'], data['description'], data['priority'], data['status']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_announcement', methods=['POST'])
@admin_required
def delete_announcement():
    """
    Elan sil
    ---
    tags:
      - Elanlar
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM contents WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_surveys', methods=['GET'])
@admin_required
def get_surveys():
    """
    Sorğu siyahısı
    ---
    tags:
      - Sorğular
    responses:
      200:
        description: Sorğu siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, description, priority, status FROM contents WHERE type='survey' ORDER BY created_at DESC")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_survey', methods=['POST'])
@admin_required
def save_survey():
    """
    Sorğu yarat / yenilə
    ---
    tags:
      - Sorğular
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            description:
              type: string
            priority:
              type: integer
            status:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            if data.get('id'):
                cur.execute("UPDATE contents SET title=%s, description=%s, priority=%s, status=%s WHERE id=%s",
                           [data['title'], data['description'], data['priority'], data['status'], data['id']])
            else:
                cur.execute("INSERT INTO contents (type, title, description, priority, status) VALUES ('survey', %s, %s, %s, %s)",
                           [data['title'], data['description'], data['priority'], data['status']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_survey', methods=['POST'])
@admin_required
def delete_survey():
    """
    Sorğu sil
    ---
    tags:
      - Sorğular
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM contents WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_penalties', methods=['GET'])
@admin_required
def get_penalties():
    """
    Cərimə siyahısı
    ---
    tags:
      - Cərimələr
    responses:
      200:
        description: Cərimə siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT p.id, p.student_id, p.amount, p.reason, p.status, DATE_FORMAT(p.created_at, '%d.%m.%Y') as tarix, s.ad_soyad
                          FROM penalties p JOIN students s ON p.student_id = s.id ORDER BY p.created_at DESC""")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_penalty', methods=['POST'])
@admin_required
def save_penalty():
    """
    Cərimə yarat / yenilə
    ---
    tags:
      - Cərimələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            student_id:
              type: integer
            amount:
              type: number
            reason:
              type: string
            status:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            if data.get('id'):
                fields = ["amount=%s", "reason=%s"]
                vals = [data['amount'], data['reason']]
                if data.get('status'):
                    fields.append("status=%s")
                    vals.append(data['status'])
                vals.append(data['id'])
                cur.execute(f"UPDATE penalties SET {', '.join(fields)} WHERE id=%s", vals)
            else:
                cur.execute("INSERT INTO penalties (student_id, amount, reason) VALUES (%s, %s, %s)",
                           [data['student_id'], data['amount'], data['reason']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/pay_penalty', methods=['POST'])
@admin_required
def pay_penalty():
    """
    Cəriməni ödənilmiş et
    ---
    tags:
      - Cərimələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("UPDATE penalties SET status = 'Ödənilib' WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_penalty', methods=['POST'])
@admin_required
def delete_penalty():
    """
    Cərimə sil
    ---
    tags:
      - Cərimələr
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM penalties WHERE id = %s", [data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_canteen', methods=['GET'])
@admin_required
def get_canteen():
    """
    Yeməkxana menyusu
    ---
    tags:
      - Yeməkxana
    responses:
      200:
        description: Menyu siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, location, day_of_week, meal_name FROM canteen_menu ORDER BY location, day_of_week ASC")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_canteen', methods=['POST'])
@admin_required
def save_canteen():
    """
    Menyu yenilə
    ---
    tags:
      - Yeməkxana
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            id:
              type: integer
            meal_name:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("UPDATE canteen_menu SET meal_name = %s WHERE id = %s", [data['meal_name'], data['id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_laundry', methods=['GET'])
@admin_required
def get_laundry():
    """
    Camaşırxana statusu
    ---
    tags:
      - Camaşırxana
    responses:
      200:
        description: Status siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT l.student_id, l.machine_1_status, l.machine_2_status, l.machine_3_status, s.ad_soyad
                          FROM laundry l JOIN students s ON l.student_id = s.id""")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_laundry', methods=['POST'])
@admin_required
def save_laundry():
    """
    Camaşırxana statusunu yenilə
    ---
    tags:
      - Camaşırxana
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            student_id:
              type: integer
            m1:
              type: string
            m2:
              type: string
            m3:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        if data.get('student_id') == '':
            return jsonify({"success": False, "message": "Telebe secilmedi"})
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO laundry (student_id, machine_1_status, machine_2_status, machine_3_status)
                          VALUES (%s, %s, %s, %s)
                          ON DUPLICATE KEY UPDATE
                          machine_1_status=%s, machine_2_status=%s, machine_3_status=%s""",
                       [data['student_id'], data['m1'], data['m2'], data['m3'], data['m1'], data['m2'], data['m3']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_laundry', methods=['POST'])
@admin_required
def delete_laundry():
    """
    Camaşırxana qeydini sil
    ---
    tags:
      - Camaşırxana
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            student_id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM laundry WHERE student_id = %s", [data['student_id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/get_profiles', methods=['GET'])
@admin_required
def get_profiles():
    """
    Tələbə profil siyahısı
    ---
    tags:
      - Profillər
    responses:
      200:
        description: Profil siyahısı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT sp.student_id, sp.yuxu_rejimi, sp.temizlik, sp.sosial_munasibet, sp.hayat_terzi, s.ad_soyad
                          FROM students_profiles sp JOIN students s ON sp.student_id = s.id""")
            return jsonify({"success": True, "data": cur.fetchall()})
    finally:
        conn.close()

@app.route('/api/admin/save_profile', methods=['POST'])
@admin_required
def save_profile():
    """
    Tələbə profili yarat / yenilə
    ---
    tags:
      - Profillər
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            student_id:
              type: integer
            yuxu_rejimi:
              type: string
            temizlik:
              type: string
            sosial_munasibet:
              type: string
            hayat_terzi:
              type: string
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO students_profiles (student_id, yuxu_rejimi, temizlik, sosial_munasibet, hayat_terzi)
                          VALUES (%s, %s, %s, %s, %s)
                          ON DUPLICATE KEY UPDATE
                          yuxu_rejimi=%s, temizlik=%s, sosial_munasibet=%s, hayat_terzi=%s""",
                       [data['student_id'], data['yuxu_rejimi'], data['temizlik'], data['sosial_munasibet'], data['hayat_terzi'],
                        data['yuxu_rejimi'], data['temizlik'], data['sosial_munasibet'], data['hayat_terzi']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route('/api/admin/delete_profile', methods=['POST'])
@admin_required
def delete_profile():
    """
    Tələbə profili sil
    ---
    tags:
      - Profillər
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            student_id:
              type: integer
    responses:
      200:
        description: Nəticə
        schema:
          type: object
          properties:
            success:
              type: boolean
    """
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]
    try:
        data = request.get_json()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students_profiles WHERE student_id = %s", [data['student_id']])
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
