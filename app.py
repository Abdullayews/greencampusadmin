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


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════
def ok(data=None, message=None, **extra):
    """Uğurlu JSON cavabı"""
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if message:
        resp["message"] = message
    resp.update(extra)
    return jsonify(resp)


def fail(message, status=400):
    """Xətalı JSON cavabı"""
    return jsonify({"success": False, "message": message}), status


# ═══════════════════════════════════════════════════════════
# Decorators
# ═══════════════════════════════════════════════════════════
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return fail("İcazə yoxdur!", 403)
        return f(*args, **kwargs)
    return decorated


def with_db(f):
    """
    Avtomatik DB bağlantısı açan/bağlayan decorator.
    Funksiyaya 'cur' ilk arqument kimi ötürülür.
    Commit/rollback avtomatik idarə olunur.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            conn = get_db_connection()
        except Exception as e:
            return fail(f"DB Bağlantı xətası: {e}", 500)

        try:
            with conn.cursor() as cur:
                result = f(cur, *args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            return fail(f"Əməliyyat xətası: {e}", 500)
        finally:
            conn.close()
    return decorated


# ═══════════════════════════════════════════════════════════
# Template helper
# ═══════════════════════════════════════════════════════════
def serve_html(filename, **context):
    filepath = os.path.join(TEMPLATES_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if context:
            return render_template_string(content, **context)
        return content
    except FileNotFoundError:
        return fail(f"{filename} tapılmadı", 404)


# ═══════════════════════════════════════════════════════════
# Routes — Views
# ═══════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════
# Routes — Auth
# ═══════════════════════════════════════════════════════════
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
    """
    data = request.get_json() or {}
    if data.get('email') == 'admin' and data.get('sifre') == '123':
        session['admin_logged_in'] = True
        return ok()
    return fail("Admin məlumatları yanlışdır!", 401)


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
    """
    session.clear()
    return ok(data={"redirect": "/admin"})


# ═══════════════════════════════════════════════════════════
# Routes — Dashboard
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/stats', methods=['GET'])
@admin_required
@with_db
def admin_stats(cur):
    """
    Dashboard statistikası
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Dashboard rəqəmləri
    """
    stats = {}
    queries = [
        ("students", "SELECT COUNT(*) as c FROM students"),
        ("apps", "SELECT COUNT(*) as c FROM applications WHERE status='Gözləmədə'"),
        ("penalties", "SELECT COUNT(*) as c FROM penalties WHERE status='Ödənilməmiş'"),
        ("rooms", "SELECT COUNT(*) as c FROM rooms"),
    ]
    for key, sql in queries:
        cur.execute(sql)
        stats[key] = cur.fetchone()['c']
    return ok(data={"stats": stats})


# ═══════════════════════════════════════════════════════════
# Routes — Students
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_students', methods=['GET'])
@admin_required
@with_db
def get_students(cur):
    """
    Tələbə siyahısı
    ---
    tags:
      - Tələbələr
    """
    cur.execute("""
        SELECT id, ad_soyad, email, ixtisas, kurs, api_key, universitet, ev_deyisme_isteyi
        FROM students ORDER BY id ASC
    """)
    return ok(data=cur.fetchall())


@app.route('/api/admin/get_student_full', methods=['POST'])
@admin_required
@with_db
def get_student_full(cur):
    """
    Tələbə tam məlumatları
    ---
    tags:
      - Tələbələr
    """
    data = request.get_json() or {}
    cur.execute("""
        SELECT id, ad_soyad, email, sifre, ixtisas, kurs, api_key, universitet, ev_deyisme_isteyi
        FROM students WHERE id=%s
    """, [data.get('id')])
    return ok(data=cur.fetchone())


@app.route('/api/admin/save_student', methods=['POST'])
@admin_required
@with_db
def save_student(cur):
    """
    Tələbə yarat / yenilə
    ---
    tags:
      - Tələbələr
    """
    data = request.get_json() or {}

    if data.get('id'):
        # ── Update ──
        fields = []
        vals = []
        field_map = {
            "ad_soyad": data.get('ad_soyad'),
            "email": data.get('email'),
            "ixtisas": data.get('ixtisas'),
            "kurs": data.get('kurs'),
            "universitet": data.get('universitet', 'Qarabağ Universiteti'),
            "ev_deyisme_isteyi": data.get('ev_deyisme_isteyi', 0),
        }
        for col, val in field_map.items():
            fields.append(f"{col}=%s")
            vals.append(val)

        if data.get('sifre'):
            fields.append("sifre=%s")
            vals.append(data['sifre'])
        if data.get('api_key') is not None:
            fields.append("api_key=%s")
            vals.append(data['api_key'])

        vals.append(data['id'])
        cur.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=%s", vals)
    else:
        # ── Insert ──
        cur.execute("""
            INSERT INTO students (ad_soyad, email, sifre, ixtisas, kurs, api_key, universitet, ev_deyisme_isteyi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            data['ad_soyad'], data['email'], data.get('sifre', '12345'),
            data['ixtisas'], data['kurs'], data.get('api_key'),
            data.get('universitet', 'Qarabağ Universiteti'), data.get('ev_deyisme_isteyi', 0)
        ])
    return ok()


