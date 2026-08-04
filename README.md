# 🛠️ GreenCampus Admin

> [GreenCampus](https://github.com/Abdullayews/greencampus) tələbə portalının administrativ paneli — bir yerdən tələbələr, otaqlar, ərizələr, elanlar, cərimələr, yeməkxana və camaşırxananı idarə et.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/Database-TiDB%20Cloud-4479A1?logo=mysql&logoColor=white)
![Deploy](https://img.shields.io/badge/Hosted%20on-Render-46E3B7?logo=render&logoColor=white)

---

## ✨ Nə edir?

| | |
|---|---|
| 🔐 **Admin auth** | Sessiya əsaslı giriş, bütün API-lər `admin_required` ilə qorunur |
| 📊 **Dashboard** | Tələbə / gözləyən ərizə / ödənilməmiş cərimə / otaq sayı |
| 🎓 **Tələbələr** | Yarat, yenilə, sil |
| 🏘️ **Otaqlar** | Çarpayı/şkaf/oturacaq statusunu idarə et |
| 📝 **Ərizələr** | Baxış + status yeniləmə |
| 📢 **Elanlar & sorğular** | Yarat, yenilə, sil |
| 💸 **Cərimələr** | Kəs, ödənilmiş kimi işarələ |
| 🍽️ **Yeməkxana** | Günlük menyunu yenilə |
| 🧺 **Camaşırxana** | Maşın statuslarını izlə |

## 🛠️ Stack

**Backend:** Python · Flask
**Database:** MySQL-uyğun (TiDB Cloud üzərində, SSL bağlantı, `PyMySQL`, `greencampus` ilə paylaşılan sxem)
**Server:** Gunicorn (`Procfile`)
**Deploy:** Render + GitHub

## 📁 Struktur

```
greencampusadmin/
├── app.py              # Flask app, route-lar, bütün /api/admin/<action> handler-ləri
├── config.py            # DB bağlantısı (PyMySQL, SSL)
├── templates/            # index.html (tələbə görünüşü) & admin_panel.html
├── requirements.txt
└── Procfile
```

## 🔑 Environment

| Dəyişən | Təsvir |
|---|---|
| `DB_HOST` | MySQL host |
| `DB_PORT` | Port (default `4000`, TiDB Cloud) |
| `DB_NAME` | Baza adı |
| `DB_USER` | İstifadəçi |
| `DB_PASSWORD` | Şifrə |

Bağlantı default olaraq SSL üzərindən qurulur.

## 🗄️ Verilənlər bazası sxemi

Faktiki MySQL dump-a (`if0_42430459_students`, MyISAM, `utf8mb4_unicode_ci`) əsaslanır:

- **`students`** — `id`, `ad_soyad`, `email` (unique), `sifre`, `universitet`, `ixtisas`, `kurs`, `ev_deyisme_isteyi`, `api_key`
- **`students_profiles`** — `student_id`, `yuxu_rejimi`, `temizlik`, `sosial_munasibet`, `hayat_terzi` (otaq yoldaşı uyğunlaşdırması üçün)
- **`rooms`** — `id` + `telebe_N_id`, `yataq_N_status`, `skaf_N_status`, `oturacaq_N_status` (`N` = 1–6, cədvəl 6 tələbəyə qədər dəstəkləyir)
- **`applications`** — `id`, `student_id`, `basliq`, `muraciet`, `priority`, `status` (default `Gözləmədə`), `created_at`
- **`contents`** — `id`, `type` (`announcement`/`survey`), `title`, `description`, `priority`, `status`, `created_at`
- **`penalties`** — `id`, `student_id`, `amount`, `reason`, `status` (`Ödənilməmiş`/`Ödənilib`), `created_at`
- **`canteen_menu`** — `id`, `location`, `day_of_week`, `meal_name`
- **`laundry`** — `student_id`, `machine_1_status`, `machine_2_status`, `machine_3_status`

## 🌐 API marşrutları

| Method | Route | |
|---|---|---|
| GET | `/` | Tələbə görünüşü |
| GET | `/admin` | Admin panel görünüşü |
| POST | `/login` | Admin girişi |
| GET | `/logout` | Admin çıxışı |
| GET/POST | `/api/admin/stats` | Dashboard rəqəmləri |
| GET/POST | `/api/admin/get_students` | Tələbə siyahısı |
| GET/POST | `/api/admin/save_student` | Tələbə yarat/yenilə |
| GET/POST | `/api/admin/delete_student` | Tələbə sil |
| GET/POST | `/api/admin/get_rooms` | Otaq siyahısı |
| GET/POST | `/api/admin/save_room` | Otaq yarat/yenilə |
| GET/POST | `/api/admin/delete_room` | Otaq sil |
| GET/POST | `/api/admin/get_applications` | Ərizə siyahısı |
| GET/POST | `/api/admin/update_app_status` | Ərizə statusunu yenilə |
| GET/POST | `/api/admin/get_announcements` | Elan siyahısı |
| GET/POST | `/api/admin/save_announcement` | Elan yarat/yenilə |
| GET/POST | `/api/admin/delete_announcement` | Elan sil |
| GET/POST | `/api/admin/get_surveys` | Sorğu siyahısı |
| GET/POST | `/api/admin/save_survey` | Sorğu yarat/yenilə |
| GET/POST | `/api/admin/delete_survey` | Sorğu sil |
| GET/POST | `/api/admin/get_penalties` | Cərimə siyahısı |
| GET/POST | `/api/admin/save_penalty` | Cərimə yarat/yenilə |
| GET/POST | `/api/admin/pay_penalty` | Cəriməni ödənilmiş et |
| GET/POST | `/api/admin/get_canteen` | Yeməkxana menyusu |
| GET/POST | `/api/admin/save_canteen` | Menyunu yenilə |
| GET/POST | `/api/admin/get_laundry` | Camaşırxana statusu |
| GET/POST | `/api/admin/save_laundry` | Camaşırxana statusunu yenilə |

Bütün `/api/admin/*` marşrutları aktiv admin sessiyası tələb edir; girişsiz sorğulara `403` və `{"success": false, "message": "İcazə yoxdur!"}` qaytarılır.

## 🔗 Bağlı repo

Tələbə tərəfi: **[greencampus →](https://github.com/Abdullayews/greencampus)**
