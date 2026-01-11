"""
Health Coach Engine - Decision Making

Pi ตัดสินใจและสั่งการ:
- Alerts (ผิดปกติ)
- Recommendations (แนะนำ)
- Plan Adjustments (ปรับแผน)
- Nutrition Integration (ผสมกับข้อมูลอาหาร)

ทำงานร่วมกับ Health AI Engine และ MQTT Handler
"""

import json
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

from mqtt_handler import (
    MQTTHealthHandler, 
    HealthAlert, 
    AlertType, 
    AlertPriority,
    create_anomaly_alert,
    create_fatigue_alert,
    create_nutrition_alert
)


class ActionType(str, Enum):
    ALERT = "ALERT"
    RECOMMENDATION = "RECOMMENDATION"
    ADJUST_PLAN = "ADJUST_PLAN"
    NUTRITION = "NUTRITION"
    WORKOUT_SUMMARY = "WORKOUT_SUMMARY"


@dataclass
class Decision:
    """A decision made by the Health Coach"""
    action: ActionType
    priority: str
    message: str
    message_en: Optional[str] = None
    data: Optional[Dict] = None
    notification_channels: List[str] = field(default_factory=lambda: ["websocket"])
    timestamp: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(time.time())
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result["action"] = self.action.value
        return result


class HealthCoachEngine:
    """
    Health Coach Engine - Decision Making System
    
    Takes processed health data and makes intelligent decisions:
    - Detects anomalies and sends alerts
    - Provides workout recommendations
    - Adjusts training plans based on performance
    - Integrates health with nutrition advice
    """
    
    def __init__(
        self, 
        mqtt_handler: MQTTHealthHandler = None,
        enable_mqtt: bool = True
    ):
        self.mqtt_handler = mqtt_handler
        self.enable_mqtt = enable_mqtt
        
        # User baselines (should be loaded from DB)
        self.user_baselines: Dict[int, Dict] = {}
        
        # Decision history (for avoiding duplicate alerts)
        self.recent_decisions: Dict[int, List[Decision]] = {}
        self.decision_cooldown = 60  # seconds between similar decisions
        
        # Thresholds
        self.thresholds = {
            "fatigue_warning": 0.7,
            "fatigue_critical": 0.85,
            "stress_warning": 60,
            "stress_critical": 80,
            "vo2_decline_percent": 10,
            "workout_calorie_threshold": 200
        }
        
        logging.info("🏃 Health Coach Engine initialized")
    
    def set_user_baseline(self, user_id: int, baseline: Dict):
        """ตั้งค่า baseline สำหรับ user"""
        self.user_baselines[user_id] = baseline
    
    def make_decisions(
        self, 
        processed_data: Dict, 
        user_id: int,
        nutrition_data: Dict = None
    ) -> List[Decision]:
        """
        Pi ตัดสินใจและสั่งการเอง
        
        Args:
            processed_data: Output from HealthAIEngine
            user_id: User identifier
            nutrition_data: Optional nutrition info for integration
        
        Returns:
            List of decisions to execute
        """
        decisions: List[Decision] = []
        
        # Initialize user recent decisions if needed
        if user_id not in self.recent_decisions:
            self.recent_decisions[user_id] = []
        
        # Clean old decisions
        self._clean_old_decisions(user_id)
        
        # 1. ตรวจจับความผิดปกติ → Alert
        if processed_data.get("anomaly_detected"):
            alert = self._handle_anomaly(processed_data, user_id)
            if alert and not self._is_duplicate(user_id, alert):
                decisions.append(alert)
        
        # 2. Fatigue สูง → Recommend พัก
        fatigue = processed_data.get("fatigue_score", 0)
        fatigue_decision = self._handle_fatigue(fatigue, processed_data, user_id)
        if fatigue_decision and not self._is_duplicate(user_id, fatigue_decision):
            decisions.append(fatigue_decision)
        
        # 3. Stress สูง → แนะนำ recovery
        stress_decision = self._handle_stress(processed_data, user_id)
        if stress_decision and not self._is_duplicate(user_id, stress_decision):
            decisions.append(stress_decision)
        
        # 4. VO2 Max monitoring
        vo2_decision = self._handle_vo2_changes(processed_data, user_id)
        if vo2_decision:
            decisions.append(vo2_decision)
        
        # 5. ผสม Health + Nutrition
        if processed_data.get("calories_burned", 0) > self.thresholds["workout_calorie_threshold"]:
            nutrition_decision = self._handle_nutrition_recommendation(
                processed_data, nutrition_data, user_id
            )
            if nutrition_decision:
                decisions.append(nutrition_decision)
        
        # 6. HR Zone warnings
        zone_decision = self._handle_hr_zone(processed_data, user_id)
        if zone_decision and not self._is_duplicate(user_id, zone_decision):
            decisions.append(zone_decision)
        
        # Store decisions
        self.recent_decisions[user_id].extend(decisions)
        
        return decisions
    
    def _handle_anomaly(self, data: Dict, user_id: int) -> Optional[Decision]:
        """จัดการกับ anomaly"""
        hr = data.get("heart_rate", 0)
        risk_level = data.get("health_risk_level", "LOW")
        
        if risk_level == "CRITICAL":
            priority = "CRITICAL"
            message = f"⚠️ ตรวจพบสัญญาณสุขภาพวิกฤต! HR: {hr} BPM"
            message_en = f"Critical health signal detected! HR: {hr} BPM"
        elif risk_level == "HIGH":
            priority = "HIGH"
            message = f"🔴 ตรวจพบรูปแบบหัวใจผิดปกติ HR: {hr} BPM"
            message_en = f"Abnormal heart pattern detected HR: {hr} BPM"
        else:
            priority = "NORMAL"
            message = f"⚡ ตรวจพบค่าผิดปกติ กรุณาตรวจสอบ"
            message_en = "Unusual values detected, please check"
        
        return Decision(
            action=ActionType.ALERT,
            priority=priority,
            message=message,
            message_en=message_en,
            data={
                "heart_rate": hr,
                "health_risk": risk_level,
                "hrv": data.get("hrv")
            },
            notification_channels=["websocket", "mqtt"]
        )
    
    def _handle_fatigue(
        self, fatigue: float, 
        data: Dict, 
        user_id: int
    ) -> Optional[Decision]:
        """จัดการกับ fatigue สูง"""
        if fatigue > self.thresholds["fatigue_critical"]:
            return Decision(
                action=ActionType.RECOMMENDATION,
                priority="HIGH",
                message=f"😴 ตรวจพบความเหนื่อยล้าสูงมาก ({fatigue:.0%}) แนะนำหยุดพักทันที",
                message_en=f"Very high fatigue detected ({fatigue:.0%}). Stop and rest immediately.",
                data={
                    "fatigue_score": fatigue,
                    "recommended_action": "rest_immediately"
                },
                notification_channels=["websocket", "mqtt"]
            )
        elif fatigue > self.thresholds["fatigue_warning"]:
            return Decision(
                action=ActionType.RECOMMENDATION,
                priority="NORMAL",
                message=f"😌 ความเหนื่อยล้าสูง ({fatigue:.0%}) แนะนำลดความเข้มข้น",
                message_en=f"High fatigue ({fatigue:.0%}). Consider reducing intensity.",
                data={
                    "fatigue_score": fatigue,
                    "recommended_hr_zone": "Zone 1-2",
                    "recommended_action": "reduce_intensity"
                }
            )
        return None
    
    def _handle_stress(self, data: Dict, user_id: int) -> Optional[Decision]:
        """จัดการกับ stress สูง"""
        hrv = data.get("hrv")
        if not hrv:
            return None
        
        stress_index = hrv.get("stress_index", 0)
        activity = data.get("activity", "unknown")
        
        # Only warn during exercise
        if activity not in ["moderate_exercise", "intense_exercise"]:
            return None
        
        if stress_index > self.thresholds["stress_critical"]:
            return Decision(
                action=ActionType.RECOMMENDATION,
                priority="HIGH",
                message=f"🧘 ความเครียดสูงมาก (Stress: {stress_index:.0f}/100) แนะนำทำ recovery",
                message_en=f"Very high stress (Stress: {stress_index:.0f}/100). Recovery recommended.",
                data={
                    "stress_index": stress_index,
                    "suggested_action": "breathing_exercise"
                }
            )
        elif stress_index > self.thresholds["stress_warning"]:
            return Decision(
                action=ActionType.RECOMMENDATION,
                priority="LOW",
                message=f"💆 ความเครียดค่อนข้างสูง พิจารณาพักหายใจ",
                message_en="Stress is elevated. Consider a breathing break.",
                data={
                    "stress_index": stress_index,
                    "suggested_action": "short_break"
                }
            )
        return None
    
    def _handle_vo2_changes(self, data: Dict, user_id: int) -> Optional[Decision]:
        """ตรวจสอบการเปลี่ยนแปลงของ VO2 Max"""
        vo2_max = data.get("vo2_max")
        if not vo2_max:
            return None
        
        baseline = self.user_baselines.get(user_id, {})
        baseline_vo2 = baseline.get("vo2_max")
        
        if not baseline_vo2:
            # First reading, set baseline
            if user_id not in self.user_baselines:
                self.user_baselines[user_id] = {}
            self.user_baselines[user_id]["vo2_max"] = vo2_max
            return None
        
        decline_threshold = self.thresholds["vo2_decline_percent"] / 100
        
        if vo2_max < baseline_vo2 * (1 - decline_threshold):
            return Decision(
                action=ActionType.ADJUST_PLAN,
                priority="LOW",
                message=f"📉 VO2 Max ลดลง ({vo2_max:.1f} vs {baseline_vo2:.1f}) แนะนำเพิ่มการออกกำลังกายแบบ cardio",
                message_en=f"VO2 Max declining ({vo2_max:.1f} vs {baseline_vo2:.1f}). Increase cardio training.",
                data={
                    "current_vo2": vo2_max,
                    "baseline_vo2": baseline_vo2,
                    "plan_modification": self._generate_cardio_plan()
                }
            )
        elif vo2_max > baseline_vo2 * 1.05:
            # Update baseline on improvement
            self.user_baselines[user_id]["vo2_max"] = vo2_max
        
        return None
    
    def _handle_nutrition_recommendation(
        self, health_data: Dict, 
        nutrition_data: Dict,
        user_id: int
    ) -> Optional[Decision]:
        """แนะนำโภชนาการหลัง workout"""
        calories_burned = health_data.get("calories_burned", 0)
        activity = health_data.get("activity", "unknown")
        
        if activity in ["moderate_exercise", "intense_exercise"]:
            # Calculate recommended macros based on workout
            protein_boost = int(calories_burned / 20)  # ~1g protein per 20 cal burned
            carb_boost = int(calories_burned / 10)     # ~1g carbs per 10 cal burned
            
            # Check current nutrition if available
            current_protein = 0
            if nutrition_data:
                current_protein = nutrition_data.get("protein", 0)
            
            return Decision(
                action=ActionType.NUTRITION,
                priority="LOW",
                message=f"🍎 ออกกำลังกายดี! เผาผลาญไป {calories_burned:.0f} kcal แนะนำเติมโปรตีน +{protein_boost}g",
                message_en=f"Great workout! Burned {calories_burned:.0f} kcal. Refuel with +{protein_boost}g protein.",
                data={
                    "calories_burned": calories_burned,
                    "suggested_macros": {
                        "protein": f"+{protein_boost}g",
                        "carbs": f"+{carb_boost}g"
                    },
                    "activity": activity
                }
            )
        return None
    
    def _handle_hr_zone(self, data: Dict, user_id: int) -> Optional[Decision]:
        """ตรวจสอบ HR Zone"""
        hr_zone = data.get("hr_zone", {})
        zone = hr_zone.get("zone", 1)
        
        if zone >= 5:
            return Decision(
                action=ActionType.RECOMMENDATION,
                priority="NORMAL",
                message=f"💓 อยู่ใน Zone {zone} (ความเข้มสูงสุด) ไม่ควรอยู่นานเกิน 2-3 นาที",
                message_en=f"In Zone {zone} (Maximum). Don't stay here more than 2-3 minutes.",
                data=hr_zone
            )
        return None
    
    def _generate_cardio_plan(self) -> Dict:
        """สร้างแผนพัฒนา cardio"""
        return {
            "type": "cardio_improvement",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "intensity": "moderate",
            "activities": ["running", "cycling", "swimming"],
            "target_zones": ["Zone 3", "Zone 4"],
            "rest_days": 2
        }
    
    def _is_duplicate(self, user_id: int, decision: Decision) -> bool:
        """ตรวจสอบว่า decision ซ้ำกับที่เพิ่งส่งไปรึเปล่า"""
        recent = self.recent_decisions.get(user_id, [])
        now = time.time()
        
        for d in recent:
            # Same action type within cooldown period
            if (d.action == decision.action and 
                now - d.timestamp < self.decision_cooldown):
                return True
        
        return False
    
    def _clean_old_decisions(self, user_id: int):
        """ลบ decisions เก่าๆ"""
        if user_id not in self.recent_decisions:
            return
        
        now = time.time()
        self.recent_decisions[user_id] = [
            d for d in self.recent_decisions[user_id]
            if now - d.timestamp < self.decision_cooldown * 2
        ]
    
    async def execute_decisions(
        self, decisions: List[Decision], 
        user_id: int,
        websocket_callback: Any = None
    ):
        """ส่ง decisions ไปยัง channels ต่างๆ"""
        for decision in decisions:
            channels = decision.notification_channels
            
            # MQTT
            if "mqtt" in channels and self.mqtt_handler and self.enable_mqtt:
                alert = HealthAlert(
                    user_id=user_id,
                    alert_type=AlertType(decision.action.value) if decision.action.value in [e.value for e in AlertType] else AlertType.SYSTEM,
                    priority=AlertPriority(decision.priority),
                    message=decision.message,
                    message_en=decision.message_en,
                    data=decision.data
                )
                self.mqtt_handler.publish_alert(alert)
            
            # WebSocket
            if "websocket" in channels and websocket_callback:
                await websocket_callback(decision.to_dict())
            
            logging.info(f"📤 Decision executed: {decision.action.value} -> {decision.message[:50]}...")
    
    def get_summary(self, user_id: int) -> Dict:
        """สรุปสถานะการตัดสินใจ"""
        recent = self.recent_decisions.get(user_id, [])
        return {
            "user_id": user_id,
            "recent_decisions_count": len(recent),
            "baseline": self.user_baselines.get(user_id, {}),
            "thresholds": self.thresholds
        }


