"""
MQTT Handler for Health Alerts

ส่ง alerts ผ่าน MQTT ไปยัง external devices
เช่น smart home, emergency contacts, other Pi devices

Topics:
- health/alerts/{type}     : Alert notifications
- health/user/{id}/realtime: Real-time health data
- health/user/{id}/status  : Device status
"""

import json
import logging
import time
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Try to import paho-mqtt, fallback to mock mode
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.warning("paho-mqtt not installed - running in mock mode")


class AlertPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    ANOMALY = "ANOMALY"
    FATIGUE = "FATIGUE"
    RECOMMENDATION = "RECOMMENDATION"
    NUTRITION = "NUTRITION"
    WORKOUT = "WORKOUT"
    SYSTEM = "SYSTEM"


@dataclass
class HealthAlert:
    """Health alert data structure"""
    user_id: int
    alert_type: AlertType
    priority: AlertPriority
    message: str
    message_en: Optional[str] = None
    data: Optional[Dict] = None
    timestamp: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(time.time())
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result["alert_type"] = self.alert_type.value
        result["priority"] = self.priority.value
        return result
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class MQTTHealthHandler:
    """
    MQTT Handler for Pi Health Coach
    
    Publishes:
    - Real-time health data
    - Health alerts (anomaly, fatigue, etc.)
    - Device status updates
    
    Subscribes:
    - Command messages (optional)
    - Configuration updates (optional)
    """
    
    def __init__(
        self, 
        broker: str = "localhost", 
        port: int = 1883,
        client_id: str = "pi_health_coach",
        mock_mode: bool = False
    ):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.mock_mode = mock_mode or not MQTT_AVAILABLE
        self.client: Optional[Any] = None
        self.connected = False
        self._message_callbacks: Dict[str, List[Callable]] = {}
        self._published_messages: List[Dict] = []  # For mock mode
        
        if self.mock_mode:
            logging.info("📡 MQTT Handler running in MOCK mode")
    
    def connect(self, username: str = None, password: str = None) -> bool:
        """เชื่อมต่อ MQTT broker"""
        if self.mock_mode:
            self.connected = True
            logging.info(f"✅ [MOCK] Connected to MQTT broker {self.broker}:{self.port}")
            return True
        
        try:
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            if username and password:
                self.client.username_pw_set(username, password)
            
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            
            # Wait a bit for connection
            time.sleep(0.5)
            return self.connected
            
        except Exception as e:
            logging.error(f"❌ MQTT connect failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """ตัดการเชื่อมต่อ MQTT"""
        if self.mock_mode:
            self.connected = False
            logging.info("🔌 [MOCK] MQTT Disconnected")
            return
        
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logging.info("🔌 MQTT Disconnected")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logging.info(f"✅ MQTT Connected to {self.broker}")
            # Subscribe to command topics
            client.subscribe("health/commands/#")
        else:
            logging.error(f"❌ MQTT Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected"""
        self.connected = False
        logging.warning(f"⚠️ MQTT Disconnected (rc={rc})")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except:
            payload = msg.payload.decode()
        
        logging.debug(f"📨 Received: {topic} -> {payload}")
        
        # Call registered callbacks
        for pattern, callbacks in self._message_callbacks.items():
            if topic.startswith(pattern.replace("#", "")):
                for callback in callbacks:
                    callback(topic, payload)
    
    def publish_alert(self, alert: HealthAlert) -> bool:
        """ส่ง health alert ผ่าน MQTT"""
        topic = f"health/alerts/{alert.alert_type.value.lower()}"
        payload = alert.to_json()
        
        if self.mock_mode:
            self._published_messages.append({
                "topic": topic,
                "payload": alert.to_dict(),
                "timestamp": time.time()
            })
            logging.info(f"📤 [MOCK] Alert: {topic} -> {alert.message}")
            return True
        
        if not self.connected:
            logging.warning("⚠️ MQTT not connected, alert not sent")
            return False
        
        result = self.client.publish(topic, payload, qos=1)
        success = result.rc == mqtt.MQTT_ERR_SUCCESS
        
        if success:
            logging.info(f"📤 Alert sent: {topic}")
        else:
            logging.error(f"❌ Failed to send alert: {result.rc}")
        
        return success
    
    def publish_health_data(self, user_id: int, data: Dict) -> bool:
        """ส่งข้อมูลสุขภาพแบบ real-time"""
        topic = f"health/user/{user_id}/realtime"
        payload = json.dumps(data, ensure_ascii=False)
        
        if self.mock_mode:
            self._published_messages.append({
                "topic": topic,
                "payload": data,
                "timestamp": time.time()
            })
            return True
        
        if not self.connected:
            return False
        
        result = self.client.publish(topic, payload, qos=0)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def publish_status(self, user_id: int, status: str, details: Dict = None) -> bool:
        """ส่งสถานะอุปกรณ์"""
        topic = f"health/user/{user_id}/status"
        payload = json.dumps({
            "status": status,
            "timestamp": int(time.time()),
            "details": details or {}
        }, ensure_ascii=False)
        
        if self.mock_mode:
            logging.info(f"📊 [MOCK] Status: {user_id} -> {status}")
            return True
        
        if not self.connected:
            return False
        
        result = self.client.publish(topic, payload, qos=1, retain=True)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def subscribe(self, topic_pattern: str, callback: Callable[[str, Any], None]) -> None:
        """Subscribe to a topic pattern"""
        if topic_pattern not in self._message_callbacks:
            self._message_callbacks[topic_pattern] = []
        self._message_callbacks[topic_pattern].append(callback)
        
        if not self.mock_mode and self.connected:
            self.client.subscribe(topic_pattern)
    
    def get_published_messages(self) -> List[Dict]:
        """[MOCK] ดึง messages ที่ถูก publish (สำหรับ testing)"""
        return self._published_messages.copy()
    
    def clear_published_messages(self) -> None:
        """[MOCK] เคลียร์ messages (สำหรับ testing)"""
        self._published_messages.clear()
    
    @property
    def is_connected(self) -> bool:
        return self.connected


# Helper functions

def create_anomaly_alert(user_id: int, message: str, data: Dict = None) -> HealthAlert:
    """สร้าง alert สำหรับ anomaly"""
    return HealthAlert(
        user_id=user_id,
        alert_type=AlertType.ANOMALY,
        priority=AlertPriority.HIGH,
        message=message,
        message_en=f"Health anomaly detected for user {user_id}",
        data=data
    )


def create_fatigue_alert(user_id: int, fatigue_score: float) -> HealthAlert:
    """สร้าง alert สำหรับ fatigue"""
    return HealthAlert(
        user_id=user_id,
        alert_type=AlertType.FATIGUE,
        priority=AlertPriority.NORMAL,
        message=f"ตรวจพบความเหนื่อยล้าสูง (คะแนน: {fatigue_score:.0%}) แนะนำให้พักผ่อน",
        message_en=f"High fatigue detected (score: {fatigue_score:.0%}). Rest recommended.",
        data={"fatigue_score": fatigue_score}
    )


def create_nutrition_alert(user_id: int, message: str, macros: Dict = None) -> HealthAlert:
    """สร้าง alert สำหรับ nutrition recommendation"""
    return HealthAlert(
        user_id=user_id,
        alert_type=AlertType.NUTRITION,
        priority=AlertPriority.LOW,
        message=message,
        data={"suggested_macros": macros}
    )


# Test function
def test_mqtt_handler():
    """ทดสอบ MQTT handler ใน mock mode"""
    print("🧪 Testing MQTT Handler in Mock Mode...\n")
    
    handler = MQTTHealthHandler(mock_mode=True)
    
    # Connect
    handler.connect()
    print(f"Connected: {handler.is_connected}")
    
    # Publish alert
    alert = create_anomaly_alert(
        user_id=1,
        message="ตรวจพบอัตราการเต้นหัวใจผิดปกติ",
        data={"heart_rate": 180, "threshold": 160}
    )
    handler.publish_alert(alert)
    
    # Publish health data
    handler.publish_health_data(1, {
        "heart_rate": 75,
        "steps": 5432,
        "calories": 234.5
    })
    
    # Publish status
    handler.publish_status(1, "online", {"battery": 85})
    
    # Check published messages
    messages = handler.get_published_messages()
    print(f"\nPublished {len(messages)} messages:")
    for msg in messages:
        print(f"  - {msg['topic']}")
    
    # Disconnect
    handler.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_mqtt_handler()
