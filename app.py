import os
import secrets
from functools import wraps

from flask import Flask, request, jsonify, session, render_template_string
from pymysql.err import IntegrityError

from config import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__)

ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASS = os.getenv('ADMIN_PASS', '123')

_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    _key_path = os.path.join(BASE_DIR, 'secret_key.txt')
    if os.path.exists(_key_path):
        with open(_key_path, 'r') as f:
            _secret_key = f.read().strip()
    if not _secret_key:
        _secret_key = secrets.token_hex(32)
        with open(_key_path, 'w') as f:
            f.write(_secret_key)
app.secret_key = _secret_key

app.config['JSON_AS_ASCII'] = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ok(data=None, message=None, **extra):
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if message:
        resp["message"] = message
    resp.update(extra)
    return jsonify(resp)


def fail(message, status=400):
    return jsonify({"success": False, "message": message}), status


def clean_val(val):
    if val is None:
        return None
    val = str(val).strip()
    return val if val else None


def qarg(name):
    """Query parametrini təmiz oxuyur (SQL axtarış filtrləri üçün)."""
    return (request.args.get(name) or '').strip()


def get_pagination_params():
    """Səhifələmə: səhifə başına maksimum 20 item."""
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get('per_page', 20))
    except (TypeError, ValueError):
        per_page = 20
    return max(page, 1), min(per_page, 20)


def room_cins_by_id(room_id):
    """Bina konvensiyası: 101-120 oğlan, 121-140 qız binası."""
    try:
        rid = int(room_id)
    except (TypeError, ValueError):
        return None
    if 101 <= rid <= 120:
        return 'Kişi'
    if 121 <= rid <= 140:
        return 'Qadın'
    return None


def remove_student_from_room(cur, student_id):
    cur.execute("UPDATE room_slots SET student_id = NULL WHERE student_id = %s", (student_id,))


def sync_ev_statuses(cur):
    cur.execute(
        "UPDATE students SET ev = 'Ev seçilib' "
        "WHERE id IN (SELECT student_id FROM room_slots WHERE student_id IS NOT NULL)"
    )
    cur.execute(
        "UPDATE students SET ev = 'Ev seçilməyib' "
        "WHERE ev = 'Ev seçilib' "
        "AND id NOT IN (SELECT student_id FROM room_slots WHERE student_id IS NOT NULL)"
    )


def dissolve_group_if_empty(cur, group_id):
    if group_id is None:
        return
    cur.execute("SELECT COUNT(*) AS c FROM students WHERE group_id = %s", (group_id,))
    if cur.fetchone()['c'] == 0:
        cur.execute("DELETE FROM student_groups WHERE id = %s", (group_id,))


def log_admin(cur, action, entity='', entity_id='', details=''):
    """Bütün admin əməliyyatlarını admin_logs cədvəlinə yazır."""
    try:
        cur.execute(
            "INSERT INTO admin_logs (admin_user, action, entity, entity_id, details) "
            "VALUES (%s, %s, %s, %s, %s)",
            (session.get('admin_user', 'admin'), action, entity, str(entity_id or ''), details or '')
        )
    except Exception:
        pass  # log yazılışı əsas əməliyyatı pozmasın


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return fail("İcazə yoxdur!", 403)
        return f(*args, **kwargs)
    return decorated


def with_db(f):
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
        except IntegrityError as e:
            conn.rollback()
            err_msg = str(e)
            if 'Duplicate entry' in err_msg and 'email' in err_msg:
                return fail("Bu email ilə tələbə artıq mövcuddur!", 400)
            if 'Duplicate entry' in err_msg and 'student_id' in err_msg:
                return fail("Bu tələbə artıq bir yerdə yaşayır!", 400)
            return fail(f"Məlumat uyğunsuzluğu: {e}", 400)
        except Exception as e:
            conn.rollback()
            return fail(f"Əməliyyat xətası: {e}", 500)
        finally:
            conn.close()
    return decorated


# ---------------------------------------------------------------------------
# Template helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return serve_html('index.html')


@app.route('/admin')
def admin_panel():
    return serve_html('index.html')


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    if data.get('email') == ADMIN_USER and data.get('sifre') == ADMIN_PASS:
        session['admin_logged_in'] = True
        session['admin_user'] = data.get('email')
        return ok()
    return fail("Admin məlumatları yanlışdır!", 401)


@app.route('/logout')
def logout():
    session.clear()
    return ok(data={"redirect": "/"})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
