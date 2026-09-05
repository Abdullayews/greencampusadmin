<div align="center">

# 🛠️ GreenCampus Admin

**The control room of the GreenCampus student portal.**

*Students · rooms & inventory · groups · requests · applications · announcements · penalties · canteen · laundry — all from one panel.*

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Database](https://img.shields.io/badge/DB-TiDB_Cloud-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://tidbcloud.com)
[![Server](https://img.shields.io/badge/WSGI-Gunicorn-499848?style=for-the-badge&logo=gunicorn&logoColor=white)](https://gunicorn.org)
[![Deploy](https://img.shields.io/badge/Hosted_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com)

[Student portal → greencampus](https://github.com/Abdullayews/greencampus)

</div>

---

## 🧭 What is this?

**GreenCampus Admin** is the administrative panel of the
[GreenCampus](https://github.com/Abdullayews/greencampus) student portal.
It talks to the **exact same database** as the student site and gives the
administration full control over it: manage students and their home status,
edit rooms down to individual bed / locker / chair slots, dissolve groups,
force-resolve roommate requests, review applications with private notes,
publish announcements and surveys, issue and settle penalties, edit the
weekly canteen menu, flip laundry machine states — and watch everything
through a live dashboard.

Every API endpoint is protected by an `admin_required` session guard, and
every destructive action is explicit: single-record delete, bulk delete,
or force-resolve with a written log.

## ✨ Features

| | |
|---|---|
| 🔐 **Admin auth** | Session-based login — every API is guarded by `admin_required` |
| 📊 **Dashboard** | 6 live KPIs: students, rooms, pending applications, unpaid penalties, active groups, pending requests |
| 🎓 **Students** | Create / update / delete (cascade) — gender + home status (3 states), room assignment, API key management, bulk delete |
| 🏘️ **Rooms & inventory** | Built on `room_slots`: 6 slots × (student + bed / locker / chair status) — **building gender is derived automatically** (101–120 boys, 121–140 girls), student lists filtered accordingly, self-healing slots |
| 👥 **Groups** | View active groups with member lists, create / dissolve, add or remove members — single or bulk |
| 📨 **Requests** | Invite / kick / leave requests with live vote counts + **admin force-resolve** (invite → place into home, kick → remove from home) or reject |
| 📝 **Applications** | Status management + **notes** — the private admin remark visible to the student (auto-defaulted on approval if left empty) |
| 📢 **Announcements & surveys** | Full CRUD, single or bulk |
| 💸 **Penalties** | Issue, mark paid, delete — single or bulk |
| 🍽️ **Canteen** | Weekly menu, live editing (Dormitory / University locations) |
| 🧺 **Laundry** | Per-student status of 3 machines |
| 👤 **Student profiles** | Sleep schedule, cleanliness, sociability, lifestyle |
| 📜 **Logs** | Action log viewer + old-log cleanup |
| 📤 **CSV export** | One-click export for every entity |

## 🛠️ Tech stack

| Layer | Technology |
|---|---|
| Backend | Python · **Flask** |
| Database | MySQL-compatible **TiDB Cloud** (SSL, `PyMySQL`) — **shared schema with the student site `greencampus`** |
| Server | **Gunicorn** (`Procfile`) |
| Deploy | **Render** + GitHub |

## 📁 Repository structure

```
greencampusadmin/
├── app.py               # Flask app + all /api/admin/<action> handlers (~1.9k lines)
├── config.py            # DB connection (PyMySQL, SSL)
├── templates/
│   └── index.html       # Admin panel — one page, SPA-style
├── requirements.txt
└── Procfile             # gunicorn entrypoint for Render
```

## 🔑 Environment variables

Everything is read from the environment — **no credentials in code**:

| Variable | Description | Default |
|---|---|---|
| `DB_HOST` | MySQL / TiDB host | — |
| `DB_PORT` | Port | `4000` |
| `DB_NAME` | Database name | — |
| `DB_USER` | Database user | — |
| `DB_PASSWORD` | Database password | — |
| `DB_SSL` | SSL connection | `true` |
| `ADMIN_USER` | Admin username | `admin` |
| `ADMIN_PASS` | Admin password | `123` |
| `SECRET_KEY` | Session key (fallback: `secret_key.txt`) | — |

## 🌐 API routes — all 63

**Session & utilities**

| Method | Route | Purpose |
|---|---|---|
| GET | `/`, `/admin` | Admin panel page |
| POST | `/login` | Admin sign-in |
| GET | `/logout` | Admin sign-out |
| GET | `/api/admin/check` | Session check |
| GET | `/api/admin/stats` | Dashboard — 6 KPIs |
| GET | `/api/admin/search_students_query` | Search query helper |
| GET | `/api/admin/export/<entity>` | CSV export |
| GET | `/api/admin/get_logs` | Action logs |
| POST | `/api/admin/clear_old_logs` | Log cleanup |

**Students**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/admin/get_students` | Student list (paginated) |
| POST | `/api/admin/get_student_full` | Full student record |
| POST | `/api/admin/save_student` | Create / update (gender + home status) |
| POST | `/api/admin/delete_student` | Delete (cascade) |
| POST | `/api/admin/delete_students` | Bulk delete |

**Rooms & inventory**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/admin/get_rooms` | Rooms + slots (self-healing) |
| POST | `/api/admin/save_room` | Create / update room (`room_slots`) |
| POST | `/api/admin/delete_room` | Delete room (residents released) |
| POST | `/api/admin/delete_rooms` | Bulk delete |

**Groups**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/admin/get_groups` | Group list |
| POST | `/api/admin/create_group` · `create_groups` | Create — single / bulk |
| POST | `/api/admin/add_group_member` · `add_group_members` | Add member(s) |
| POST | `/api/admin/remove_group_member` · `remove_group_members` | Remove member(s) |
| POST | `/api/admin/delete_group` · `delete_groups` | Dissolve — single / bulk |

**Requests (invite / kick / leave)**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/admin/get_requests` | Request list with vote counts |
| GET | `/api/admin/get_request_votes` | Votes for one request |
| POST | `/api/admin/create_request` · `create_requests` | Create — single / bulk |
| POST | `/api/admin/resolve_request` | **Force-resolve or reject** |
| POST | `/api/admin/delete_request` · `delete_requests` | Delete — single / bulk |

**Applications · announcements · surveys**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/admin/get_applications` | List (with notes) |
| POST | `/api/admin/save_application` | Create / update |
| POST | `/api/admin/update_app_status` | Change status |
| POST | `/api/admin/delete_application` · `delete_applications` | Delete — single / bulk |
| GET | `/api/admin/get_announcements` | Announcement list |
| POST | `/api/admin/save_announcement` | Create / update |
| POST | `/api/admin/delete_announcement` · `delete_announcements` | Delete — single / bulk |
| GET | `/api/admin/get_surveys` | Survey list |
| POST | `/api/admin/save_survey` | Create / update |
| POST | `/api/admin/delete_survey` · `delete_surveys` | Delete — single / bulk |

**Penalties · canteen · laundry · profiles**

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/admin/get_penalties` | Penalty list |
| POST | `/api/admin/save_penalty` | Issue a penalty |
| POST | `/api/admin/pay_penalty` | Mark as paid |
| POST | `/api/admin/delete_penalty` · `delete_penalties` | Delete — single / bulk |
| GET | `/api/admin/get_canteen` | Weekly menu |
| POST | `/api/admin/save_canteen` | Live menu editing |
| GET | `/api/admin/get_laundry` | Laundry status |
| POST | `/api/admin/save_laundry` | Update machine status |
| POST | `/api/admin/delete_laundry` · `delete_laundries` | Delete — single / bulk |
| GET | `/api/admin/get_profiles` | Lifestyle profiles |
| POST | `/api/admin/save_profile` | Update a profile |
| POST | `/api/admin/delete_profile` · `delete_profiles` | Delete — single / bulk |

## 🚀 Installation

```bash
git clone https://github.com/Abdullayews/greencampusadmin.git
cd greencampusadmin

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DB_HOST="..." DB_NAME="..." DB_USER="..." DB_PASSWORD="..."
export ADMIN_USER="admin" ADMIN_PASS="change-me"
export SECRET_KEY="$(openssl rand -hex 32)"

python app.py          # dev server
# or: gunicorn app:app  # production
```

> 💡 The panel expects the **same database** as
> [greencampus](https://github.com/Abdullayews/greencampus) — deploy them
> as a pair.

## 📄 License

Personal / educational project — the management half of a real campus system.


## 👤 Author

**Muhəmməd Abdullayev** — Computer Engineering student · Qarabağ University & Holberton School

<p>
<a href="https://github.com/Abdullayews"><img src="https://img.shields.io/badge/GitHub-@Abdullayews-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="https://t.me/arasss08"><img src="https://img.shields.io/badge/Telegram-@arasss08-26A5E4?style=flat-square&logo=telegram&logoColor=white" alt="Telegram"></a>
<a href="mailto:08abdullayevv@gmail.com"><img src="https://img.shields.io/badge/Email-08abdullayevv@gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>
</p>

> 🇦🇿 Bu layihə Azərbaycan tələbə həyatı üçün hazırlanıb — *GreenCampus — kampus həyatı bir panelə yığılır.*