@app.route('/api/admin/delete_student', methods=['POST'])
@admin_required
@with_db
def delete_student(cur):
    """
    Tələbə sil
    ---
    tags:
      - Tələbələr
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM students WHERE id = %s", [data.get('id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Rooms
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_rooms', methods=['GET'])
@admin_required
@with_db
def get_rooms(cur):
    """
    Otaq siyahısı
    ---
    tags:
      - Otaqlar
    """
    cur.execute("SELECT * FROM rooms ORDER BY id ASC")
    return ok(data=cur.fetchall())


@app.route('/api/admin/save_room', methods=['POST'])
@admin_required
@with_db
def save_room(cur):
    """
    Otaq yarat / yenilə
    ---
    tags:
      - Otaqlar
    """
    data = request.get_json() or {}

    # Boş string-ləri None et
    for i in range(1, 7):
        k = f't{i}'
        if data.get(k) == '':
            data[k] = None

    # Dinamik sütunlar və dəyərlər
    cols = []
    vals = []
    for i in range(1, 7):
        cols.extend([
            f'telebe_{i}_id', f'yataq_{i}_status',
            f'skaf_{i}_status', f'oturacaq_{i}_status'
        ])
        vals.extend([
            data.get(f't{i}'), data.get(f'y{i}'),
            data.get(f's{i}'), data.get(f'o{i}')
        ])

    if data.get('id'):
        # UPDATE
        set_clause = ', '.join([f"{c}=%s" for c in cols])
        vals.append(data['id'])
        cur.execute(f"UPDATE rooms SET {set_clause} WHERE id=%s", vals)
    else:
        # INSERT
        cols.insert(0, 'id')
        vals.insert(0, data['id'])
        placeholders = ', '.join(['%s'] * len(cols))
        cols_str = ', '.join(cols)
        cur.execute(f"INSERT INTO rooms ({cols_str}) VALUES ({placeholders})", vals)

    return ok()


@app.route('/api/admin/delete_room', methods=['POST'])
@admin_required
@with_db
def delete_room(cur):
    """
    Otaq sil
    ---
    tags:
      - Otaqlar
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM rooms WHERE id = %s", [data.get('id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Applications
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_applications', methods=['GET'])
@admin_required
@with_db
def get_applications(cur):
    """
    Ərizə siyahısı
    ---
    tags:
      - Ərizələr
    """
    cur.execute("""
        SELECT a.id, a.student_id, a.basliq, a.muraciet, a.priority, a.status,
               DATE_FORMAT(a.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad
        FROM applications a
        JOIN students s ON a.student_id = s.id
        ORDER BY a.created_at DESC
    """)
    return ok(data=cur.fetchall())


@app.route('/api/admin/save_application', methods=['POST'])
@admin_required
@with_db
def save_application(cur):
    """
    Ərizə yarat / yenilə
    ---
    tags:
      - Ərizələr
    """
    data = request.get_json() or {}
    if not data.get('student_id'):
        return fail("Tələbə seçilməyib")

    if data.get('id'):
        cur.execute("""
            UPDATE applications
            SET student_id=%s, basliq=%s, muraciet=%s, priority=%s, status=%s
            WHERE id=%s
        """, [data['student_id'], data['basliq'], data['muraciet'],
              data['priority'], data['status'], data['id']])
    else:
        cur.execute("""
            INSERT INTO applications (student_id, basliq, muraciet, priority, status)
            VALUES (%s, %s, %s, %s, %s)
        """, [data['student_id'], data['basliq'], data['muraciet'],
              data['priority'], data.get('status', 'Gözləmədə')])
    return ok()