@with_db
def admin_stats(cur):
    stats = {}
    queries = [
        ("students", "SELECT COUNT(*) as c FROM students"),
        ("rooms", "SELECT COUNT(*) as c FROM rooms"),
        ("apps", "SELECT COUNT(*) as c FROM applications WHERE status='Gözləmədə'"),
        ("penalties", "SELECT COUNT(*) as c FROM penalties WHERE status='Ödənilməmiş'"),
        ("groups", "SELECT COUNT(DISTINCT group_id) as c FROM students WHERE group_id IS NOT NULL"),
        ("requests", "SELECT COUNT(*) as c FROM home_requests WHERE status='Gözləmədə'"),
    ]
    for key, sql in queries:
        cur.execute(sql)
        stats[key] = cur.fetchone()['c']
    return ok(stats=stats)


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_students', methods=['GET'])
@admin_required
@with_db
def get_students(cur):
    page, per_page = get_pagination_params()
    where, params = ["1=1"], []

    v = qarg('ad_soyad')
    if v: where.append("s.ad_soyad LIKE %s"); params.append(f"%{v}%")
    v = qarg('email')
    if v: where.append("s.email LIKE %s"); params.append(f"%{v}%")
    v = qarg('ixtisas')
    if v: where.append("s.ixtisas LIKE %s"); params.append(f"%{v}%")
    v = qarg('kurs')
    if v: where.append("s.kurs LIKE %s"); params.append(f"%{v}%")
    v = qarg('cins')
    if v: where.append("s.cins = %s"); params.append(v)
    v = qarg('ev')
    if v: where.append("s.ev = %s"); params.append(v)
    v = qarg('otaq')
    if v: where.append("rs.room_id LIKE %s"); params.append(f"%{v}%")
    v = qarg('api_key')
    if v == 'var': where.append("s.api_key IS NOT NULL AND s.api_key != ''")
    elif v == 'yoxdur': where.append("(s.api_key IS NULL OR s.api_key = '')")
    v = qarg('ev_deyisme_isteyi')
    if v == 'var': where.append("s.ev_deyisme_isteyi = 1")
    elif v == 'yoxdur': where.append("COALESCE(s.ev_deyisme_isteyi, 0) = 0")

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"SELECT COUNT(*) as c FROM students s LEFT JOIN room_slots rs ON rs.student_id = s.id {where_clause}", params)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT s.id, s.ad_soyad, s.email, s.ixtisas, s.kurs, s.api_key, s.universitet,
               s.ev_deyisme_isteyi, s.cins, s.ev, rs.room_id AS otaq
        FROM students s
        LEFT JOIN room_slots rs ON rs.student_id = s.id
        {where_clause}
        ORDER BY s.id ASC LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/get_students_light', methods=['GET'])
@admin_required
@with_db
def get_students_light(cur):
    """Modal seçimləri üçün yüngül siyahı."""
    cur.execute("SELECT id, ad_soyad, cins FROM students ORDER BY ad_soyad ASC")
    return ok(data=cur.fetchall())


@app.route('/api/admin/get_student_full', methods=['POST'])
@admin_required
@with_db
def get_student_full(cur):
    data = request.get_json() or {}
    cur.execute("""
        SELECT s.id, s.ad_soyad, s.email, s.ixtisas, s.kurs, s.api_key, s.universitet,
               s.ev_deyisme_isteyi, s.cins, s.ev, rs.room_id AS otaq
        FROM students s
        LEFT JOIN room_slots rs ON rs.student_id = s.id
        WHERE s.id = %s
    """, [data.get('id')])
    return ok(data=cur.fetchone())


