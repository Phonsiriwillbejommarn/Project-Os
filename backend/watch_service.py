"""
Real Aolon Watch Service - Background BLE Connection

เชื่อมต่อ Aolon Curve และส่ง data แบบ real-time
รองรับ: Heart Rate, Battery, Steps (vendor)
"""

import asyncio
import logging
import time
from typing import Callable, Optional, Dict, Any
from bleak import BleakScanner, BleakClient

# Aolon Curve Address (Pi format)
AOLON_ADDRESS = "E2:AD:F6:7A:56:55"

# Standard GATT UUIDs
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Vendor service (contains Steps)
VENDOR_STEPS_UUID = "0000fee1-0000-1000-8000-00805f9b34fb"


class AolonRealTimeService:
    """
    Real-time service for Aolon Curve watch
    Connects via BLE and streams health data
    """
    
    def __init__(self, address: str = None):
        self.address = address or AOLON_ADDRESS
        self.client: Optional[BleakClient] = None
        self.connected = False
        
        # Current data
        self.current_hr = 0
        self.battery = 0
        self.steps = 0
        self.last_update = 0
        
        # Callbacks
        self.on_data_callbacks = []
        
        # Background polling task
        self._polling_task = None
        self._polling = False
        
        logging.basicConfig(level=logging.INFO)
    
    def add_callback(self, callback: Callable[[Dict], Any]):
        """Add callback for data updates"""
        self.on_data_callbacks.append(callback)
    
    def _parse_hr(self, data: bytes) -> int:
        """Parse HR from BLE notification"""
        flags = data[0]
        if flags & 0x01:
            return int.from_bytes(data[1:3], byteorder='little')
        return data[1]
    
    def _parse_steps(self, data: bytes) -> int:
        """Parse steps from vendor data (fee1)"""
        if len(data) >= 2:
            # First 2 bytes seem to be steps (little-endian)
            return int.from_bytes(data[0:2], byteorder='little')
        return 0
    
    def _hr_notification_handler(self, sender, data):
        """Handle HR notifications"""
        self.current_hr = self._parse_hr(data)
        self.last_update = time.time()
        print(f"💓 HR: {self.current_hr} BPM")
        self._notify_callbacks()
    
    def _notify_callbacks(self):
        """Call all registered callbacks with current data"""
        data = self.get_current_data()
        for cb in self.on_data_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(data))
                else:
                    cb(data)
            except Exception as e:
                logging.error(f"Callback error: {e}")
    
    def get_current_data(self) -> Dict:
        """Get current health data"""
        return {
            "hr": self.current_hr,
            "steps": self.steps,
            "battery": self.battery,
            "connected": self.connected,
            "timestamp": int(time.time()),
            "last_update": self.last_update
        }
    
    async def find_watch(self) -> Optional[str]:
        """Scan and find Aolon watch"""
        print("🔍 Scanning for Aolon watch...")
        try:
            devices = await BleakScanner.discover(timeout=5, return_adv=True)
            for d, adv in devices.values():
                if d.name and "aolon" in d.name.lower():
                    print(f"✅ Found: {d.name} ({d.address})")
                    return d.address
        except Exception as e:
            print(f"Scan error: {e}")
        return None
    
    async def connect(self) -> bool:
        """Connect to Aolon watch"""
        # Use stored address or default
        addr = self.address
        
        # Only scan if we absolutely don't have an address
        if not addr:
            found = await self.find_watch()
            if found:
                addr = found
                self.address = found
        
        if not addr:
            print("❌ Watch not found (no address)")
            return False
        
        print(f"🔗 Connecting to {addr}...")
        
        try:
            self.client = BleakClient(addr, timeout=15)
            await self.client.connect()
            self.connected = self.client.is_connected
            
            if self.connected:
                print("✅ Connected!")
                
                # Read battery
                try:
                    bat_data = await self.client.read_gatt_char(BATTERY_UUID)
                    self.battery = bat_data[0]
                    print(f"🔋 Battery: {self.battery}%")
                except Exception as e:
                    print(f"Battery read failed: {e}")
                
                # Read steps from vendor service
                try:
                    steps_data = await self.client.read_gatt_char(VENDOR_STEPS_UUID)
                    self.steps = self._parse_steps(steps_data)
                    print(f"👟 Steps: {self.steps}")
                except Exception as e:
                    print(f"Steps read failed: {e}")
                
                # Subscribe to HR
                try:
                    await self.client.start_notify(
                        HR_MEASUREMENT_UUID, 
                        self._hr_notification_handler
                    )
                    print("📡 Subscribed to Heart Rate")
                except Exception as e:
                    print(f"HR subscribe failed: {e}")
                
                return True
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
        
        return False
    
    async def disconnect(self):
        """Disconnect from watch"""
        if self.client and self.connected:
            try:
                await self.client.stop_notify(HR_MEASUREMENT_UUID)
            except:
                pass
            try:
                await self.client.disconnect()
            except:
                pass
        self.connected = False
        self.current_hr = 0
        print("🔌 Disconnected")
    
    async def update_steps(self):
        """Manually update steps (read from vendor service)"""
        if self.connected and self.client:
            try:
                steps_data = await self.client.read_gatt_char(VENDOR_STEPS_UUID)
                self.steps = self._parse_steps(steps_data)
            except:
                pass
    
    async def update_battery(self):
        """Update battery level"""
        if self.connected and self.client:
            try:
                bat_data = await self.client.read_gatt_char(BATTERY_UUID)
                self.battery = bat_data[0]
            except:
                pass
    
    async def _auto_connect_loop(self, interval: float = 5.0):
        """Background loop to maintain connection"""
        print(f"🔄 Starting auto-connect service (interval={interval}s)")
        self._polling = True
        
        while self._polling:
            if not self.connected:
                print("🔍 Auto-connecting...")
                success = await self.connect()
                if success:
                    print("✅ Auto-connect successful!")
                else:
                    print("⚠️ Auto-connect failed, retrying...")
                    await asyncio.sleep(10)  # Wait before retry
                    continue
            
            # If connected, poll data
            try:
                # Update steps and battery
                await self.update_steps()
                await self.update_battery()
                
                # Check connection status
                if self.client and not self.client.is_connected:
                    print("⚠️ Connection lost during polling")
                    self.connected = False
                    continue
                
                self.last_update = time.time()
                # print(f"📊 Data: HR={self.current_hr} Steps={self.steps} Battery={self.battery}%")
                self._notify_callbacks()
                
            except Exception as e:
                print(f"Polling error: {e}")
                self.connected = False
            
            await asyncio.sleep(interval)
        
        print("🛑 Auto-connect service stopped")

    def start_auto_connect(self, interval: float = 5.0):
        """Start background auto-connect task"""
        if self._polling_task is None or self._polling_task.done():
            self._polling_task = asyncio.create_task(self._auto_connect_loop(interval))
            print("✅ Auto-connect task started")
    
    def stop_auto_connect(self):
        """Stop background auto-connect task"""
        self._polling = False
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
        print("🛑 Auto-connect task stopped")
    
    async def run_forever(self, reconnect_interval: float = 5.0):
        """Run continuously with auto-reconnect"""
        while True:
            if not self.connected:
                success = await self.connect()
                if not success:
                    print(f"⏳ Retrying in {reconnect_interval}s...")
                    await asyncio.sleep(reconnect_interval)
                    continue
            
            # Update steps periodically
            await self.update_steps()
            
            # Wait and check connection
            await asyncio.sleep(10)
            
            if self.client and not self.client.is_connected:
                print("⚠️ Connection lost")
                self.connected = False


# Global instance for the app
watch_service: Optional[AolonRealTimeService] = None


def get_watch_service() -> AolonRealTimeService:
    """Get or create global watch service instance"""
    global watch_service
    if watch_service is None:
        watch_service = AolonRealTimeService()
    return watch_service


# Test
async def test():
    service = AolonRealTimeService()
    
    def on_data(data):
        print(f"  -> Data: HR={data['hr']} Steps={data['steps']}")
    
    service.add_callback(on_data)
    
    if await service.connect():
        print("\n📡 Running for 30 seconds...")
        print("   (Keep HR screen open on watch)")
        print("-" * 40)
        
        # Update steps every 5 seconds
        for _ in range(6):
            await asyncio.sleep(5)
            await service.update_steps()
            print(f"👟 Steps: {service.steps}")
        
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(test())
