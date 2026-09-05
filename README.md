# 🛠️ GreenCampus Admin

> [GreenCampus](https://github.com/Abdullayews/greencampus) tələbə portalının administrativ paneli — tələbələr, otaqlar, qruplar, tələblər, ərizələr, elanlar, cərimələr, yeməkxana və camaşırxananı bir yerdən idarə et.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/Database-TiDB%20Cloud-4479A1?logo=mysql&logoColor=white)
![Deploy](https://img.shields.io/badge/Hosted%20on-Render-46E3B7?logo=render&logoColor=white)

---

## ✨ Nə edir?

| | |
|---|---|
| 🔐 **Admin auth** | Sessiya əsaslı giriş, bütün API-lər `admin_required` ilə qorunur |
| 📊 **Dashboard** | 6 göstərici: tələbə, otaq, gözləyən müraciət, ödənilməmiş cərimə, aktiv qrup, gözləyən tələb |
| 🎓 **Tələbələr** | Yarat / yenilə / sil (kaskad) — **cins** + **ev statusu** (3 hal) idarəsi, otaq göstərişi, API açarı |
| 🏘️ **Otaqlar və Əşyalar** | `room_slots` əsaslı: 6 yer × (tələbə + yataq / şkaf / oturacaq statusu) — **bina cinsi avtomatik təyin olunur** (101–120 oğlan binası, 121–140 qız binası), tələbə siyahısı cinsə görə filtrlənir |
| 👥 **Qruplar** | Aktiv qrupların baxışı (üzv siyahısı ilə) + ləğv etmə — boş qruplar avtomatik silinir |
| 📨 **Tələblər** | Dəvət / qovma / çıxma tələblərinin baxışı (səs sayı ilə) + admin müdaxiləsi — məcburi təsdiq (dəvət → evə yerləşdir, qovma → evdən çıxar) və ya rədd |
| 📝 **Ərizələr** | Status idarəsi + **notlar** (tələbəyə görünən admin qeydi — təsdiqdə boşdursa avtomatik default yazılır) |
| 📢 **Elanlar & Anketlər** | Yarat, yenilə, sil |
| 💸 **Cərimələr** | Kəs, ödə, sil |
| 🍽️ **Yeməkxana** | Həftəlik menyu — canlı redaktə (Yataqxana / Universitet) |
| 🧺 **Camaşırxana** | Hər tələbə üzrə 3 maşın statusu |
| 👤 **Tələbə Profilləri** | Yuxu rejimi, təmizlik, sosial münasibət, həyat tərzi |

## 🛠️ Stack

**Backend:** Python · Flask
**Database:** MySQL-uyğun (TiDB Cloud üzərində, SSL bağlantı, `PyMySQL`) — tələbə saytı **`greencampus` ilə paylaşılan sxem**
**Server:** Gunicorn (`Procfile`)
**Deploy:** Render + GitHub

## 📁 Struktur

```
greencampusadmin/
├── app.py               # Flask app + bütün /api/admin/<action> handler-ləri
├── config.py             # DB bağlantısı (PyMySQL, SSL)
├── templates/index.html  # Admin panel (tək səhifə, SPA tipli)
├── requirements.txt
└── Procfile
```

## 🔑 Environment

Bütün dəyərlər env variable-lardan oxunur — kodda credential yoxdur:

| Dəyişən | Təsvir | Default |
|---|---|---|
| `DB_HOST` | MySQL host | — |
| `DB_PORT` | Port | `4000` |
| `DB_NAME` | Baza adı | — |
| `DB_USER` | İstifadəçi | — |
| `DB_PASSWORD` | Şifrə | — |
| `DB_SSL` | SSL bağlantı | `true` |
| `ADMIN_USER` | Admin istifadəçi adı | `admin` |
| `ADMIN_PASS` | Admin şifrə | `123` |
| `SECRET_KEY` | Session açarı (fallback: `secret_key.txt`) | — |

## 🗄️ Verilənlər bazası sxemi

Tələbə saytı ilə **eyni bazanı** oxuyur:

| Cədvəl | Sütunlar |
|---|---|
| `students` | id, ad_soyad, email (unique), sifre, universitet, ixtisas, kurs, ev_deyisme_isteyi, api_key, **cins**, **ev** (3 hal), **group_id** |
| `rooms` | id, capacity, **cins** (Kişi/Qadın) |
| `room_slots` | (room_id, slot) PK, student_id (unique), yataq/skaf/oturacaq_status |
| `student_groups` | id (AUTO), created_at |
| `home_requests` | id, type (invite/kick/leave), room_id, target_id, requester_id, status, created_at |
| `home_request_votes` | (request_id, voter_id) PK, vote (Təsdiq/Rədd) |
| `students_profiles` | student_id (PK), yuxu_rejimi, temizlik, sosial_munasibet, hayat_terzi |
| `applications` | id, student_id, basliq, muraciet, priority, status, **notlar**, created_at |
| `contents` | id, type (announcement/survey), title, description, priority, status, created_at |
| `penalties` | id, student_id, amount, reason, status, created_at |
| `canteen_menu` | id, location, day_of_week, meal_name |
| `laundry` | student_id (PK), machine_1-3_status |

## 🌐 API marşrutları

| Method | Route | |
|---|---|---|
| GET | `/` , `/admin` | Admin panel səhifəsi |
| POST | `/login` | Admin girişi |
| GET | `/logout` | Admin çıxışı |
| GET | `/api/admin/stats` | Dashboard statistikası (6 göstərici) |
| GET/POST | `/api/admin/get_students` | Tələbə siyahısı (paginasiyalı) |
| POST | `/api/admin/get_student_full` | Tələbə tam məlumat |
| POST | `/api/admin/save_student` | Tələbə yarat / yenilə (cins + ev statusu) |
| POST | `/api/admin/delete_student` | Tələbə sil (kaskad) |
| GET/POST | `/api/admin/get_rooms` | Otaq siyahısı + slotlar (self-heal) |
| POST | `/api/admin/save_room` | Otaq yarat / yenilə (room_slots) |
| POST | `/api/admin/delete_room` | Otaq sil (sakinlər çıxarılır) |
| GET/POST | `/api/admin/get_groups` | Qrup siyahısı |
| POST | `/api/admin/delete_group` | Qrup ləğv et |
| GET/POST | `/api/admin/get_requests` | Tələb siyahısı (səs sayı ilə) |
| POST | `/api/admin/resolve_request` | Tələbi məcburi təsdiq / rədd et |
| POST | `/api/admin/delete_request` | Tələb sil |
| GET/POST | `/api/admin/get_applications` | Ərizə siyahısı (notlar ilə) |
| POST | `/api/admin/save_application` | Ərizə yarat / yenilə |
| POST | `/api/admin/update_app_status` | Ərizə statusunu yenilə |
| POST | `/api/admin/delete_application` | Ərizə sil |
| GET/POST | `/api/admin/get_announcements` | Elan siyahısı |
| POST | `/api/admin/save_announcement` | Elan yarat / yenilə |
| POST | `/api/admin/delete_announcement` | Elan sil |
| GET/POST | `/api/admin/get_surveys` | Anket siyahısı |
| POST | `/api/admin/save_survey` | Anket yarat / yenilə |
| POST | `/api/admin/delete_survey` | Anket sil |
| GET/POST | `/api/admin/get_penalties` | Cərimə siyahısı |
| POST | `/api/admin/save_penalty` | Cərimə yarat / yenilə |
| POST | `/api/admin/pay_penalty` | Cəriməni ödənilmiş et |
| POST | `/api/admin/delete_penalty` | Cərimə sil |
| GET/POST | `/api/admin/get_canteen` | Yeməkxana menyusu |
| POST | `/api/admin/save_canteen` | Menyu yenilə |
| GET/POST | `/api/admin/get_laundry` | Camaşırxana siyahısı |
| POST | `/api/admin/save_laundry` | Camaşırxana yarat / yenilə |
| POST | `/api/admin/delete_laundry` | Camaşırxana qeydi sil |
| GET/POST | `/api/admin/get_profiles` | Profil siyahısı |
| POST | `/api/admin/save_profile` | Profil yarat / yenilə |
| POST | `/api/admin/delete_profile` | Profil sil |

Bütün `/api/admin/*` marşrutları aktiv admin sessiyası tələb edir; girişsiz sorğulara `403` və `{"success": false, "message": "İcazə yoxdur!"}` qaytarılır.

## 🏢 Bina qaydası

| Bina | Evlər | Cins |
|---|---|---|
| Oğlan binası | 101–120 | Kişi |
| Qız binası | 121–140 | Qadın |

Yeni otaq yaradılarkən nömrə aralığına görə cins **avtomatik təyin olunur və kilidlənir** — cins uyğun gəlməyən tələbəni otağa yerləşdirmək mümkün deyil.

## 🔗 Bağlı repo

Tələbə tərəfi: **[greencampus →](https://github.com/Abdullayews/greencampus)**