@app.route('/api/admin/save_student', methods=['POST'])
@admin_required
@with_db
def save_student(cur):
    data = request.get_json() or {}

    cins = data.get('cins') or 'Kişi'
    if cins not in ('Kişi', 'Qadın'):
        cins = 'Kişi'
    ev = data.get('ev') or 'Ev seçilməyib'
    if ev not in ('Ev seçilib', 'Ev seçilməyib', 'Rədd edilib'):
        ev = 'Ev seçilməyib'

    if data.get('id'):
        student_id = data['id']

        cur.execute("""
            SELECT r.cins FROM room_slots rs JOIN rooms r ON r.id = rs.room_id
            WHERE rs.student_id = %s
        """, (student_id,))
        room_row = cur.fetchone()
        if room_row and room_row['cins'] and room_row['cins'] != cins:
            return fail("Tələbə hazırda əks cinsə aid evdə yaşayır — əvvəlcə Otaqlar bölməsindən çıxarın!", 400)

        fields, vals = [], []
        field_map = {
            "ad_soyad": data.get('ad_soyad'),
            "email": data.get('email'),
            "ixtisas": clean_val(data.get('ixtisas')),
            "universitet": data.get('universitet', 'Qarabağ Universiteti'),
            "cins": cins,
            "ev": ev,
            "ev_deyisme_isteyi": int(data.get('ev_deyisme_isteyi', 0) or 0),
            "kurs": clean_val(data.get('kurs')) or '1',
            "api_key": clean_val(data.get('api_key')),
        }
        if data.get('sifre'):
            field_map['sifre'] = data['sifre']
        for col, val in field_map.items():
            fields.append(f"{col}=%s")
            vals.append(val)
        vals.append(student_id)
        cur.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=%s", vals)

        log_admin(cur, 'Tələbə yeniləndi', 'Tələbə', student_id,
                  f"{data.get('ad_soyad')} — cins: {cins}, ev: {ev}")
    else:
        cur.execute("""
            INSERT INTO students (ad_soyad, email, sifre, ixtisas, kurs, api_key,
                                  universitet, ev_deyisme_isteyi, cins, ev)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            data['ad_soyad'], data['email'], data.get('sifre', '12345'),
            clean_val(data.get('ixtisas')), clean_val(data.get('kurs')) or '1',
            clean_val(data.get('api_key')), data.get('universitet', 'Qarabağ Universiteti'),
            int(data.get('ev_deyisme_isteyi', 0) or 0), cins, ev
        ])
        student_id = cur.lastrowid

        log_admin(cur, 'Tələbə yaradıldı', 'Tələbə', student_id,
                  f"{data.get('ad_soyad')} — cins: {cins}, email: {data.get('email')}")

    if ev != 'Ev seçilib':
        remove_student_from_room(cur, student_id)

    return ok()


# Silmə: həm tək, həm cəm URL (404-ün qarşısını alır)
@app.route('/api/admin/delete_student', methods=['POST'])
@app.route('/api/admin/delete_students', methods=['POST'])
@admin_required
@with_db
def delete_student(cur):
    data = request.get_json() or {}
    student_id = data.get('id')

    cur.execute("SELECT ad_soyad, group_id FROM students WHERE id = %s", (student_id,))
    row = cur.fetchone()
    name = row['ad_soyad'] if row else ''
    gid = row['group_id'] if row else None

    cur.execute("UPDATE room_slots SET student_id = NULL WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM students_profiles WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM laundry WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM penalties WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM applications WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM home_request_votes WHERE voter_id = %s", (student_id,))
    cur.execute(
        "DELETE FROM home_request_votes WHERE request_id IN "
        "(SELECT id FROM (SELECT id FROM home_requests WHERE target_id = %s OR requester_id = %s) t)",
        (student_id, student_id)
    )
    cur.execute("DELETE FROM home_requests WHERE target_id = %s OR requester_id = %s", (student_id, student_id))
    cur.execute("DELETE FROM students WHERE id = %s", (student_id,))

    if gid:
        dissolve_group_if_empty(cur, gid)

    log_admin(cur, 'Tələbə silindi', 'Tələbə', student_id,
              f"{name} — bütün bağlı məlumatlar silindi")
    return ok()


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_rooms', methods=['GET'])
@admin_required
@with_db
def get_rooms(cur):
    page, per_page = get_pagination_params()

    # Self-heal: slot sətirləri yaradılmamış evlər üçün avtomatik yaradılır
    cur.execute("""
        INSERT IGNORE INTO room_slots (room_id, slot)
        SELECT r.id, s.slot
        FROM rooms r
        JOIN (SELECT 1 AS slot UNION SELECT 2 UNION SELECT 3
              UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) s
             ON s.slot <= COALESCE(r.capacity, 6)
        LEFT JOIN room_slots rs ON rs.room_id = r.id AND rs.slot = s.slot
        WHERE rs.room_id IS NULL
    """)

    where, params = ["1=1"], []
    v = qarg('id')
    if v: where.append("r.id LIKE %s"); params.append(f"%{v}%")
    v = qarg('cins')
    if v: where.append("r.cins = %s"); params.append(v)

    having, hparams = [], []
    v = qarg('dolu')
    if v: having.append("CAST(COALESCE(SUM(rs.student_id IS NOT NULL),0) AS CHAR) LIKE %s"); hparams.append(f"%{v}%")
    v = qarg('occupants')
    if v: having.append("COALESCE(GROUP_CONCAT(s.ad_soyad SEPARATOR ', '),'') LIKE %s"); hparams.append(f"%{v}%")

    where_clause = "WHERE " + " AND ".join(where)
    having_clause = ("HAVING " + " AND ".join(having)) if having else ""
    offset = (page - 1) * per_page

    base = f"""
        FROM rooms r
        LEFT JOIN room_slots rs ON rs.room_id = r.id
        LEFT JOIN students s ON s.id = rs.student_id
        {where_clause}
        GROUP BY r.id, r.capacity, r.cins
        {having_clause}
    """
    cur.execute(f"SELECT COUNT(*) as c FROM (SELECT r.id {base}) x", params + hparams)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT r.id, r.capacity, r.cins,
               CAST(COALESCE(SUM(rs.student_id IS NOT NULL), 0) AS SIGNED) AS dolu
        {base}
        ORDER BY r.id ASC LIMIT %s OFFSET %s
    """, params + hparams + [per_page, offset])
    rooms = cur.fetchall()

    if rooms:
        ids = [r['id'] for r in rooms]
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"""
            SELECT rs.room_id, rs.slot, rs.student_id, rs.yataq_status, rs.skaf_status,
                   rs.oturacaq_status, s.ad_soyad
            FROM room_slots rs
            LEFT JOIN students s ON s.id = rs.student_id
            WHERE rs.room_id IN ({placeholders})
            ORDER BY rs.room_id, rs.slot
        """, ids)
        slot_rows = cur.fetchall()
        for r in rooms:
            r['slots'] = [dict(sr) for sr in slot_rows if sr['room_id'] == r['id']]

    return ok(data=rooms, total=total, page=page, per_page=per_page)


