🛠️ GreenCampus Admin

    GreenCampus tələbə portalının administrativ paneli — tələbələr, otaqlar, qruplar, tələblər, ərizələr, elanlar, cərimələr, yeməkxana və camaşırxananı bir yerdən idarə et.

PythonFlaskMySQLDeploy
✨ Nə edir?
	
🔐 Admin auth	Sessiya əsaslı giriş, bütün API-lər admin_required ilə qorunur
📊 Dashboard	Tələbə / otaq / gözləyən müraciət / cərimə / qrup / tələb sayı
🎓 Tələbələr	Yarat, yenilə, sil (kaskad) — cins + ev statusu idarəsi, otaq göstərişi
🚪 Otaqlar	room_slots əsaslı: 6 yer × (tələbə + yataq/şkaf/oturacaq), bina cinsi avtomatik (101–120 oğlan, 121–140 qız)
👥 Qruplar	Baxış + ləğv (boş qruplar avtomatik silinir)
📨 Tələblər	Dəvət / qovma / çıxma tələblərinin baxışı + admin müdaxiləsi (məcburi təsdiq/rədd)
📝 Ərizələr	Status + notlar (təsdiqdə avtomatik default qeyd)
📢 Elanlar & anketlər	Yarat, yenilə, sil
💸 Cərimələr	Kəs, ödə, sil
🍽️ Yeməkxana	Həftəlik menyu (canlı redaktə)
🧺 Camaşırxana	Maşın statusları
👤 Profillər	Xarakteristikaların idarəsi
🛠️ Stack

Backend: Python · FlaskDatabase: MySQL-uyğun (TiDB Cloud, SSL, PyMySQL) — greencampus ilə paylaşılan sxemServer: Gunicorn (Procfile)Deploy: Render + GitHub
📁 Struktur

greencampusadmin/
├── app.py              # Flask app + bütün /api/admin/* handler-ləri
├── config.py            # DB bağlantısı (PyMySQL, SSL)
├── templates/index.html # Admin panel (tək səhifə)
├── requirements.txt
└── Procfile
text
 
  
 
 

## 🔑 Environment

| Dəyişən | Təsvir |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | DB bağlantısı |
| `ADMIN_USER` / `ADMIN_PASS` | Admin girişi (default: `admin` / `123`) |
| `SECRET_KEY` | Session açarı (fallback: `secret_key.txt`) |

## 🗄️ Sxem (tələbə saytı ilə ortaq)

`students` (cins, ev, group_id) · `rooms` (capacity, cins) · `room_slots` · `student_groups` · `home_requests` · `home_request_votes` · `applications` (notlar) · `students_profiles` · `contents` · `penalties` · `canteen_menu` · `laundry`

## 🌐 API marşrutları

| Method | Route | |
|---|---|---|
| GET | `/` , `/admin` | Admin panel |
| POST | `/login` / GET `/logout` | Auth |
| GET/POST | `/api/admin/stats` | Dashboard (6 göstərici) |
| GET/POST | `/api/admin/get_students` · `save_student` · `delete_student` · `get_student_full` | Tələbələr |
| GET/POST | `/api/admin/get_rooms` · `save_room` · `delete_room` | Otaqlar (room_slots) |
| GET/POST | `/api/admin/get_groups` · `delete_group` | Qruplar |
| GET/POST | `/api/admin/get_requests` · `resolve_request` · `delete_request` | Tələblər |
| GET/POST | `/api/admin/get_applications` · `save_application` · `update_app_status` · `delete_application` | Müraciətlər |
| GET/POST | `/api/admin/get_announcements` · `save_announcement` · `delete_announcement` | Elanlar |
| GET/POST | `/api/admin/get_surveys` · `save_survey` · `delete_survey` | Anketlər |
| GET/POST | `/api/admin/get_penalties` · `save_penalty` · `pay_penalty` · `delete_penalty` | Cərimələr |
| GET/POST | `/api/admin/get_canteen` · `save_canteen` | Yeməkxana |
| GET/POST | `/api/admin/get_laundry` · `save_laundry` · `delete_laundry` | Camaşırxana |
| GET/POST | `/api/admin/get_profiles` · `save_profile` · `delete_profile` | Profillər |

## 🔗 Bağlı repo

Tələbə tərəfi: **[greencampus →](https://github.com/Abdullayews/greencampus)**
