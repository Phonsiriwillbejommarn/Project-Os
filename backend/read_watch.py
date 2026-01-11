#!/usr/bin/env python3
"""
Crontab Watch Reader - อ่านข้อมูลจาก Aolon Watch ทุก 1 นาที

ใช้กับ crontab:
* * * * * /usr/bin/python3 /home/os/Project-Os3/Project-Os/backend/read_watch.py

Script นี้จะ:
1. Connect to Aolon watch
2. Read: Steps, Battery, HR (ถ้ามี)
3. POST ไป API /watch/data
4. Disconnect
"""

import asyncio
import sys
import time
import os

# Force UTF-8 encoding for stdout/stderr
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

# Set environment variable for encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

import requests
from bleak import BleakScanner, BleakClient

# Aolon Watch Address (เปลี่ยนตาม address ของคุณ)
AOLON_ADDRESS = "E2:AD:F6:7A:56:55"

# API Endpoint
API_URL = "http://localhost:8000/watch/data"

# GATT UUIDs
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
VENDOR_STEPS_UUID = "0000fee1-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


def parse_steps(data: bytes) -> int:
    """Parse steps from vendor data"""
    if len(data) >= 2:
        return int.from_bytes(data[0:2], byteorder='little')
    return 0


def parse_hr(data: bytes) -> int:
    """Parse HR from BLE data"""
    if len(data) < 2:
        return 0
    flags = data[0]
    if flags & 0x01:
        return int.from_bytes(data[1:3], byteorder='little')
    return data[1]


async def read_watch_data():
    """Connect to watch and read all data"""
    print(f"[{time.strftime('%H:%M:%S')}] 🔍 Connecting to {AOLON_ADDRESS}...")
    
    data = {
        "hr": 0,
        "steps": 0,
        "battery": 0,
        "timestamp": int(time.time()),
        "connected": False
    }
    
    try:
        async with BleakClient(AOLON_ADDRESS, timeout=15) as client:
            if not client.is_connected:
                print("❌ Failed to connect")
                return data
            
            print("✅ Connected!")
            data["connected"] = True
            
            # Read Battery
            try:
                bat_data = await client.read_gatt_char(BATTERY_UUID)
                data["battery"] = bat_data[0]
                print(f"🔋 Battery: {data['battery']}%")
            except Exception as e:
                print(f"Battery read failed: {e}")
            
            # Read Steps
            try:
                steps_data = await client.read_gatt_char(VENDOR_STEPS_UUID)
                data["steps"] = parse_steps(steps_data)
                print(f"👟 Steps: {data['steps']}")
            except Exception as e:
                print(f"Steps read failed: {e}")
            
            # Try to read HR (may not work without notification)
            try:
                hr_data = await client.read_gatt_char(HR_MEASUREMENT_UUID)
                data["hr"] = parse_hr(hr_data)
                print(f"💓 HR: {data['hr']} BPM")
            except Exception as e:
                print(f"HR read failed (normal if not in HR mode): {e}")
            
            print("🔌 Disconnecting...")
    
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    return data


def send_to_api(data: dict):
    """Send data to API endpoint"""
    try:
        response = requests.post(API_URL, json=data, timeout=5)
        if response.ok:
            print(f"📤 Data sent to API successfully")
        else:
            print(f"⚠️ API response: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to send to API: {e}")


async def main():
    print("=" * 50)
    print(f"📡 Crontab Watch Reader - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Read data from watch
    data = await read_watch_data()
    
    # Send to API
    if data["connected"]:
        send_to_api(data)
    
    print(f"\n📊 Final Data: HR={data['hr']} Steps={data['steps']} Battery={data['battery']}%")
    print("=" * 50)
    
    return 0 if data["connected"] else 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
