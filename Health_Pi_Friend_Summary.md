# 🏥 Health Pi Friend - สรุปโปรเจคสำหรับนำเสนอ

## 📋 วัตถุประสงค์ของโปรเจค

**Health Pi Friend** คือ ระบบผู้ช่วย AI ด้านสุขภาพและโภชนาการ ที่รันบน **Raspberry Pi** โดยมีวัตถุประสงค์:

1. **บันทึกและวิเคราะห์อาหาร** - ผู้ใช้ถ่ายรูปอาหาร → AI วิเคราะห์แคลอรี่/สารอาหาร
2. **ติดตามสุขภาพ** - เชื่อมต่อ Smart Watch ผ่าน BLE → รับข้อมูล HR, Steps แบบ real-time
3. **AI Coaching** - ให้คำแนะนำแบบ personalized ตามข้อมูลผู้ใช้
4. **Dashboard** - แสดงภาพรวมสุขภาพแบบ real-time

---

## 🏗️ สถาปัตยกรรมระบบ

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Smart Watch   │────▶│  Raspberry Pi   │◀────│   Mobile/Web    │
│   (Aolon BLE)   │     │   (Backend)     │     │   (Frontend)    │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ SQLite   │ │ Gemini   │ │ Systemd  │
              │ Database │ │ AI API   │ │ Service  │
              └──────────┘ └──────────┘ └──────────┘
```

---

## 🐧 Linux/OS Commands ที่ใช้ในโปรเจค

### 1. การจัดการ Services (systemd)

| คำสั่ง | หน้าที่ |
|--------|---------|
| `sudo systemctl start nutrifriend` | เริ่มต้น service |
| `sudo systemctl stop nutrifriend` | หยุด service |
| `sudo systemctl restart nutrifriend` | รีสตาร์ท service |
| `sudo systemctl status nutrifriend` | ดูสถานะ service |
| `sudo systemctl enable nutrifriend` | เปิด auto-start ตอน boot |
| `journalctl -u nutrifriend -f` | ดู log แบบ real-time |

**ไฟล์ Service:** `/etc/systemd/system/nutrifriend.service`
```ini
[Unit]
Description=NutriFriend AI Health Assistant
After=network.target bluetooth.target

[Service]
Type=simple
User=os
WorkingDirectory=/home/os/Project-Os3/Project-Os
ExecStart=/bin/bash -c 'source backend/.venv/bin/activate && ./start_pi.sh'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

### 2. Crontab - งานตั้งเวลาอัตโนมัติ

```bash
# เปิด crontab editor
crontab -e

# ดู crontab ปัจจุบัน
crontab -l
```

**งานที่ตั้งไว้:**
```bash
# บันทึกข้อมูลนาฬิกาทุก 1 นาที
* * * * * /home/os/Project-Os3/Project-Os/backend/venv/bin/python3 /home/os/Project-Os3/Project-Os/backend/read_watch.py >> /home/os/health_data.log 2>&1
```

---

### 3. การจัดการ Process

| คำสั่ง | หน้าที่ |
|--------|---------|
| `ps aux \| grep python` | ดู Python process ที่รันอยู่ |
| `kill -9 <PID>` | หยุด process |
| `nohup ./start_pi.sh &` | รัน background (ไม่หยุดเมื่อปิด terminal) |
| `htop` | ดู resource usage แบบ interactive |

---

### 4. การจัดการ Bluetooth (BLE)

| คำสั่ง | หน้าที่ |
|--------|---------|
| `bluetoothctl` | เปิด Bluetooth control |
| `scan on` | เริ่มสแกนอุปกรณ์ |
| `devices` | แสดงอุปกรณ์ที่เจอ |
| `connect <MAC>` | เชื่อมต่ออุปกรณ์ |
| `hciconfig` | ดูสถานะ Bluetooth adapter |

---

### 5. การจัดการ Network

| คำสั่ง | หน้าที่ |
|--------|---------|
| `ip addr` | ดู IP address |
| `curl http://localhost:8000/health` | ทดสอบ API |
| `ss -tulpn` | ดู port ที่เปิดอยู่ |
| `ping <host>` | ทดสอบ network connectivity |

---

### 6. การจัดการ Files และ Logs

| คำสั่ง | หน้าที่ |
|--------|---------|
| `tail -f /home/os/health_data.log` | ดู log แบบ real-time |
| `tail -50 <file>` | ดู 50 บรรทัดล่าสุด |
| `less <file>` | อ่านไฟล์แบบ scroll ได้ |
| `cat <file>` | แสดงเนื้อหาทั้งไฟล์ |
| `grep "ERROR" <file>` | ค้นหาคำใน file |

---

### 7. การจัดการ Database (SQLite)