@app.route('/api/admin/save_room', methods=['POST'])
@admin_required
@with_db
def save_room(cur):
    data = request.get_json() or {}

    room_id = data.get('id')
    try:
        room_id = int(room_id) if room_id else None
    except (TypeError, ValueError):
        return fail("Otaq nömrəsi düzgün deyil", 400)
    if not room_id:
        return fail("Otaq nömrəsi daxil edilməyib", 400)

    try:
        capacity = int(data.get('capacity', 6))
    except (TypeError, ValueError):
        capacity = 6
    capacity = max(1, min(capacity, 6))

    cins = room_cins_by_id(room_id) or clean_val(data.get('cins'))

    placed = []
    for i in range(1, capacity + 1):
        t = data.get(f't{i}')
        if t:
            try:
                t = int(t)
            except (TypeError, ValueError):
                return fail(f"{i}-ci yerdəki tələbə ID-si düzgün deyil", 400)
            if t in placed:
                return fail("Eyni tələbə birdən çox yerdə seçilib!", 400)
            placed.append(t)

    cur.execute("SELECT 1 FROM rooms WHERE id = %s", (room_id,))
    exists = cur.fetchone() is not None

    if exists:
        cur.execute("UPDATE rooms SET capacity = %s, cins = %s WHERE id = %s", (capacity, cins, room_id))
        for i in range(1, capacity + 1):
            cur.execute("INSERT IGNORE INTO room_slots (room_id, slot) VALUES (%s, %s)", (room_id, i))
        cur.execute("DELETE FROM room_slots WHERE room_id = %s AND slot > %s", (room_id, capacity))
    else:
        cur.execute("INSERT INTO rooms (id, capacity, cins) VALUES (%s, %s, %s)", (room_id, capacity, cins))
        for i in range(1, capacity + 1):
            cur.execute(
                "INSERT INTO room_slots (room_id, slot, student_id, yataq_status, skaf_status, oturacaq_status) "
                "VALUES (%s, %s, NULL, 'Yaxşı', 'Yaxşı', 'Yaxşı')",
                (room_id, i)
            )

    for i in range(1, capacity + 1):
        t = data.get(f't{i}')
        t = int(t) if t else None
        y = data.get(f'y{i}') or 'Yaxşı'
        s = data.get(f's{i}') or 'Yaxşı'
        o = data.get(f'o{i}') or 'Yaxşı'

        if t is not None:
            cur.execute("SELECT cins FROM students WHERE id = %s", (t,))
            st = cur.fetchone()
            if not st:
                return fail(f"{i}-ci yerdəki tələbə (ID {t}) tapılmadı!", 400)
            if cins and st['cins'] != cins:
                return fail(f"{i}-ci yerdəki tələbənin cinsi otağın cinsinə uyğun gəlmir!", 400)
            cur.execute(
                "UPDATE room_slots SET student_id = NULL WHERE student_id = %s "
                "AND NOT (room_id = %s AND slot = %s)",
                (t, room_id, i)
            )

        cur.execute(
            "UPDATE room_slots SET student_id = %s, yataq_status = %s, skaf_status = %s, oturacaq_status = %s "
            "WHERE room_id = %s AND slot = %s",
            (t, y, s, o, room_id, i)
        )

    sync_ev_statuses(cur)

    log_admin(cur, 'Otaq yeniləndi' if exists else 'Otaq yaradıldı', 'Otaq', room_id,
              f"Ev {room_id} — cins: {cins or '-'}, tutum: {capacity}, yerləşən: {len(placed)}")
    return ok()


# Silmə: həm tək, həm cəm URL
@app.route('/api/admin/delete_room', methods=['POST'])
@app.route('/api/admin/delete_rooms', methods=['POST'])
@admin_required
@with_db
def delete_room(cur):
    data = request.get_json() or {}
    room_id = data.get('id')

    cur.execute("SELECT COUNT(*) AS c FROM room_slots WHERE room_id = %s AND student_id IS NOT NULL", (room_id,))
    dolu = cur.fetchone()['c']

    cur.execute(
        "UPDATE students SET ev = 'Ev seçilməyib' "
        "WHERE id IN (SELECT student_id FROM room_slots WHERE room_id = %s AND student_id IS NOT NULL)",
        (room_id,)
    )
    cur.execute("DELETE FROM room_slots WHERE room_id = %s", (room_id,))
    cur.execute("DELETE FROM rooms WHERE id = %s", (room_id,))

    log_admin(cur, 'Otaq silindi', 'Otaq', room_id, f"Ev {room_id} — {dolu} sakin çıxarıldı")
    return ok()


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_applications', methods=['GET'])
@admin_required
@with_db
def get_applications(cur):
    page, per_page = get_pagination_params()
    where, params = ["1=1"], []

    v = qarg('ad_soyad')
    if v: where.append("s.ad_soyad LIKE %s"); params.append(f"%{v}%")
    v = qarg('muraciet')
    if v:
        where.append("(a.basliq LIKE %s OR a.muraciet LIKE %s)")
        params.extend([f"%{v}%", f"%{v}%"])
    v = qarg('status')
    if v: where.append("a.status = %s"); params.append(v)

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT COUNT(*) as c FROM applications a
        JOIN students s ON a.student_id = s.id {where_clause}
    """, params)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT a.id, a.student_id, a.basliq, a.muraciet, a.priority, a.status, a.notlar,
               DATE_FORMAT(a.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad
        FROM applications a
        JOIN students s ON a.student_id = s.id
        {where_clause}
        ORDER BY a.created_at DESC LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/save_application', methods=['POST'])
@admin_required
@with_db
def save_application(cur):
    data = request.get_json() or {}
    if not data.get('student_id'):
        return fail("Tələbə seçilməyib")

    status = data.get('status', 'Gözləmədə')
    notlar = clean_val(data.get('notlar'))
    if status == 'Təsdiqləndi' and not notlar:
        notlar = 'Müraciətiniz təsdiqləndi.'

    if data.get('id'):
        cur.execute("""
            UPDATE applications
            SET student_id=%s, basliq=%s, muraciet=%s, priority=%s, status=%s, notlar=%s
            WHERE id=%s
        """, [data['student_id'], data['basliq'], data['muraciet'],
              data['priority'], status, notlar, data['id']])
        log_admin(cur, 'Müraciət yeniləndi', 'Müraciət', data['id'],
                  f"{data.get('basliq')} — status: {status}")
    else:
        cur.execute("""
            INSERT INTO applications (student_id, basliq, muraciet, priority, status, notlar)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [data['student_id'], data['basliq'], data['muraciet'],
              data['priority'], status, notlar])
        log_admin(cur, 'Müraciət yaradıldı', 'Müraciət', cur.lastrowid,
                  f"{data.get('basliq')} — status: {status}")
    return ok()


