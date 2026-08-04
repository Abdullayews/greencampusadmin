import os
from flask import Flask, request, jsonify, session, render_template_string
from functools import wraps
from config import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

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
    return serve_html('index.html',
        user_name="Tələbə", user_ixtisas="", user_kurs="", user_otaq="",
        is_logged_in=False, name_first="Tələbə", user_initials="T",
        name_short="Tələbə", current_year=2026
    )

@app.route('/admin')
def admin_panel():
    return serve_html('admin_panel.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '')
    sifre = data.get('sifre', '')
    if email == 'admin' and sifre == '123':
        session['admin_logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Admin məlumatları yanlışdır!"})

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({"success": True, "redirect": "/admin"})

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

        elif action == 'get_student_full':
            with conn.cursor() as cur:
                cur.execute("SELECT id, ad_soyad, email, sifre, ixtisas, kurs, api_key FROM students WHERE id=%s", [data.get('id')])
                student = cur.fetchone()
                return jsonify({"success": True, "data": student})

        elif action == 'save_student':
            with conn.cursor() as cur:
                if data.get('id'):
                    fields = ["ad_soyad=%s", "email=%s", "ixtisas=%s", "kurs=%s"]
                    vals = [data['ad_soyad'], data['email'], data['ixtisas'], data['kurs']]
                    if data.get('sifre'):
                        fields.append("sifre=%s")
                        vals.append(data['sifre'])
                    if data.get('api_key') is not None:
                        fields.append("api_key=%s")
                        vals.append(data['api_key'])
                    vals.append(data['id'])
                    cur.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=%s", vals)
                else:
                    cur.execute("INSERT INTO students (ad_soyad, email, sifre, ixtisas, kurs, api_key) VALUES (%s, %s, %s, %s, %s, %s)",
                               [data['ad_soyad'], data['email'], data.get('sifre','12345'), data['ixtisas'], data['kurs'], data.get('api_key')])
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
            # Boş string telebe ID-lerini None cevir
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

        elif action == 'delete_room':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rooms WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_applications':
            with conn.cursor() as cur:
                cur.execute("""SELECT a.id, a.student_id, a.basliq, a.muraciet, a.priority, a.status,
                              DATE_FORMAT(a.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad
                              FROM applications a JOIN students s ON a.student_id = s.id
                              ORDER BY a.created_at DESC""")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_application':
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

        elif action == 'delete_application':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM applications WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

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
                cur.execute("""SELECT p.id, p.student_id, p.amount, p.reason, p.status, DATE_FORMAT(p.created_at, '%%d.%%m.%%Y') as tarix, s.ad_soyad
                              FROM penalties p JOIN students s ON p.student_id = s.id ORDER BY p.created_at DESC""")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_penalty':
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

        elif action == 'pay_penalty':
            with conn.cursor() as cur:
                cur.execute("UPDATE penalties SET status = 'Ödənilib' WHERE id = %s", [data['id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'delete_penalty':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM penalties WHERE id = %s", [data['id']])
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

        elif action == 'delete_laundry':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM laundry WHERE student_id = %s", [data['student_id']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'get_profiles':
            with conn.cursor() as cur:
                cur.execute("""SELECT sp.student_id, sp.yuxu_rejimi, sp.temizlik, sp.sosial_munasibet, sp.hayat_terzi, s.ad_soyad
                              FROM students_profiles sp JOIN students s ON sp.student_id = s.id""")
                return jsonify({"success": True, "data": cur.fetchall()})

        elif action == 'save_profile':
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO students_profiles (student_id, yuxu_rejimi, temizlik, sosial_munasibet, hayat_terzi)
                              VALUES (%s, %s, %s, %s, %s)
                              ON DUPLICATE KEY UPDATE
                              yuxu_rejimi=%s, temizlik=%s, sosial_munasibet=%s, hayat_terzi=%s""",
                           [data['student_id'], data['yuxu_rejimi'], data['temizlik'], data['sosial_munasibet'], data['hayat_terzi'],
                            data['yuxu_rejimi'], data['temizlik'], data['sosial_munasibet'], data['hayat_terzi']])
            conn.commit()
            return jsonify({"success": True})

        elif action == 'delete_profile':
            with conn.cursor() as cur:
                cur.execute("DELETE FROM students_profiles WHERE student_id = %s", [data['student_id']])
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
