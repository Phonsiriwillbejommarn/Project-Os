#!/home/os/Project-Os3/Project-Os/backend/venv/bin/python3
"""
Crontab Watch Data Saver - บันทึกข้อมูลจาก Main Server ลง Database ทุก 1 นาที

แก้ไขใหม่: ไม่เชื่อมต่อ BLE โดยตรง แต่ดึงข้อมูลจาก /watch/status แทน
เพื่อไม่ให้แย่ง BLE กับ main server
"""

import sys
import os
import time
from datetime import datetime

# Force UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import requests

# Config
API_BASE = "http://localhost:8000"

def log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def main():
    print("=" * 50)
    print(f"📡 Crontab Data Saver - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        # 1. ดึงข้อมูลจาก main server (ที่เชื่อมต่อ BLE อยู่แล้ว)
        log("🔍 Getting data from main server...")
        res = requests.get(f"{API_BASE}/watch/status", timeout=5)
        
        if res.status_code != 200:
            log(f"❌ Server returned {res.status_code}")
            return
        
        data = res.json()
        
        if not data.get("connected"):
            log("⚠️ Watch not connected")
            return
        
        hr = data.get("hr", 0)
        steps = data.get("steps", 0)
        battery = data.get("battery", 0)
        
        log(f"❤️ HR: {hr} BPM")
        log(f"👟 Steps: {steps}")
        log(f"🔋 Battery: {battery}%")
        
        # 2. ส่งไปบันทึกลง database (ผ่าน /watch/data)
        if steps > 0 or hr > 0:
            save_data = {
                "hr": hr,
                "steps": steps,
                "battery": battery,
                "connected": True,
                "timestamp": int(time.time())
            }
            
            save_res = requests.post(f"{API_BASE}/watch/data", json=save_data, timeout=5)
            
            if save_res.status_code == 200:
                log("💾 Data saved to database!")
            else:
                log(f"⚠️ Save failed: {save_res.status_code}")
        else:
            log("⚠️ No valid data to save")
        
    except requests.exceptions.ConnectionError:
        log("❌ Cannot connect to server (is it running?)")
    except Exception as e:
        log(f"❌ Error: {e}")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