# Silmə: həm tək, həm cəm URL
@app.route('/api/admin/delete_application', methods=['POST'])
@app.route('/api/admin/delete_applications', methods=['POST'])
@admin_required
@with_db
def delete_application(cur):
    data = request.get_json() or {}
    cur.execute("SELECT basliq FROM applications WHERE id = %s", (data.get('id'),))
    row = cur.fetchone()
    cur.execute("DELETE FROM applications WHERE id = %s", [data.get('id')])
    log_admin(cur, 'Müraciət silindi', 'Müraciət', data.get('id'),
              row['basliq'] if row else '')
    return ok()


@app.route('/api/admin/update_app_status', methods=['POST'])
@admin_required
@with_db
def update_app_status(cur):
    data = request.get_json() or {}
    status = data.get('status')
    notlar = clean_val(data.get('notlar'))

    if status == 'Təsdiqləndi' and not notlar:
        cur.execute("SELECT notlar FROM applications WHERE id = %s", (data.get('id'),))
        row = cur.fetchone()
        if row and not row['notlar']:
            notlar = 'Müraciətiniz təsdiqləndi.'

    if notlar is not None:
        cur.execute("UPDATE applications SET status = %s, notlar = %s WHERE id = %s",
                    (status, notlar, data.get('id')))
    else:
        cur.execute("UPDATE applications SET status = %s WHERE id = %s",
                    (status, data.get('id')))

    log_admin(cur, 'Müraciət statusu dəyişildi', 'Müraciət', data.get('id'),
              f"Yeni status: {status}")
    return ok()


# ---------------------------------------------------------------------------
# Contents (Announcements & Surveys)
# ---------------------------------------------------------------------------

def _save_content(cur, content_type):
    data = request.get_json() or {}
    label = 'Elan' if content_type == 'announcement' else 'Anket'
    if data.get('id'):
        cur.execute("""
            UPDATE contents SET title=%s, description=%s, priority=%s, status=%s
            WHERE id=%s
        """, [data['title'], data['description'], data['priority'], data['status'], data['id']])
        log_admin(cur, f'{label} yeniləndi', label, data['id'], data.get('title'))
    else:
        cur.execute("""
            INSERT INTO contents (type, title, description, priority, status)
            VALUES (%s, %s, %s, %s, %s)
        """, [content_type, data['title'], data['description'], data['priority'], data['status']])
        log_admin(cur, f'{label} yaradıldı', label, cur.lastrowid, data.get('title'))
    return ok()


