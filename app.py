import os
from flask import Flask, request, jsonify, session, render_template_string
from functools import wraps
from config import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "kampus-secret-key-2026")
app.config['JSON_AS_ASCII'] = False

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({"success": False, "message": "İcazə yoxdur!"}), 403
        return f(*args, **kwargs)
    return decorated

def serve_html(filename, **context):
    """Read and serve HTML file. If Jinja2 variables exist, render them."""
    filepath = os.path.join(BASE_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if context:
            return render_template_string(content, **context)
        return content
    except FileNotFoundError:
        return jsonify({"success": False, "message": f"{filename} tapılmadı"}), 404

# ===== PUBLIC PAGE ROUTES =====

@app.route('/')
def index():
    """Student panel"""
    return serve_html('index.html',
        user_name="Tələbə",
        user_ixtisas="",
        user_kurs="",
        user_otaq="",
        is_logged_in=False,
        name_first="Tələbə",
        user_initials="T",
        name_short="Tələbə",
        current_year=2026
    )

@app.route('/admin')
def admin_panel():
    """Admin panel"""
    return serve_html('admin_panel.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '')
    sifre = data.get('sifre', '')

    if email == '123' and sifre == '123':
        session['admin_logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Admin məlumatları yanlışdır!"})

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({"success": True, "redirect": "/admin"})

# ===== ADMIN API ROUTES =====

@app.route('/api/admin/<action>', methods=['GET', 'POST'])
@admin_required
def admin_api(action):
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn[0]

    try:
        data = request.get_json() if request.method == 'POST' else {}

        if action == 'stats':
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

        elif action == 'get_students':
            with conn.cursor() as cur:
                cur.execute("SELECT id, ad_soyad, email, ixtisas, kurs, api_key FROM students ORDER BY id ASC")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_student':
            with conn.cursor() as cur:
                if data.get('id'):
                    cur.execute("UPDATE students SET ad_soyad=%s, email=%s, ixtisas=%s, kurs=%s WHERE id=%s",
                               [data['ad_soyad'], data['email'], data['ixtisas'], data['kurs'], data['id']])
                else:
                    cur.execute("INSERT INTO students (ad_soyad, email, sifre, ixtisas, kurs) VALUES (%s, %s, '12345', %s, %s)",
                               [data['ad_soyad'], data['email'], data['ixtisas'], data['kurs']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'delete_student':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM students WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_rooms':
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM rooms ORDER BY id ASC")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_room':
            with conn.cursor() as cur:
                if data.get('id'):
                    cur.execute("""UPDATE rooms SET telebe_1_id=%s, yataq_1_status=%s, skaf_1_status=%s, oturacaq_1_status=%s,
                                  telebe_2_id=%s, yataq_2_status=%s, skaf_2_status=%s, oturacaq_2_status=%s WHERE id=%s""",
                               [data['t1'], data['y1'], data['s1'], data['o1'], data['t2'], data['y2'], data['s2'], data['o2'], data['id']])
                else:
                    cur.execute("""INSERT INTO rooms (id, telebe_1_id, yataq_1_status, skaf_1_status, oturacaq_1_status,
                                  telebe_2_id, yataq_2_status, skaf_2_status, oturacaq_2_status) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                               [data['id'], data['t1'], data['y1'], data['s1'], data['o1'], data['t2'], data['y2'], data['s2'], data['o2']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'delete_room':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rooms WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_applications':
            with conn.cursor() as cur:
                cur.execute("""SELECT a.id, a.basliq, a.muraciet, a.priority, a.status, 
                              DATE_FORMAT(a.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad 
                              FROM applications a JOIN students s ON a.student_id = s.id 
                              ORDER BY a.created_at DESC""")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'update_app_status':
            with conn.cursor() as cur:
                cur.execute("UPDATE applications SET status = %s WHERE id = %s", [data['status'], data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_announcements':
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, description, priority, status FROM contents WHERE type='announcement' ORDER BY created_at DESC")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_announcement':
            with conn.cursor() as cur:
                if data.get('id'):
                    cur.execute("UPDATE contents SET title=%s, description=%s, priority=%s, status=%s WHERE id=%s",
                               [data['title'], data['description'], data['priority'], data['status'], data['id']])
                else:
                    cur.execute("INSERT INTO contents (type, title, description, priority, status) VALUES ('announcement', %s, %s, %s, %s)",
                               [data['title'], data['description'], data['priority'], data['status']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'delete_announcement':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM contents WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_surveys':
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, description, priority, status FROM contents WHERE type='survey' ORDER BY created_at DESC")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_survey':
            with conn.cursor() as cur:
                if data.get('id'):
                    cur.execute("UPDATE contents SET title=%s, description=%s, priority=%s, status=%s WHERE id=%s",
                               [data['title'], data['description'], data['priority'], data['status'], data['id']])
                else:
                    cur.execute("INSERT INTO contents (type, title, description, priority, status) VALUES ('survey', %s, %s, %s, %s)",
                               [data['title'], data['description'], data['priority'], data['status']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'delete_survey':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM contents WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_penalties':
            with conn.cursor() as cur:
                cur.execute("""SELECT p.id, p.amount, p.reason, p.status, DATE_FORMAT(p.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad 
                              FROM penalties p JOIN students s ON p.student_id = s.id ORDER BY p.created_at DESC""")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_penalty':
            with conn.cursor() as cur:
                if data.get('id'):
                    cur.execute("UPDATE penalties SET amount=%s, reason=%s WHERE id=%s",
                               [data['amount'], data['reason'], data['id']])
                else:
                    cur.execute("INSERT INTO penalties (student_id, amount, reason) VALUES (%s, %s, %s)",
                               [data['student_id'], data['amount'], data['reason']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'pay_penalty':
            with conn.cursor() as cur:
                cur.execute("UPDATE penalties SET status = 'Ödənilib' WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_canteen':
            with conn.cursor() as cur:
                cur.execute("SELECT id, location, day_of_week, meal_name FROM canteen_menu ORDER BY location, day_of_week ASC")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_canteen':
            with conn.cursor() as cur:
                cur.execute("UPDATE canteen_menu SET meal_name = %s WHERE id = %s", [data['meal_name'], data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_laundry':
            with conn.cursor() as cur:
                cur.execute("""SELECT l.student_id, l.machine_1_status, l.machine_2_status, l.machine_3_status, s.ad_soyad 
                              FROM laundry l JOIN students s ON l.student_id = s.id""")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_laundry':
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO laundry (student_id, machine_1_status, machine_2_status, machine_3_status) 
                              VALUES (%s, %s, %s, %s) 
                              ON DUPLICATE KEY UPDATE 
                              machine_1_status=%s, machine_2_status=%s, machine_3_status=%s""",
                           [data['student_id'], data['m1'], data['m2'], data['m3'], data['m1'], data['m2'], data['m3']])
            conn.commit()
            return jsonify({"success": True})

        else:
            return jsonify({"success": False, "message": "Action tapılmadı"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
