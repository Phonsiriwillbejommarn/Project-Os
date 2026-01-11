"""
Health AI Engine - Multi-Model ML Pipeline

Pi ทำงานหนักทุกอย่าง:
1. Activity Classification
2. HRV Analysis (Signal Processing)
3. Anomaly Detection (IsolationForest)
4. Fatigue Prediction
5. VO2 Max Estimation
6. Calorie Burn (Advanced Algorithm)

ทั้งหมดรันบน Raspberry Pi โดยไม่ต้องพึ่งพา cloud
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import math

# Try to import ML libraries, fallback to simple implementations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("numpy not installed - using basic math")

try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.warning("scipy not installed - HRV frequency analysis disabled")

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("sklearn not installed - using rule-based anomaly detection")


class ActivityType(str, Enum):
    RESTING = "resting"
    WALKING = "walking"
    LIGHT_EXERCISE = "light_exercise"
    MODERATE_EXERCISE = "moderate_exercise"
    INTENSE_EXERCISE = "intense_exercise"
    SLEEPING = "sleeping"
    UNKNOWN = "unknown"


class HealthRiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class HRVFeatures:
    """Heart Rate Variability Features"""
    sdnn: float          # Standard deviation of NN intervals
    rmssd: float         # Root mean square of successive differences
    pnn50: float         # % of NN intervals > 50ms different from previous
    lf_hf_ratio: Optional[float]  # Low/High frequency power ratio
    stress_index: float  # Calculated stress index (0-100)


@dataclass
class HRZone:
    """Heart Rate Zone Information"""
    zone: int            # 1-5
    name: str           # Zone name
    hr_percent: float   # % of max HR


@dataclass
class ProcessedHealthData:
    """Output from Health AI Engine"""
    timestamp: int
    heart_rate: int
    steps: int
    activity: str
    hrv: Optional[Dict]
    anomaly_detected: bool
    fatigue_score: float
    vo2_max: Optional[float]
    calories_burned: float
    hr_zone: Dict
    health_risk_level: str
    processing_time_ms: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


class HealthAIEngine:
    """
    Health AI Engine - Main ML Pipeline
    
    Runs on Raspberry Pi and processes:
    - Real-time sensor data from smartwatch
    - Calculates HRV, fatigue, VO2 max, etc.
    - Detects anomalies and health risks
    """
    
    def __init__(self, user_age: int = 30, user_weight: float = 70.0):
        # User info for calculations
        self.user_age = user_age
        self.user_weight = user_weight
        self.max_hr = 220 - user_age  # Standard formula
        
        # Buffers for time-series analysis
        self.hr_buffer: List[int] = []
        self.step_buffer: List[int] = []
        self.accel_buffer: List[Tuple[float, float, float]] = []
        
        # Buffer settings
        self.hr_buffer_size = 300     # 5 minutes at 1Hz
        self.step_buffer_size = 60    # 1 minute
        
        # Anomaly detector
        self.anomaly_detector = None
        if SKLEARN_AVAILABLE:
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=50
            )
            self.anomaly_trained = False
        
        # User baseline (should be loaded from DB)
        self.baseline = {
            "resting_hr": 70,
            "max_hr": self.max_hr,
            "avg_steps_per_day": 8000,
            "vo2_max": None
        }
        
        logging.info(f"🧠 Health AI Engine initialized (max_hr={self.max_hr})")
    
    def update_user_info(self, age: int = None, weight: float = None, 
                         resting_hr: int = None):
        """อัพเดตข้อมูล user"""
        if age:
            self.user_age = age
            self.max_hr = 220 - age
            self.baseline["max_hr"] = self.max_hr
        if weight:
            self.user_weight = weight
        if resting_hr:
            self.baseline["resting_hr"] = resting_hr
    
    def process_realtime(
        self, 
        hr: int, 
        steps: int,
        accel_x: float = 0.0,
        accel_y: float = 0.0,
        accel_z: float = 9.8,
        spo2: int = None
    ) -> ProcessedHealthData:
        """
        Main processing pipeline - Pi ประมวลผลทุกอย่าง
        
        Args:
            hr: Heart rate (BPM)
            steps: Current step count
            accel_x/y/z: Accelerometer data
            spo2: Blood oxygen level (optional)
        
        Returns:
            ProcessedHealthData with all computed metrics
        """
        start_time = time.time()
        timestamp = int(start_time)
        
        # Update buffers
        self._update_buffers(hr, steps, (accel_x, accel_y, accel_z))
        
        # 1. Activity Classification
        activity = self._classify_activity(hr, steps, accel_x, accel_y, accel_z)
        
        # 2. HRV Analysis (needs enough data)
        hrv_features = self._calculate_hrv_advanced()
        hrv_dict = asdict(hrv_features) if hrv_features else None
        
        # 3. Anomaly Detection
        is_anomaly = self._detect_health_anomaly(hr, hrv_features, spo2)
        
        # 4. Fatigue Prediction
        fatigue_score = self._predict_fatigue(hr, hrv_features, activity)
        
        # 5. VO2 Max Estimation
        vo2_max = self._estimate_vo2max(hr, activity, steps)
        
        # 6. Calorie Burn (Advanced)
        calories = self._calculate_calories_advanced(hr, activity, vo2_max)
        
        # 7. HR Zone
        hr_zone = self._get_hr_zone(hr)
        
        # 8. Health Risk Assessment
        health_risk = self._assess_health_risk(hr, hrv_features, is_anomaly, spo2)
        
        processing_time = (time.time() - start_time) * 1000  # ms
        
        return ProcessedHealthData(
            timestamp=timestamp,
            heart_rate=hr,
            steps=steps,
            activity=activity.value,
            hrv=hrv_dict,
            anomaly_detected=is_anomaly,
            fatigue_score=round(fatigue_score, 3),
            vo2_max=round(vo2_max, 1) if vo2_max else None,
            calories_burned=round(calories, 2),
            hr_zone=asdict(hr_zone),
            health_risk_level=health_risk.value,
            processing_time_ms=round(processing_time, 2)
        )
    
    def _update_buffers(self, hr: int, steps: int, 
                        accel: Tuple[float, float, float]):
        """อัพเดต time-series buffers"""
        self.hr_buffer.append(hr)
        if len(self.hr_buffer) > self.hr_buffer_size:
            self.hr_buffer.pop(0)
        
        self.step_buffer.append(steps)
        if len(self.step_buffer) > self.step_buffer_size:
            self.step_buffer.pop(0)
        
        self.accel_buffer.append(accel)
        if len(self.accel_buffer) > 60:  # Keep 1 minute
            self.accel_buffer.pop(0)
    
    def _classify_activity(
        self, hr: int, steps: int,
        ax: float, ay: float, az: float
    ) -> ActivityType:
        """จำแนกกิจกรรมจาก sensor data"""
        # Calculate acceleration magnitude
        if NUMPY_AVAILABLE:
            accel_magnitude = np.sqrt(ax**2 + ay**2 + az**2)
        else:
            accel_magnitude = math.sqrt(ax**2 + ay**2 + az**2)
        
        # Step rate (steps per minute)
        step_rate = 0
        if len(self.step_buffer) >= 2:
            step_rate = self.step_buffer[-1] - self.step_buffer[0]
        
        # Classification logic
        if accel_magnitude < 1.5 and step_rate == 0 and hr < 60:
            return ActivityType.SLEEPING
        elif accel_magnitude < 2.0 and step_rate < 5:
            return ActivityType.RESTING
        elif step_rate < 60 and hr < 100:
            return ActivityType.WALKING
        elif hr < 120:
            return ActivityType.LIGHT_EXERCISE
        elif hr < 150:
            return ActivityType.MODERATE_EXERCISE
        elif hr >= 150:
            return ActivityType.INTENSE_EXERCISE
        else:
            return ActivityType.UNKNOWN
    
    def _calculate_hrv_advanced(self) -> Optional[HRVFeatures]:
        """คำนวณ HRV metrics หลายตัว"""
        if len(self.hr_buffer) < 60:  # Need at least 60 samples
            return None
        
        # Get last 60 samples for analysis
        if NUMPY_AVAILABLE:
            hr_series = np.array(self.hr_buffer[-60:])
            
            # Convert HR to RR intervals (ms)
            rr_intervals = 60000 / hr_series
            
            # Time-domain: SDNN
            sdnn = float(np.std(rr_intervals))
            
            # Time-domain: RMSSD
            diff_rr = np.diff(rr_intervals)
            rmssd = float(np.sqrt(np.mean(diff_rr**2)))
            
            # Time-domain: pNN50
            pnn50 = float(np.sum(np.abs(diff_rr) > 50) / len(diff_rr) * 100)
            
            # Frequency-domain analysis (if scipy available)
            lf_hf_ratio = None
            if SCIPY_AVAILABLE and len(rr_intervals) >= 60:
                try:
                    freqs, psd = signal.welch(rr_intervals, fs=1.0, nperseg=min(64, len(rr_intervals)))
                    lf_mask = (freqs >= 0.04) & (freqs < 0.15)
                    hf_mask = (freqs >= 0.15) & (freqs < 0.4)
                    lf_power = float(np.trapz(psd[lf_mask]))
                    hf_power = float(np.trapz(psd[hf_mask]))
                    lf_hf_ratio = lf_power / hf_power if hf_power > 0 else None
                except Exception:
                    pass
        else:
            # Basic calculation without numpy
            hr_series = self.hr_buffer[-60:]
            rr_intervals = [60000 / hr for hr in hr_series]
            
            mean_rr = sum(rr_intervals) / len(rr_intervals)
            variance = sum((rr - mean_rr)**2 for rr in rr_intervals) / len(rr_intervals)
            sdnn = math.sqrt(variance)
            
            diff_rr = [rr_intervals[i+1] - rr_intervals[i] for i in range(len(rr_intervals)-1)]
            rmssd = math.sqrt(sum(d**2 for d in diff_rr) / len(diff_rr))
            pnn50 = sum(1 for d in diff_rr if abs(d) > 50) / len(diff_rr) * 100
            lf_hf_ratio = None
        
        # Calculate stress index
        stress_index = self._calculate_stress_index(sdnn, rmssd, lf_hf_ratio)
        
        return HRVFeatures(
            sdnn=round(sdnn, 2),
            rmssd=round(rmssd, 2),
            pnn50=round(pnn50, 2),
            lf_hf_ratio=round(lf_hf_ratio, 2) if lf_hf_ratio else None,
            stress_index=round(stress_index, 2)
        )
    
    def _calculate_stress_index(
        self, sdnn: float, rmssd: float, 
        lf_hf: Optional[float]
    ) -> float:
        """คำนวณ Stress Index (0-100)"""
        stress = 50  # baseline
        
        # SDNN contribution (lower = more stress)
        if sdnn < 30:
            stress += 25
        elif sdnn < 50:
            stress += 15
        elif sdnn > 100:
            stress -= 15
        elif sdnn > 70:
            stress -= 10
        
        # RMSSD contribution
        if rmssd < 20:
            stress += 20
        elif rmssd < 30:
            stress += 10
        elif rmssd > 60:
            stress -= 10
        
        # LF/HF ratio (higher = more stress/sympathetic activation)
        if lf_hf is not None:
            if lf_hf > 3:
                stress += 15
            elif lf_hf > 2:
                stress += 10
            elif lf_hf < 1:
                stress -= 5
        
        return max(0, min(100, stress))
    
    def _detect_health_anomaly(
        self, hr: int, 
        hrv: Optional[HRVFeatures],
        spo2: int = None
    ) -> bool:
        """ตรวจจับความผิดปกติด้วย rule-based + ML"""
        # Rule-based checks
        if hr < 40 or hr > 200:
            return True
        
        if spo2 is not None and spo2 < 90:
            return True
        
        if hrv and hrv.stress_index > 85:
            return True
        
        # ML-based detection (if trained)
        if SKLEARN_AVAILABLE and self.anomaly_detector is not None and len(self.hr_buffer) >= 30:
            if not self.anomaly_trained and len(self.hr_buffer) >= 100:
                # Train on initial data
                if NUMPY_AVAILABLE:
                    try:
                        training_data = np.array(self.hr_buffer[-100:]).reshape(-1, 1)
                        self.anomaly_detector.fit(training_data)
                        self.anomaly_trained = True
                    except Exception as e:
                        logging.warning(f"Failed to train anomaly detector: {e}")
            
            if self.anomaly_trained:
                if NUMPY_AVAILABLE:
                    try:
                        prediction = self.anomaly_detector.predict([[hr]])
                        if prediction[0] == -1:  # -1 = outlier
                            return True
                    except Exception:
                        pass
        
        return False
    
    def _predict_fatigue(
        self, hr: int, 
        hrv: Optional[HRVFeatures],
        activity: ActivityType
    ) -> float:
        """ทำนาย Fatigue Score (0-1)"""
        fatigue = 0.0
        
        # HR-based fatigue (Heart Rate Reserve used)
        resting_hr = self.baseline["resting_hr"]
        max_hr = self.baseline["max_hr"]
        hr_reserve_used = (hr - resting_hr) / (max_hr - resting_hr)
        hr_reserve_used = max(0, min(1, hr_reserve_used))
        fatigue += hr_reserve_used * 0.4
        
        # HRV-based fatigue
        if hrv:
            # Low RMSSD = high fatigue
            if hrv.rmssd < 20:
                fatigue += 0.25
            elif hrv.rmssd < 30:
                fatigue += 0.15
            
            # High stress = high fatigue
            stress_factor = hrv.stress_index / 100
            fatigue += stress_factor * 0.2
        
        # Activity-based modifier
        if activity in [ActivityType.INTENSE_EXERCISE, ActivityType.MODERATE_EXERCISE]:
            fatigue += 0.1
        elif activity == ActivityType.RESTING:
            fatigue -= 0.05
        
        return max(0.0, min(1.0, fatigue))
    
    def _estimate_vo2max(
        self, hr: int, 
        activity: ActivityType, 
        steps: int
    ) -> Optional[float]:
        """ประมาณการ VO2 Max"""
        # Need exercise state for valid estimation
        if activity not in [ActivityType.MODERATE_EXERCISE, ActivityType.INTENSE_EXERCISE]:
            return self.baseline.get("vo2_max")
        
        # Uth–Sørensen–Overgaard–Pedersen formula
        resting_hr = self.baseline["resting_hr"]
        max_hr = self.baseline["max_hr"]
        
        if resting_hr > 0 and hr > resting_hr:
            hr_ratio = max_hr / resting_hr
            vo2_max = 15.3 * hr_ratio
            
            # Update baseline if valid
            if 20 < vo2_max < 80:  # Reasonable range
                self.baseline["vo2_max"] = vo2_max
            
            return vo2_max
        
        return None
    
    def _calculate_calories_advanced(
        self, hr: int, 
        activity: ActivityType,
        vo2_max: Optional[float]
    ) -> float:
        """คำนวณ Calories Burned แบบละเอียด"""
        # MET values for different activities
        met_values = {
            ActivityType.RESTING: 1.0,
            ActivityType.SLEEPING: 0.9,
            ActivityType.WALKING: 3.5,
            ActivityType.LIGHT_EXERCISE: 5.0,
            ActivityType.MODERATE_EXERCISE: 7.0,
            ActivityType.INTENSE_EXERCISE: 10.0,
            ActivityType.UNKNOWN: 2.0
        }
        
        met = met_values.get(activity, 2.0)
        
        # Base calorie calculation: MET * weight(kg) * 3.5 / 200
        # This gives calories per minute
        calories_per_min = met * self.user_weight * 3.5 / 200
        
        # Adjust with HR factor (higher HR = higher effort)
        hr_factor = 1.0
        if hr > 70:
            hr_factor = 1.0 + (hr - 70) / 150  # Up to ~1.8x at high HR
        
        # VO2 max adjustment (fitter = burns more efficiently)
        vo2_factor = 1.0
        if vo2_max and vo2_max > 40:
            vo2_factor = 1.0 + (vo2_max - 40) / 100
        
        return calories_per_min * hr_factor * vo2_factor
    
    def _get_hr_zone(self, hr: int) -> HRZone:
        """กำหนด Heart Rate Zone"""
        max_hr = self.baseline["max_hr"]
        hr_percent = (hr / max_hr) * 100
        
        if hr_percent < 50:
            return HRZone(zone=1, name="พักผ่อน (Rest)", hr_percent=hr_percent)
        elif hr_percent < 60:
            return HRZone(zone=2, name="เผาผลาญไขมัน (Fat Burn)", hr_percent=hr_percent)
        elif hr_percent < 70:
            return HRZone(zone=3, name="คาร์ดิโอ (Cardio)", hr_percent=hr_percent)
        elif hr_percent < 85:
            return HRZone(zone=4, name="ประสิทธิภาพสูงสุด (Peak)", hr_percent=hr_percent)
        else:
            return HRZone(zone=5, name="ความเข้มสูงสุด (Max)", hr_percent=hr_percent)
    
    def _assess_health_risk(
        self, hr: int, 
        hrv: Optional[HRVFeatures],
        is_anomaly: bool,
        spo2: int = None
    ) -> HealthRiskLevel:
        """ประเมินระดับความเสี่ยงสุขภาพ"""
        if is_anomaly:
            return HealthRiskLevel.HIGH
        
        # Critical thresholds
        if hr > 190 or hr < 40:
            return HealthRiskLevel.CRITICAL
        
        if spo2 is not None and spo2 < 88:
            return HealthRiskLevel.CRITICAL
        
        # High risk checks
        if hr > 180 or hr < 45:
            return HealthRiskLevel.HIGH
        
        if spo2 is not None and spo2 < 92:
            return HealthRiskLevel.HIGH
        
        # Moderate risk
        if hrv and hrv.stress_index > 70:
            return HealthRiskLevel.MODERATE
        
        if hr > 160:
            return HealthRiskLevel.MODERATE
        
        return HealthRiskLevel.LOW
    
    def get_stats(self) -> Dict:
        """ดึงสถิติ buffer"""
        return {
            "hr_buffer_size": len(self.hr_buffer),
            "avg_hr": sum(self.hr_buffer) / len(self.hr_buffer) if self.hr_buffer else 0,
            "baseline": self.baseline,
            "anomaly_trained": getattr(self, 'anomaly_trained', False)
        }


# Test function
def test_health_ai_engine():
    """ทดสอบ Health AI Engine"""
    print("🧪 Testing Health AI Engine...\n")
    
    engine = HealthAIEngine(user_age=30, user_weight=70)
    
    # Simulate data for 2 minutes
    import random
    
    print("Simulating 120 seconds of data...")
    for i in range(120):
        hr = random.randint(65, 85)  # Resting HR
        steps = i * 2
        
        result = engine.process_realtime(
            hr=hr,
            steps=steps,
            accel_x=random.uniform(-0.3, 0.3),
            accel_y=random.uniform(-0.3, 0.3),
            accel_z=random.uniform(9.5, 10.0),
            spo2=random.randint(96, 99)
        )
    
    # Print final result
    print(f"\n📊 Final Result:")
    print(f"  Heart Rate: {result.heart_rate} BPM")
    print(f"  Activity: {result.activity}")
    print(f"  HR Zone: Zone {result.hr_zone['zone']} ({result.hr_zone['name']})")
    print(f"  Fatigue: {result.fatigue_score:.1%}")
    print(f"  Health Risk: {result.health_risk_level}")
    print(f"  Processing Time: {result.processing_time_ms:.2f} ms")
    
    if result.hrv:
        print(f"\n  HRV Analysis:")
        print(f"    SDNN: {result.hrv['sdnn']:.2f} ms")
        print(f"    RMSSD: {result.hrv['rmssd']:.2f} ms")
        print(f"    Stress Index: {result.hrv['stress_index']:.0f}/100")
    
    # Simulate exercise
    print("\n🏃 Simulating exercise (HR 140-160)...")
    for i in range(30):
        hr = random.randint(140, 160)
        result = engine.process_realtime(hr=hr, steps=i*10)
    
    print(f"  Activity: {result.activity}")
    print(f"  Fatigue: {result.fatigue_score:.1%}")
    print(f"  Calories: {result.calories_burned:.1f} kcal/min")
    if result.vo2_max:
        print(f"  VO2 Max: {result.vo2_max:.1f} ml/kg/min")
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_health_ai_engine()