def _get_contents_paged(cur, content_type):
    page, per_page = get_pagination_params()
    where, params = ["type=%s"], [content_type]

    v = qarg('title')
    if v:
        where.append("(title LIKE %s OR description LIKE %s)")
        params.extend([f"%{v}%", f"%{v}%"])
    v = qarg('status')
    if v: where.append("status = %s"); params.append(v)

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"SELECT COUNT(*) as c FROM contents {where_clause}", params)
    total = cur.fetchone()['c']
    cur.execute(f"""
        SELECT id, title, description, priority, status FROM contents
        {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/get_announcements', methods=['GET'])
@admin_required
@with_db
def get_announcements(cur):
    return _get_contents_paged(cur, 'announcement')


@app.route('/api/admin/save_announcement', methods=['POST'])
@admin_required
@with_db
def save_announcement(cur):
    return _save_content(cur, 'announcement')


# Silmə: həm tək, həm cəm URL
@app.route('/api/admin/delete_announcement', methods=['POST'])
@app.route('/api/admin/delete_announcements', methods=['POST'])
@admin_required
@with_db
def delete_announcement(cur):
    data = request.get_json() or {}
    cur.execute("SELECT title FROM contents WHERE id = %s", (data.get('id'),))
    row = cur.fetchone()
    cur.execute("DELETE FROM contents WHERE id = %s", [data.get('id')])
    log_admin(cur, 'Elan silindi', 'Elan', data.get('id'), row['title'] if row else '')
    return ok()


@app.route('/api/admin/get_surveys', methods=['GET'])
@admin_required
@with_db
def get_surveys(cur):
    return _get_contents_paged(cur, 'survey')


@app.route('/api/admin/save_survey', methods=['POST'])
@admin_required
@with_db
def save_survey(cur):
    return _save_content(cur, 'survey')


# Silmə: həm tək, həm cəm URL
@app.route('/api/admin/delete_survey', methods=['POST'])
@app.route('/api/admin/delete_surveys', methods=['POST'])
@admin_required
@with_db
def delete_survey(cur):
    data = request.get_json() or {}
    cur.execute("SELECT title FROM contents WHERE id = %s", (data.get('id'),))
    row = cur.fetchone()
    cur.execute("DELETE FROM contents WHERE id = %s", [data.get('id')])
    log_admin(cur, 'Anket silindi', 'Anket', data.get('id'), row['title'] if row else '')
    return ok()


# ---------------------------------------------------------------------------
# Penalties
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_penalties', methods=['GET'])
@admin_required
@with_db
def get_penalties(cur):
    page, per_page = get_pagination_params()
    where, params = ["1=1"], []

    v = qarg('ad_soyad')
    if v: where.append("s.ad_soyad LIKE %s"); params.append(f"%{v}%")
    v = qarg('reason')
    if v: where.append("p.reason LIKE %s"); params.append(f"%{v}%")
    v = qarg('amount')
    if v: where.append("CAST(p.amount AS CHAR) LIKE %s"); params.append(f"%{v}%")
    v = qarg('status')
    if v: where.append("p.status = %s"); params.append(v)

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT COUNT(*) as c FROM penalties p
        JOIN students s ON p.student_id = s.id {where_clause}
    """, params)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT p.id, p.student_id, p.amount, p.reason, p.status,
               DATE_FORMAT(p.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad
        FROM penalties p
        JOIN students s ON p.student_id = s.id
        {where_clause}
        ORDER BY p.created_at DESC LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/save_penalty', methods=['POST'])
@admin_required
@with_db
def save_penalty(cur):
    data = request.get_json() or {}
    if not data.get('amount') or float(data['amount']) <= 0:
        return fail("Məbləğ düzgün deyil", 400)
    if data.get('id'):
        fields = ["amount=%s", "reason=%s"]
        vals = [data['amount'], data['reason']]
        if data.get('status'):
            fields.append("status=%s")
            vals.append(data['status'])
        vals.append(data['id'])
        cur.execute(f"UPDATE penalties SET {', '.join(fields)} WHERE id=%s", vals)
        log_admin(cur, 'Cərimə yeniləndi', 'Cərimə', data['id'],
                  f"{data.get('amount')} AZN — {data.get('reason')}")
    else:
        cur.execute("""
            INSERT INTO penalties (student_id, amount, reason)
            VALUES (%s, %s, %s)
        """, [data['student_id'], data['amount'], data['reason']])
        log_admin(cur, 'Cərimə yaradıldı', 'Cərimə', cur.lastrowid,
                  f"{data.get('amount')} AZN — {data.get('reason')}")
    return ok()


@app.route('/api/admin/pay_penalty', methods=['POST'])
@admin_required
@with_db
def pay_penalty(cur):
    data = request.get_json() or {}
    cur.execute("UPDATE penalties SET status = 'Ödənilib' WHERE id = %s", [data.get('id')])
    log_admin(cur, 'Cərimə ödənildi', 'Cərimə', data.get('id'), '')
    return ok()


# Silmə: həm tək, həm cəm URL — 404 DÜZƏLDİLDİ
@app.route('/api/admin/delete_penalty', methods=['POST'])
@app.route('/api/admin/delete_penalties', methods=['POST'])
@admin_required
@with_db
def delete_penalty(cur):
    data = request.get_json() or {}
    cur.execute("DELETE FROM penalties WHERE id = %s", [data.get('id')])
    log_admin(cur, 'Cərimə silindi', 'Cərimə', data.get('id'), '')
    return ok()


# ---------------------------------------------------------------------------
# Canteen
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_canteen', methods=['GET'])
@admin_required
@with_db
def get_canteen(cur):
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
    data = request.get_json() or {}
    cur.execute("UPDATE canteen_menu SET meal_name = %s WHERE id = %s",
                [data.get('meal_name'), data.get('id')])
    log_admin(cur, 'Menyu yeniləndi', 'Yeməkxana', data.get('id'),
              f"Yeni: {data.get('meal_name')}")
    return ok()


# ---------------------------------------------------------------------------
# Laundry
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_laundry', methods=['GET'])
@admin_required
@with_db
def get_laundry(cur):
    page, per_page = get_pagination_params()
    where, params = ["1=1"], []

    v = qarg('ad_soyad')
    if v: where.append("s.ad_soyad LIKE %s"); params.append(f"%{v}%")
    for m in ('m1', 'm2', 'm3'):
        v = qarg(m)
        if v: where.append(f"l.machine_{m[1]}_status = %s"); params.append(v)

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT COUNT(*) as c FROM laundry l
        JOIN students s ON l.student_id = s.id {where_clause}
    """, params)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT l.student_id, l.machine_1_status, l.machine_2_status, l.machine_3_status, s.ad_soyad
        FROM laundry l
        JOIN students s ON l.student_id = s.id
        {where_clause}
        ORDER BY s.ad_soyad ASC LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/save_laundry', methods=['POST'])
@admin_required
@with_db
def save_laundry(cur):
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
    log_admin(cur, 'Çamaşırxana yeniləndi', 'Çamaşırxana', data['student_id'],
              f"M1: {data.get('m1')}, M2: {data.get('m2')}, M3: {data.get('m3')}")
    return ok()


# Silmə: həm tək, həm cəm URL
@app.route('/api/admin/delete_laundry', methods=['POST'])
@app.route('/api/admin/delete_laundries', methods=['POST'])
@admin_required
@with_db
def delete_laundry(cur):
    data = request.get_json() or {}
    cur.execute("DELETE FROM laundry WHERE student_id = %s", [data.get('student_id')])
    log_admin(cur, 'Çamaşırxana qeydi silindi', 'Çamaşırxana', data.get('student_id'), '')
    return ok()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_profiles', methods=['GET'])
@admin_required
@with_db
def get_profiles(cur):
    page, per_page = get_pagination_params()
    where, params = ["1=1"], []

    for col in ('ad_soyad', 'yuxu_rejimi', 'temizlik', 'sosial_munasibet', 'hayat_terzi'):
        v = qarg(col)
        if v:
            target = 's.ad_soyad' if col == 'ad_soyad' else f'sp.{col}'
            where.append(f"{target} LIKE %s")
            params.append(f"%{v}%")

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT COUNT(*) as c FROM students_profiles sp
        JOIN students s ON sp.student_id = s.id {where_clause}
    """, params)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT sp.student_id, sp.yuxu_rejimi, sp.temizlik, sp.sosial_munasibet, sp.hayat_terzi, s.ad_soyad
        FROM students_profiles sp
        JOIN students s ON sp.student_id = s.id
        {where_clause}
        ORDER BY s.ad_soyad ASC LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/save_profile', methods=['POST'])