@app.route('/api/admin/delete_application', methods=['POST'])
@admin_required
@with_db
def delete_application(cur):
    """
    Ərizə sil
    ---
    tags:
      - Ərizələr
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM applications WHERE id = %s", [data.get('id')])
    return ok()


@app.route('/api/admin/update_app_status', methods=['POST'])
@admin_required
@with_db
def update_app_status(cur):
    """
    Ərizə statusunu yenilə
    ---
    tags:
      - Ərizələr
    """
    data = request.get_json() or {}
    cur.execute("UPDATE applications SET status = %s WHERE id = %s",
                [data.get('status'), data.get('id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Contents (Announcements & Surveys)
# ═══════════════════════════════════════════════════════════
def _get_contents(cur, content_type):
    cur.execute("""
        SELECT id, title, description, priority, status
        FROM contents
        WHERE type=%s ORDER BY created_at DESC
    """, [content_type])
    return ok(data=cur.fetchall())


def _save_content(cur, content_type):
    data = request.get_json() or {}
    if data.get('id'):
        cur.execute("""
            UPDATE contents SET title=%s, description=%s, priority=%s, status=%s
            WHERE id=%s
        """, [data['title'], data['description'], data['priority'], data['status'], data['id']])
    else:
        cur.execute("""
            INSERT INTO contents (type, title, description, priority, status)
            VALUES (%s, %s, %s, %s, %s)
        """, [content_type, data['title'], data['description'], data['priority'], data['status']])
    return ok()


@app.route('/api/admin/get_announcements', methods=['GET'])
@admin_required
@with_db
def get_announcements(cur):
    """
    Elan siyahısı
    ---
    tags:
      - Elanlar
    """
    return _get_contents(cur, 'announcement')


@app.route('/api/admin/save_announcement', methods=['POST'])
@admin_required
@with_db
def save_announcement(cur):
    """
    Elan yarat / yenilə
    ---
    tags:
      - Elanlar
    """
    return _save_content(cur, 'announcement')


@app.route('/api/admin/delete_announcement', methods=['POST'])
@admin_required
@with_db
def delete_announcement(cur):
    """
    Elan sil
    ---
    tags:
      - Elanlar
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM contents WHERE id = %s", [data.get('id')])
    return ok()


@app.route('/api/admin/get_surveys', methods=['GET'])
@admin_required
@with_db
def get_surveys(cur):
    """
    Sorğu siyahısı
    ---
    tags:
      - Sorğular
    """
    return _get_contents(cur, 'survey')


@app.route('/api/admin/save_survey', methods=['POST'])
@admin_required
@with_db
def save_survey(cur):
    """
    Sorğu yarat / yenilə
    ---
    tags:
      - Sorğular
    """
    return _save_content(cur, 'survey')


