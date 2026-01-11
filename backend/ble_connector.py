"""
Aolon Smartwatch BLE Connector

ใช้ bleak library สำหรับเชื่อมต่อ BLE กับนาฬิกา Aolon
รับข้อมูล: Heart Rate, Steps, SpO2, etc.

Note: GATT UUIDs อาจต้อง reverse-engineer สำหรับ Aolon แต่ละรุ่น
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
import time
import random

# Try to import bleak, fallback to mock mode if not available
try:
    from bleak import BleakScanner, BleakClient
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    logging.warning("bleak not installed - running in mock mode")

# Standard BLE UUIDs
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# Battery Service
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Generic Access
DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"


@dataclass
class BLEDevice:
    """Represents a discovered BLE device"""
    address: str
    name: Optional[str]
    rssi: int


@dataclass
class SensorData:
    """Raw sensor data from watch"""
    timestamp: int
    heart_rate: int
    steps: int
    spo2: Optional[int] = None
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 9.8
    battery_level: Optional[int] = None


class AolonWatchConnector:
    """
    BLE Connector for Aolon Smartwatch
    
    Handles:
    - Device scanning and discovery
    - Connection management
    - Heart rate subscription
    - Sensor data reading
    """
    
    def __init__(self, device_address: str = None, mock_mode: bool = False):
        self.device_address = device_address
        self.client: Optional[Any] = None
        self.connected = False
        self.mock_mode = mock_mode or not BLEAK_AVAILABLE
        self._callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        self._last_hr = 70
        self._step_count = 0
        
        if self.mock_mode:
            logging.info("🔧 BLE Connector running in MOCK mode")
    
    async def scan_devices(self, timeout: float = 10.0) -> tuple:
        """
        สแกนหา BLE devices รอบๆ
        Returns: (all_devices, aolon_devices)
        """
        if self.mock_mode:
            # Return mock devices for testing
            mock_devices = [
                BLEDevice("AA:BB:CC:DD:EE:FF", "Aolon Watch", -60),
                BLEDevice("11:22:33:44:55:66", "Mi Band 7", -75),
            ]
            aolon = [d for d in mock_devices if "aolon" in (d.name or "").lower()]
            return mock_devices, aolon
        
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
        all_devices = []
        for d, adv in devices.values():
            all_devices.append(BLEDevice(d.address, d.name, adv.rssi if adv else -100))
        aolon_devices = [
            d for d in all_devices 
            if d.name and "aolon" in d.name.lower()
        ]
        
        logging.info(f"Found {len(all_devices)} devices, {len(aolon_devices)} Aolon devices")
        return all_devices, aolon_devices
    
    async def connect(self, address: str = None) -> bool:
        """เชื่อมต่อกับนาฬิกา"""
        addr = address or self.device_address
        if not addr:
            raise ValueError("Device address required")
        
        if self.mock_mode:
            self.connected = True
            self.device_address = addr
            logging.info(f"✅ [MOCK] Connected to {addr}")
            return True
        
        try:
            self.client = BleakClient(addr)
            await self.client.connect()
            self.connected = self.client.is_connected
            self.device_address = addr
            logging.info(f"✅ Connected to {addr}")
            return self.connected
        except Exception as e:
            logging.error(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """ตัดการเชื่อมต่อ"""
        if self.mock_mode:
            self.connected = False
            logging.info("🔌 [MOCK] Disconnected")
            return
        
        if self.client and self.connected:
            await self.client.disconnect()
            self.connected = False
            logging.info("🔌 Disconnected")
    
    async def get_device_info(self) -> Dict:
        """อ่านข้อมูลอุปกรณ์"""
        if self.mock_mode:
            return {
                "name": "Aolon Watch (Mock)",
                "address": self.device_address,
                "battery": 85
            }
        
        if not self.connected:
            raise ConnectionError("Not connected")
        
        info = {}
        try:
            # Read device name
            name_data = await self.client.read_gatt_char(DEVICE_NAME_UUID)
            info["name"] = name_data.decode("utf-8")
            
            # Read battery level
            battery_data = await self.client.read_gatt_char(BATTERY_LEVEL_UUID)
            info["battery"] = battery_data[0]
            
            info["address"] = self.device_address
        except Exception as e:
            logging.warning(f"Could not read device info: {e}")
        
        return info
    
    async def subscribe_heart_rate(self, callback: Callable[[int], None]) -> None:
        """
        Subscribe รับ heart rate แบบ real-time
        callback จะถูกเรียกทุกครั้งที่มี HR ใหม่
        """
        if not self.connected:
            raise ConnectionError("Not connected")
        
        if self.mock_mode:
            # Store callback for mock data generation
            if "heart_rate" not in self._callbacks:
                self._callbacks["heart_rate"] = []
            self._callbacks["heart_rate"].append(callback)
            logging.info("📡 [MOCK] Subscribed to heart rate")
            return
        
        def notification_handler(sender, data):
            # Parse heart rate from BLE data (standard format)
            flags = data[0]
            if flags & 0x01:  # 16-bit HR
                hr = int.from_bytes(data[1:3], byteorder='little')
            else:  # 8-bit HR
                hr = data[1]
            callback(hr)
        
        await self.client.start_notify(
            HEART_RATE_MEASUREMENT_UUID,
            notification_handler
        )
        logging.info("📡 Subscribed to heart rate")
    
    async def unsubscribe_heart_rate(self) -> None:
        """หยุด subscribe heart rate"""
        if self.mock_mode:
            self._callbacks.pop("heart_rate", None)
            return
        
        if self.connected and self.client:
            await self.client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
    
    async def get_raw_sensor_data(self) -> SensorData:
        """
        ดึงข้อมูล sensor ทั้งหมด
        ใช้ polling mode (ไม่ใช่ notification)
        """
        timestamp = int(time.time())
        
        if self.mock_mode:
            # Generate realistic mock data
            self._last_hr = self._simulate_heart_rate()
            self._step_count += random.randint(0, 15)
            
            return SensorData(
                timestamp=timestamp,
                heart_rate=self._last_hr,
                steps=self._step_count,
                spo2=random.randint(95, 99),
                accel_x=random.uniform(-0.5, 0.5),
                accel_y=random.uniform(-0.5, 0.5),
                accel_z=random.uniform(9.5, 10.1),
                battery_level=random.randint(70, 100)
            )
        
        if not self.connected:
            raise ConnectionError("Not connected")
        
        # Read from actual device
        # Note: Actual UUIDs depend on Aolon's GATT profile
        sensor_data = SensorData(timestamp=timestamp, heart_rate=0, steps=0)
        
        try:
            hr_data = await self.client.read_gatt_char(HEART_RATE_MEASUREMENT_UUID)
            sensor_data.heart_rate = hr_data[1] if len(hr_data) > 1 else hr_data[0]
        except Exception as e:
            logging.warning(f"Could not read HR: {e}")
        
        return sensor_data
    
    def _simulate_heart_rate(self) -> int:
        """Generate realistic HR pattern for mock mode"""
        # Add some variation
        delta = random.randint(-3, 3)
        new_hr = self._last_hr + delta
        
        # Keep within realistic bounds
        new_hr = max(55, min(180, new_hr))
        
        # Occasionally simulate activity bursts
        if random.random() < 0.05:
            new_hr += random.randint(10, 30)
        
        return new_hr
    
    async def start_continuous_monitoring(
        self, 
        callback: Callable[[SensorData], None],
        interval: float = 1.0
    ) -> None:
        """
        เริ่มการ monitor แบบต่อเนื่อง
        callback จะถูกเรียกทุก interval วินาที
        """
        self._running = True
        logging.info(f"🏃 Starting continuous monitoring (interval={interval}s)")
        
        while self._running:
            try:
                data = await self.get_raw_sensor_data()
                await asyncio.to_thread(callback, data)
                await asyncio.sleep(interval)
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                await asyncio.sleep(interval * 2)
    
    def stop_monitoring(self) -> None:
        """หยุดการ monitor"""
        self._running = False
        logging.info("🛑 Monitoring stopped")
    
    @property
    def is_connected(self) -> bool:
        return self.connected


# Convenience function for quick setup
async def create_watch_connection(address: str = None, mock: bool = False) -> AolonWatchConnector:
    """
    สร้างและเชื่อมต่อกับนาฬิกา
    
    Usage:
        watch = await create_watch_connection("AA:BB:CC:DD:EE:FF")
        data = await watch.get_raw_sensor_data()
    """
    connector = AolonWatchConnector(device_address=address, mock_mode=mock)
    
    if address:
        await connector.connect(address)
    
    return connector


# Test function
async def test_ble_connector():
    """ทดสอบ BLE connector ใน mock mode"""
    print("🧪 Testing BLE Connector in Mock Mode...\n")
    
    connector = AolonWatchConnector(mock_mode=True)
    
    # Scan
    all_devices, aolon_devices = await connector.scan_devices()
    print(f"Found {len(all_devices)} devices")
    for d in aolon_devices:
        print(f"  - Aolon: {d.name} ({d.address})")
    
    # Connect
    await connector.connect("AA:BB:CC:DD:EE:FF")
    
    # Get info
    info = await connector.get_device_info()
    print(f"\nDevice Info: {info}")
    
    # Read sensor data
    print("\nReading sensor data (5 samples):")
    for i in range(5):
        data = await connector.get_raw_sensor_data()
        print(f"  [{i+1}] HR: {data.heart_rate} bpm, Steps: {data.steps}, SpO2: {data.spo2}%")
        await asyncio.sleep(0.5)
    
    # Disconnect
    await connector.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_ble_connector())