```bash
# เปิด SQLite shell
sqlite3 /home/os/Project-Os3/Project-Os/nutrifriend.db

# ดู tables
.tables

# ดู schema
.schema user_profiles

# Query
SELECT * FROM user_profiles;

# เพิ่ม column (Migration)
ALTER TABLE user_profiles ADD COLUMN step_goal INTEGER DEFAULT 10000;

# Backup
cp nutrifriend.db nutrifriend_backup_$(date +%Y%m%d).db
```

---

### 8. Python Virtual Environment

```bash
# สร้าง venv
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Deactivate
deactivate
```

---

### 9. Git Version Control

| คำสั่ง | หน้าที่ |
|--------|---------|
| `git pull origin issue-1` | ดึงโค้ดล่าสุด |
| `git status` | ดูสถานะ |
| `git log -5` | ดู 5 commits ล่าสุด |
| `git diff` | ดูการเปลี่ยนแปลง |

---

## 📁 โครงสร้างไฟล์สำคัญ

```
Project-Os/
├── backend/
│   ├── main.py              # FastAPI server หลัก (API endpoints ทั้งหมด)
│   ├── models.py            # SQLAlchemy models (Database schema)
│   ├── schemas.py           # Pydantic schemas (API validation)
│   ├── watch_service.py     # BLE connection กับ Smart Watch
│   ├── health_ai_engine.py  # AI วิเคราะห์สุขภาพ
│   ├── read_watch.py        # Crontab script บันทึกข้อมูลนาฬิกา
│   └── nutrifriend.db       # SQLite Database
│
├── frontend/
│   ├── App.tsx              # Main React component
│   ├── components/
│   │   ├── OverviewDashboard.tsx  # หน้าภาพรวม
│   │   ├── HealthDashboard.tsx    # หน้าสุขภาพ
│   │   ├── ChatAssistant.tsx      # Chat กับ AI
│   │   └── Onboarding.tsx         # หน้าลงทะเบียน
│   └── dist/                # Built production files
│
├── nutrifriend.service      # Systemd service file
├── install_service.sh       # Script ติดตั้ง service
├── start_pi.sh              # Script เริ่มต้น server
└── backup_db.sh             # Script backup database
```

---

## 🔄 ระบบ Log Analytics (API Management)

### การทำงาน:
1. **โดน Rate Limit (429)** → Parse `retryDelay` จาก API
2. **ตั้ง Cooldown** → ห้ามยิง model นี้ตามเวลาที่ API แนะนำ
3. **Fallback** → ลอง model อื่นอัตโนมัติ
4. **บันทึก Log** → เขียนลง `/home/os/api_analytics.log`

### Fallback Chain:
```
gemini-2.0-flash → gemini-3-flash-preview → gemini-2.5-flash-lite → gemini-2.5-flash → gemma-3-27b-it
```

### ดูสถิติ:
```bash
# Log file
tail -f /home/os/api_analytics.log

# API endpoint
curl http://localhost:8000/api/stats
```

---

## 📊 Log Files ทั้งหมด

| ไฟล์ | เนื้อหา | ที่มา |
|------|---------|-------|
| `/home/os/health_data.log` | HR, Steps จากนาฬิกา | Crontab (ทุก 1 นาที) |
| `/home/os/api_analytics.log` | Rate limit, Cooldown events | Auto (เมื่อเกิด event) |
| `journalctl -u nutrifriend` | Server logs | Systemd |

---

## 🚀 คำสั่ง Deploy บน Pi

```bash
# 1. Pull code ล่าสุด
cd /home/os/Project-Os3/Project-Os
git pull origin issue-1

# 2. Backup database (ถ้ามี migration)
cp nutrifriend.db nutrifriend_backup_$(date +%Y%m%d).db

# 3. Run migration (ถ้ามี column ใหม่)
sqlite3 nutrifriend.db "ALTER TABLE user_profiles ADD COLUMN step_goal INTEGER DEFAULT 10000;"

# 4. Restart service
sudo systemctl restart nutrifriend

# 5. ดู log
journalctl -u nutrifriend -f
```

---

## 📌 Features หลักของระบบ

| Feature | คำอธิบาย | ใช้ Linux/OS อะไร |
|---------|----------|-------------------|
| Auto-start on Boot | เริ่มทำงานอัตโนมัติเมื่อเปิด Pi | Systemd |
| BLE Watch Connection | เชื่อมต่อนาฬิกา Smart Watch | Bluetooth, bleak library |
| Periodic Data Save | บันทึกข้อมูลทุก 1 นาที | Crontab |
| AI API Management | จัดการ rate limit อัตโนมัติ | In-memory + File logging |
| Database | เก็บข้อมูลผู้ใช้, อาหาร, สุขภาพ | SQLite |
| Web Server | API และ Frontend | FastAPI + React |