@app.route('/api/admin/delete_survey', methods=['POST'])
@admin_required
@with_db
def delete_survey(cur):
    """
    Sorğu sil
    ---
    tags:
      - Sorğular
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM contents WHERE id = %s", [data.get('id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Penalties
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_penalties', methods=['GET'])
@admin_required
@with_db
def get_penalties(cur):
    """
    Cərimə siyahısı
    ---
    tags:
      - Cərimələr
    """
    cur.execute("""
        SELECT p.id, p.student_id, p.amount, p.reason, p.status,
               DATE_FORMAT(p.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad
        FROM penalties p
        JOIN students s ON p.student_id = s.id
        ORDER BY p.created_at DESC
    """)
    return ok(data=cur.fetchall())


@app.route('/api/admin/save_penalty', methods=['POST'])
@admin_required
@with_db
def save_penalty(cur):
    """
    Cərimə yarat / yenilə
    ---
    tags:
      - Cərimələr
    """
    data = request.get_json() or {}
    if data.get('id'):
        fields = ["amount=%s", "reason=%s"]
        vals = [data['amount'], data['reason']]
        if data.get('status'):
            fields.append("status=%s")
            vals.append(data['status'])
        vals.append(data['id'])
        cur.execute(f"UPDATE penalties SET {', '.join(fields)} WHERE id=%s", vals)
    else:
        cur.execute("""
            INSERT INTO penalties (student_id, amount, reason)
            VALUES (%s, %s, %s)
        """, [data['student_id'], data['amount'], data['reason']])
    return ok()


@app.route('/api/admin/pay_penalty', methods=['POST'])
@admin_required
@with_db
def pay_penalty(cur):
    """
    Cəriməni ödənilmiş et
    ---
    tags:
      - Cərimələr
    """
    data = request.get_json() or {}
    cur.execute("UPDATE penalties SET status = 'Ödənilib' WHERE id = %s", [data.get('id')])
    return ok()


@app.route('/api/admin/delete_penalty', methods=['POST'])
@admin_required
@with_db
def delete_penalty(cur):
    """
    Cərimə sil
    ---
    tags:
      - Cərimələr
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM penalties WHERE id = %s", [data.get('id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Canteen
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_canteen', methods=['GET'])
@admin_required
@with_db
def get_canteen(cur):
    """
    Yeməkxana menyusu
    ---
    tags:
      - Yeməkxana
    """
    cur.execute("""
        SELECT id, location, day_of_week, meal_name
        FROM canteen_menu
        ORDER BY location, day_of_week ASC
    """)
    return ok(data=cur.fetchall())


@app.route('/api/admin/save_canteen', methods=['POST'])
@admin_required
@with_db
def save_canteen(cur):
    """
    Menyu yenilə
    ---
    tags:
      - Yeməkxana
    """
    data = request.get_json() or {}
    cur.execute("UPDATE canteen_menu SET meal_name = %s WHERE id = %s",
                [data.get('meal_name'), data.get('id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Laundry
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_laundry', methods=['GET'])
@admin_required
@with_db
def get_laundry(cur):
    """
    Camaşırxana statusu
    ---
    tags:
      - Camaşırxana
    """
    cur.execute("""
        SELECT l.student_id, l.machine_1_status, l.machine_2_status, l.machine_3_status, s.ad_soyad
        FROM laundry l
        JOIN students s ON l.student_id = s.id
    """)
    return ok(data=cur.fetchall())


@app.route('/api/admin/save_laundry', methods=['POST'])
@admin_required
@with_db
def save_laundry(cur):
    """
    Camaşırxana statusunu yenilə
    ---
    tags:
      - Camaşırxana
    """
    data = request.get_json() or {}
    if not data.get('student_id'):
        return fail("Tələbə seçilməyib")
    cur.execute("""
        INSERT INTO laundry (student_id, machine_1_status, machine_2_status, machine_3_status)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        machine_1_status=%s, machine_2_status=%s, machine_3_status=%s
    """, [data['student_id'], data['m1'], data['m2'], data['m3'],
          data['m1'], data['m2'], data['m3']])
    return ok()


@app.route('/api/admin/delete_laundry', methods=['POST'])
@admin_required
@with_db
def delete_laundry(cur):
    """
    Camaşırxana qeydini sil
    ---
    tags:
      - Camaşırxana
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM laundry WHERE student_id = %s", [data.get('student_id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Routes — Profiles
# ═══════════════════════════════════════════════════════════
@app.route('/api/admin/get_profiles', methods=['GET'])
@admin_required
@with_db
def get_profiles(cur):
    """
    Tələbə profil siyahısı
    ---
    tags:
      - Profillər
    """
    cur.execute("""
        SELECT sp.student_id, sp.yuxu_rejimi, sp.temizlik, sp.sosial_munasibet, sp.hayat_terzi, s.ad_soyad
        FROM students_profiles sp
        JOIN students s ON sp.student_id = s.id
    """)
    return ok(data=cur.fetchall())


@app.route('/api/admin/save_profile', methods=['POST'])
@admin_required
@with_db
def save_profile(cur):
    """
    Tələbə profili yarat / yenilə
    ---
    tags:
      - Profillər
    """
    data = request.get_json() or {}
    cur.execute("""
        INSERT INTO students_profiles (student_id, yuxu_rejimi, temizlik, sosial_munasibet, hayat_terzi)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        yuxu_rejimi=%s, temizlik=%s, sosial_munasibet=%s, hayat_terzi=%s
    """, [data['student_id'], data['yuxu_rejimi'], data['temizlik'],
          data['sosial_munasibet'], data['hayat_terzi'],
          data['yuxu_rejimi'], data['temizlik'],
          data['sosial_munasibet'], data['hayat_terzi']])
    return ok()


@app.route('/api/admin/delete_profile', methods=['POST'])
@admin_required
@with_db
def delete_profile(cur):
    """
    Tələbə profili sil
    ---
    tags:
      - Profillər
    """
    data = request.get_json() or {}
    cur.execute("DELETE FROM students_profiles WHERE student_id = %s", [data.get('student_id')])
    return ok()


# ═══════════════════════════════════════════════════════════
# Error Handlers
# ═══════════════════════════════════════════════════════════
@app.errorhandler(404)
def not_found(e):
    return fail("Səhifə tapılmadı", 404)


@app.errorhandler(500)
def server_error(e):
    return fail("Daxili server xətası", 500)


@app.errorhandler(403)
def forbidden(e):
    return fail("İcazə yoxdur!", 403)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