@admin_required
@with_db
def save_profile(cur):
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
    log_admin(cur, 'Profil yeniləndi', 'Profil', data['student_id'], '')
    return ok()


# Silmə: həm tək, həm cəm URL
@app.route('/api/admin/delete_profile', methods=['POST'])
@app.route('/api/admin/delete_profiles', methods=['POST'])
@admin_required
@with_db
def delete_profile(cur):
    data = request.get_json() or {}
    cur.execute("DELETE FROM students_profiles WHERE student_id = %s", [data.get('student_id')])
    log_admin(cur, 'Profil silindi', 'Profil', data.get('student_id'), '')
    return ok()


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_groups', methods=['GET'])
@admin_required
@with_db
def get_groups(cur):
    cur.execute("""
        DELETE FROM student_groups
        WHERE id NOT IN (
            SELECT gid FROM (SELECT DISTINCT group_id AS gid FROM students WHERE group_id IS NOT NULL) x
        )
    """)

    cur.execute("""
        SELECT g.id AS group_id, s.id AS student_id, s.ad_soyad, s.ixtisas, s.kurs, s.cins, s.ev
        FROM student_groups g
        JOIN students s ON s.group_id = g.id
        ORDER BY g.id, s.ad_soyad
    """)
    rows = cur.fetchall()

    groups = {}
    for r in rows:
        gid = r['group_id']
        if gid not in groups:
            groups[gid] = {"id": gid, "members": []}
        groups[gid]["members"].append({
            "id": r["student_id"], "ad_soyad": r["ad_soyad"],
            "ixtisas": r["ixtisas"], "cins": r["cins"], "ev": r["ev"]
        })

    return ok(data=list(groups.values()))


@app.route('/api/admin/delete_group', methods=['POST'])
@app.route('/api/admin/delete_groups', methods=['POST'])
@admin_required
@with_db
def delete_group(cur):
    data = request.get_json() or {}
    gid = data.get('id')
    cur.execute("UPDATE students SET group_id = NULL WHERE group_id = %s", (gid,))
    cur.execute("DELETE FROM student_groups WHERE id = %s", (gid,))
    log_admin(cur, 'Qrup ləğv edildi', 'Qrup', gid, '')
    return ok()


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_requests', methods=['GET'])
@admin_required
@with_db
def get_requests(cur):
    page, per_page = get_pagination_params()
    offset = (page - 1) * per_page

    cur.execute("SELECT COUNT(*) as c FROM home_requests")
    total = cur.fetchone()['c']

    cur.execute("""
        SELECT hr.id, hr.type, hr.room_id, hr.target_id, hr.requester_id, hr.status,
               DATE_FORMAT(hr.created_at, '%%d.%%m.%%Y %%H:%%i') AS tarix,
               t.ad_soyad AS target_name, r.ad_soyad AS requester_name,
               (SELECT COUNT(*) FROM home_request_votes v WHERE v.request_id = hr.id) AS vote_count
        FROM home_requests hr
        JOIN students t ON t.id = hr.target_id
        JOIN students r ON r.id = hr.requester_id
        ORDER BY hr.created_at DESC LIMIT %s OFFSET %s
    """, [per_page, offset])
    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