# Test function
def test_health_coach():
    """ทดสอบ Health Coach Engine"""
    print("🧪 Testing Health Coach Engine...\n")
    
    # Create with mock MQTT
    from mqtt_handler import MQTTHealthHandler
    mqtt = MQTTHealthHandler(mock_mode=True)
    mqtt.connect()
    
    coach = HealthCoachEngine(mqtt_handler=mqtt)
    
    # Test with normal data
    print("Testing with normal data:")
    decisions = coach.make_decisions({
        "heart_rate": 75,
        "steps": 5000,
        "activity": "resting",
        "fatigue_score": 0.3,
        "hrv": {"stress_index": 45}
    }, user_id=1)
    print(f"  Decisions: {len(decisions)}")
    
    # Test with anomaly
    print("\nTesting with anomaly:")
    decisions = coach.make_decisions({
        "heart_rate": 185,
        "anomaly_detected": True,
        "health_risk_level": "HIGH",
        "fatigue_score": 0.9,
        "hrv": {"stress_index": 85}
    }, user_id=1)
    print(f"  Decisions: {len(decisions)}")
    for d in decisions:
        print(f"    - {d.action.value}: {d.message[:50]}...")
    
    # Test with workout
    print("\nTesting after workout:")
    decisions = coach.make_decisions({
        "heart_rate": 145,
        "activity": "moderate_exercise",
        "calories_burned": 350,
        "fatigue_score": 0.6,
        "vo2_max": 42.5
    }, user_id=1)
    print(f"  Decisions: {len(decisions)}")
    for d in decisions:
        print(f"    - {d.action.value}: {d.message[:50]}...")
    
    # Check MQTT messages
    messages = mqtt.get_published_messages()
    print(f"\nMQTT messages sent: {len(messages)}")
    
    mqtt.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_health_coach()
