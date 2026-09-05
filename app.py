import os
import secrets
import logging
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
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

log = logging.getLogger('admin')
logging.basicConfig(level=logging.INFO)


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
    return (request.args.get(name) or '').strip()


def as_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def get_pagination_params():
    page = as_int(request.args.get('page'), 1) or 1
    per_page = as_int(request.args.get('per_page'), 20) or 20
    return max(page, 1), min(per_page, 20)


def room_cins_by_id(room_id):
    rid = as_int(room_id)
    if rid is None:
        return None
    if 101 <= rid <= 120:
        return 'Kişi'
    if 121 <= rid <= 140:
        return 'Qadın'
    return None


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


def remove_student_from_room(cur, student_id):
    cur.execute("UPDATE room_slots SET student_id = NULL WHERE student_id = %s", (student_id,))
    sync_ev_statuses(cur)


def dissolve_group_if_empty(cur, group_id):
    if group_id is None:
        return
    cur.execute("SELECT COUNT(*) AS c FROM students WHERE group_id = %s", (group_id,))
    if cur.fetchone()['c'] == 0:
        cur.execute("DELETE FROM student_groups WHERE id = %s", (group_id,))


def log_admin(cur, action, entity='', entity_id='', details=''):
    try:
        cur.execute(
            "INSERT INTO admin_logs (admin_user, action, entity, entity_id, details) "
            "VALUES (%s, %s, %s, %s, %s)",
            (session.get('admin_user', 'admin'), action, entity, str(entity_id or ''), details or '')
        )
    except Exception as e:
        log.warning("log_admin yazıla bilmədi: %s", e)


def heal_room_slots(cur):
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


def heal_one_room_slots(cur, room_id):
    cur.execute("""
        INSERT IGNORE INTO room_slots (room_id, slot)
        SELECT %s, s.slot
        FROM (SELECT 1 AS slot UNION SELECT 2 UNION SELECT 3
              UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) s
    """, (room_id,))


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
            if 'Duplicate entry' in err_msg and 'uq_slot_student' in err_msg:
                return fail("Bu tələbə artıq bir evdə yaşayır!", 400)
            return fail(f"Məlumat uyğunsuzluğu: {e}", 400)
        except Exception as e:
            conn.rollback()
            log.exception("Əməliyyat xətası")
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


@app.route('/api/admin/check', methods=['GET'])
@admin_required
def admin_check():
    """Yüngül sessiya yoxlaması — DB-yə toxunmur.
    Frontend yalnız 200 cavabında paneli açır (500/502 halında login görünür)."""
    return ok()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
@with_db
def admin_stats(cur):
    # QEYD: "groups" rezerv söz olduğundan backtick içində
    cur.execute("""
        SELECT
          (SELECT COUNT(*) FROM students) AS students,
          (SELECT COUNT(*) FROM rooms) AS rooms,
          (SELECT COUNT(*) FROM applications WHERE status='Gözləmədə') AS apps,
          (SELECT COUNT(*) FROM penalties WHERE status='Ödənilməmiş') AS penalties,
          (SELECT COUNT(DISTINCT group_id) FROM students WHERE group_id IS NOT NULL) AS `groups`,
          (SELECT COUNT(*) FROM home_requests WHERE status='Gözləmədə') AS requests
    """)
    stats = dict(cur.fetchone() or {})
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
    cur.execute("SELECT id, ad_soyad, cins FROM students ORDER BY ad_soyad ASC LIMIT 5000")
    return ok(data=cur.fetchall())


@app.route('/api/admin/get_student_full', methods=['POST'])
@admin_required
@with_db
def get_student_full(cur):
    data = request.get_json() or {}
    sid = as_int(data.get('id'))
    if sid is None:
        return fail("ID düzgün deyil", 400)
    cur.execute("""
        SELECT s.id, s.ad_soyad, s.email, s.ixtisas, s.kurs, s.api_key, s.universitet,
               s.ev_deyisme_isteyi, s.cins, s.ev, rs.room_id AS otaq
        FROM students s
        LEFT JOIN room_slots rs ON rs.student_id = s.id
        WHERE s.id = %s
    """, (sid,))
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

    student_id = as_int(data.get('id'))

    if student_id is not None:
        cur.execute("""
            SELECT r.cins FROM room_slots rs JOIN rooms r ON r.id = rs.room_id
            WHERE rs.student_id = %s
        """, (student_id,))
        room_row = cur.fetchone()
        if room_row and room_row['cins'] and room_row['cins'] != cins:
            return fail("Tələbə hazırda əks cinsə aid evdə yaşayır — əvvəlcə Otaqlar bölməsindən çıxarın!", 400)

        if not data.get('ad_soyad') or not data.get('email'):
            return fail("Ad və email mütləqdir!", 400)

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
        if not data.get('ad_soyad') or not data.get('email'):
            return fail("Ad və email mütləqdir!", 400)

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
        cur.execute("UPDATE room_slots SET student_id = NULL WHERE student_id = %s", (student_id,))
        sync_ev_statuses(cur)

    return ok()


@app.route('/api/admin/delete_student', methods=['POST'])
@app.route('/api/admin/delete_students', methods=['POST'])
@admin_required
@with_db
def delete_student(cur):
    data = request.get_json() or {}
    student_id = as_int(data.get('id'))
    if student_id is None:
        return fail("ID düzgün deyil", 400)

    cur.execute("SELECT ad_soyad, group_id FROM students WHERE id = %s", (student_id,))
    row = cur.fetchone()
    if not row:
        return fail("Tələbə tapılmadı", 404)
    name = row['ad_soyad']
    gid = row['group_id']

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
    sync_ev_statuses(cur)

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
    page, per_page