@app.route('/api/admin/resolve_request', methods=['POST'])
@admin_required
@with_db
def resolve_request(cur):
    data = request.get_json() or {}
    req_id = data.get('id')
    approve = bool(data.get('approve'))

    cur.execute("SELECT * FROM home_requests WHERE id = %s", (req_id,))
    req = cur.fetchone()
    if not req:
        return fail("Tələb tapılmadı!")
    if req['status'] != 'Gözləmədə':
        return fail("Bu tələb artıq həll olunub!")

    if approve:
        if req['type'] == 'invite':
            cur.execute("SELECT cins, ev FROM students WHERE id = %s", (req['target_id'],))
            st = cur.fetchone()
            if not st:
                return fail("Tələbə tapılmadı!")
            if st['ev'] != 'Ev seçilməyib':
                return fail("Tələbənin artıq evi var!")

            cur.execute("SELECT cins FROM rooms WHERE id = %s", (req['room_id'],))
            room = cur.fetchone()
            if room and room['cins'] and room['cins'] != st['cins']:
                return fail("Cins uyğunsuzluğu — bu ev qarşı cinsə aiddir!")

            cur.execute("""
                INSERT IGNORE INTO room_slots (room_id, slot)
                SELECT %s, s.slot FROM (SELECT 1 AS slot UNION SELECT 2 UNION SELECT 3
                                        UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) s
            """, (req['room_id'],))

            cur.execute(
                "SELECT slot FROM room_slots WHERE room_id = %s AND student_id IS NULL ORDER BY slot ASC LIMIT 1",
                (req['room_id'],)
            )
            slot_row = cur.fetchone()
            if not slot_row:
                return fail("Evdə boş yer yoxdur!")

            cur.execute(
                "UPDATE room_slots SET student_id = %s WHERE room_id = %s AND slot = %s",
                (req['target_id'], req['room_id'], slot_row['slot'])
            )
            cur.execute(
                "UPDATE students SET ev = 'Ev seçilib', group_id = NULL WHERE id = %s",
                (req['target_id'],)
            )
        else:
            remove_student_from_room(cur, req['target_id'])
            cur.execute(
                "UPDATE students SET ev = 'Ev seçilməyib', group_id = NULL WHERE id = %s",
                (req['target_id'],)
            )
        cur.execute("UPDATE home_requests SET status = 'Təsdiqləndi' WHERE id = %s", (req_id,))
        log_admin(cur, 'Tələb admin tərəfindən təsdiq edildi', 'Tələb', req_id,
                  f"Tip: {req['type']}, otaq: {req['room_id']}, hədəf ID: {req['target_id']}")
    else:
        cur.execute("UPDATE home_requests SET status = 'Rədd edildi' WHERE id = %s", (req_id,))
        log_admin(cur, 'Tələb admin tərəfindən rədd edildi', 'Tələb', req_id,
                  f"Tip: {req['type']}, otaq: {req['room_id']}")

    return ok()


@app.route('/api/admin/delete_request', methods=['POST'])
@app.route('/api/admin/delete_requests', methods=['POST'])
@admin_required
@with_db
def delete_request(cur):
    data = request.get_json() or {}
    cur.execute("DELETE FROM home_request_votes WHERE request_id = %s", (data.get('id'),))
    cur.execute("DELETE FROM home_requests WHERE id = %s", (data.get('id'),))
    log_admin(cur, 'Tələb silindi', 'Tələb', data.get('id'), '')
    return ok()


# ---------------------------------------------------------------------------
# Logs (son 1 ay)
# ---------------------------------------------------------------------------

@app.route('/api/admin/get_logs', methods=['GET'])
@admin_required
@with_db
def get_logs(cur):
    page, per_page = get_pagination_params()
    where = ["l.created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)"]
    params = []

    v = qarg('tarix')
    if v:
        where.append("DATE_FORMAT(l.created_at, '%%d.%%m.%%Y %%H:%%i') LIKE %s")
        params.append(f"%{v}%")
    v = qarg('admin')
    if v: where.append("l.admin_user LIKE %s"); params.append(f"%{v}%")
    v = qarg('action')
    if v: where.append("l.action LIKE %s"); params.append(f"%{v}%")
    v = qarg('entity')
    if v: where.append("l.entity LIKE %s"); params.append(f"%{v}%")
    v = qarg('entity_id')
    if v: where.append("CAST(l.entity_id AS CHAR) LIKE %s"); params.append(f"%{v}%")
    v = qarg('details')
    if v: where.append("l.details LIKE %s"); params.append(f"%{v}%")

    where_clause = "WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    cur.execute(f"SELECT COUNT(*) as c FROM admin_logs l {where_clause}", params)
    total = cur.fetchone()['c']

    cur.execute(f"""
        SELECT l.id, l.admin_user, l.action, l.entity, l.entity_id, l.details,
               DATE_FORMAT(l.created_at, '%%d.%%m.%%Y %%H:%%i') AS tarix
        FROM admin_logs l
        {where_clause}
        ORDER BY l.created_at DESC LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return ok(data=cur.fetchall(), total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

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
