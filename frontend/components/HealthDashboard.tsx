import React, { useState, useEffect, useCallback, useRef } from 'react';
import { HealthData, HealthDecision, HealthSummary, HealthAlert as HealthAlertType } from '../types';
import {
    Heart, Activity, Flame, TrendingUp, AlertTriangle, Zap,
    Brain, Footprints, Bell, CheckCircle, XCircle, Wifi, WifiOff, Watch, Battery
} from 'lucide-react';

interface HealthDashboardProps {
    userId: number;
}

interface WatchStatus {
    available: boolean;
    connected: boolean;
    hr: number;
    steps: number;
    battery: number;
    last_update: number;
}

const HealthDashboard: React.FC<HealthDashboardProps> = ({ userId }) => {
    // State
    const [connected, setConnected] = useState(false);
    const [healthData, setHealthData] = useState<HealthData | null>(null);
    const [decisions, setDecisions] = useState<HealthDecision[]>([]);
    const [alerts, setAlerts] = useState<HealthAlertType[]>([]);
    const [summary, setSummary] = useState<HealthSummary | null>(null);
    const [mode, setMode] = useState<'mock' | 'watch'>('mock');
    const [watchStatus, setWatchStatus] = useState<WatchStatus | null>(null);
    const [connecting, setConnecting] = useState(false);
    const [demoAnomaly, setDemoAnomaly] = useState(false);

    // Refs
    const wsRef = useRef<WebSocket | null>(null);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    // Fetch watch status
    const fetchWatchStatus = useCallback(async () => {
        try {
            const res = await fetch('/watch/status');
            if (res.ok) {
                const data: WatchStatus = await res.json();
                setWatchStatus(data);
                setConnected(data.connected);

                if (data.connected && data.hr > 0) {
                    // Convert watch data to HealthData format
                    const watchHealth: HealthData = {
                        timestamp: data.last_update || Date.now() / 1000,
                        heart_rate: data.hr,
                        steps: data.steps,
                        activity: data.hr < 80 ? 'resting' : data.hr < 100 ? 'walking' : 'light_exercise',
                        anomaly_detected: false,
                        fatigue_score: Math.min(1, (data.hr - 60) / 100),
                        calories_burned: data.steps * 0.04,
                        hr_zone: {
                            zone: data.hr < 100 ? 1 : data.hr < 120 ? 2 : data.hr < 140 ? 3 : 4,
                            name: data.hr < 100 ? 'พักผ่อน' : data.hr < 120 ? 'เผาผลาญไขมัน' : data.hr < 140 ? 'คาร์ดิโอ' : 'Peak',
                            hr_percent: (data.hr / 190) * 100
                        },
                        health_risk_level: data.hr > 150 ? 'MODERATE' : 'LOW',
                        processing_time_ms: 0
                    };
                    setHealthData(watchHealth);
                    setSummary({
                        avg_heart_rate: data.hr,
                        total_steps: data.steps,
                        total_calories: data.steps * 0.04
                    });
                }
            }
        } catch (error) {
            console.error('Failed to fetch watch status:', error);
        }
    }, []);

    // Connect to watch
    const connectWatch = async () => {
        setConnecting(true);
        try {
            await fetch('/watch/connect', { method: 'POST' });
            // Poll for connection
            setTimeout(() => fetchWatchStatus(), 2000);
            setTimeout(() => fetchWatchStatus(), 5000);
            setTimeout(() => {
                fetchWatchStatus();
                setConnecting(false);
            }, 10000);
        } catch (error) {
            console.error('Failed to connect watch:', error);
            setConnecting(false);
        }
    };

    // Generate mock data for demo
    const generateMockData = useCallback(() => {
        const baseHr = demoAnomaly ? 185 + Math.floor(Math.random() * 20) : 70 + Math.floor(Math.random() * 30);
        const mockHealth: HealthData = {
            timestamp: Date.now() / 1000,
            heart_rate: baseHr,
            steps: 5000 + Math.floor(Math.random() * 3000),
            activity: demoAnomaly ? 'intense_exercise' : ['resting', 'walking', 'light_exercise'][Math.floor(Math.random() * 3)],
            hrv: {
                sdnn: demoAnomaly ? 15 + Math.random() * 10 : 40 + Math.random() * 30,
                rmssd: demoAnomaly ? 10 + Math.random() * 10 : 30 + Math.random() * 25,
                pnn50: 10 + Math.random() * 20,
                stress_index: demoAnomaly ? 80 + Math.random() * 15 : 30 + Math.random() * 40
            },
            anomaly_detected: demoAnomaly,
            fatigue_score: demoAnomaly ? 0.85 + Math.random() * 0.1 : 0.2 + Math.random() * 0.4,
            vo2_max: 35 + Math.random() * 15,
            calories_burned: 200 + Math.random() * 300,
            hr_zone: {
                zone: demoAnomaly ? 5 : (baseHr < 100 ? 1 : baseHr < 120 ? 2 : 3),
                name: demoAnomaly ? 'ความเข้มสูงสุด (Max)' : (baseHr < 100 ? 'พักผ่อน' : baseHr < 120 ? 'เผาผลาญไขมัน' : 'คาร์ดิโอ'),
                hr_percent: (baseHr / 190) * 100
            },
            health_risk_level: demoAnomaly ? 'HIGH' : 'LOW',
            processing_time_ms: 5 + Math.random() * 10
        };

        setHealthData(mockHealth);
        setSummary({
            avg_heart_rate: baseHr,
            max_heart_rate: baseHr + 20,
            min_heart_rate: baseHr - 15,
            total_steps: mockHealth.steps,
            total_calories: mockHealth.calories_burned
        });
    }, [demoAnomaly]);

    // Mode effect
    useEffect(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }

        if (mode === 'mock') {
            generateMockData();
            intervalRef.current = setInterval(generateMockData, 2000);
        } else {
            // Watch mode - fetch status every 2 seconds
            fetchWatchStatus();
            intervalRef.current = setInterval(fetchWatchStatus, 2000);
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [mode, generateMockData, fetchWatchStatus]);

    // Fetch alerts
    useEffect(() => {
        const fetchAlerts = async () => {
            try {
                const res = await fetch(`/users/${userId}/health/alerts`);
                if (res.ok) {
                    const data = await res.json();
                    setAlerts(data.alerts || []);
                }
            } catch (error) {
                console.error('Failed to fetch alerts:', error);
            }
        };
        fetchAlerts();
    }, [userId]);

    // Get HR zone color
    const getZoneColor = (zone: number) => {
        const colors = ['#94a3b8', '#22c55e', '#eab308', '#f97316', '#ef4444'];
        return colors[zone - 1] || colors[0];
    };

    // Get risk level color
    const getRiskColor = (level: string) => {
        const colors: Record<string, string> = {
            'LOW': '#22c55e',
            'MODERATE': '#eab308',
            'HIGH': '#f97316',
            'CRITICAL': '#ef4444'
        };
        return colors[level] || '#94a3b8';
    };

    return (
        <div className="space-y-4 animate-fade-in">
            {/* Connection Status */}
            <div className="flex items-center justify-between bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${mode === 'mock' || connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                    <span className="text-sm text-gray-600">
                        {mode === 'mock' ? '🔧 Mock Mode (Demo)' : connected ? '⌚ Aolon Curve Connected' : '⚠️ Watch Disconnected'}
                    </span>
                    {mode === 'watch' && watchStatus && (
                        <span className="text-xs text-gray-400 flex items-center gap-1">
                            <Battery size={12} /> {watchStatus.battery}%
                        </span>
                    )}
                </div>
                <div className="flex gap-2">
                    {mode === 'watch' && !connected && (
                        <button
                            onClick={connectWatch}
                            disabled={connecting}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-50"
                        >
                            <Watch size={16} />
                            {connecting ? 'Connecting...' : 'Connect Watch'}
                        </button>
                    )}
                    <button
                        onClick={() => setMode(mode === 'mock' ? 'watch' : 'mock')}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${mode === 'mock'
                            ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                            : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                            }`}
                    >
                        {mode === 'mock' ? <WifiOff size={16} /> : <Watch size={16} />}
                        {mode === 'mock' ? 'Mock Mode' : 'Watch Mode'}
                    </button>

                </div>
            </div>

            {/* 🚨 Anomaly Detection Alert Banner (ML Result) */}
            {healthData?.anomaly_detected && (
                <div className="bg-red-600 text-white p-4 rounded-2xl shadow-lg border-2 border-red-400 animate-pulse">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <AlertTriangle className="w-8 h-8" />
                            <div>
                                <div className="font-bold text-lg">⚠️ ตรวจพบความผิดปกติ! (Anomaly Detected)</div>
                                <div className="text-sm opacity-90">
                                    ML Model (Isolation Forest) ตรวจพบรูปแบบหัวใจที่ผิดปกติ - HR: {healthData.heart_rate} BPM
                                </div>
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-xs opacity-75">Edge AI Processing</div>
                            <div className="text-sm font-mono">{healthData.processing_time_ms?.toFixed(2)} ms</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Main Health Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Heart Rate */}
                <div className="bg-gradient-to-br from-red-50 to-pink-50 p-5 rounded-2xl shadow-sm border border-red-100">
                    <div className="flex items-center justify-between mb-2">
                        <Heart className="w-6 h-6 text-red-500" />
                        <span className="text-xs text-red-400">BPM</span>
                    </div>
                    <div className="text-3xl font-bold text-red-600">
                        {healthData?.heart_rate || '--'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Heart Rate</div>
                </div>

                {/* Steps */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-5 rounded-2xl shadow-sm border border-blue-100">
                    <div className="flex items-center justify-between mb-2">
                        <Footprints className="w-6 h-6 text-blue-500" />
                        <span className="text-xs text-blue-400">Steps</span>
                    </div>
                    <div className="text-3xl font-bold text-blue-600">
                        {healthData?.steps?.toLocaleString() || '--'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">วันนี้</div>
                </div>

                {/* Calories */}
                <div className="bg-gradient-to-br from-orange-50 to-amber-50 p-5 rounded-2xl shadow-sm border border-orange-100">
                    <div className="flex items-center justify-between mb-2">
                        <Flame className="w-6 h-6 text-orange-500" />
                        <span className="text-xs text-orange-400">kcal</span>
                    </div>
                    <div className="text-3xl font-bold text-orange-600">
                        {healthData?.calories_burned?.toFixed(0) || '--'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">เผาผลาญ</div>
                </div>

                {/* Activity */}
                <div className="bg-gradient-to-br from-emerald-50 to-green-50 p-5 rounded-2xl shadow-sm border border-emerald-100">
                    <div className="flex items-center justify-between mb-2">
                        <Activity className="w-6 h-6 text-emerald-500" />
                        <span className="text-xs text-emerald-400">Activity</span>
                    </div>
                    <div className="text-xl font-bold text-emerald-600 capitalize">
                        {healthData?.activity?.replace('_', ' ') || '--'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">กิจกรรมปัจจุบัน</div>
                </div>
            </div>

            {/* HR Zone & HRV Analysis */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* HR Zone */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                        <TrendingUp className="w-5 h-5 mr-2 text-purple-500" />
                        Heart Rate Zone
                    </h3>

                    {healthData?.hr_zone && (
                        <>
                            <div className="flex items-center justify-between mb-4">
                                <div
                                    className="text-4xl font-bold"
                                    style={{ color: getZoneColor(healthData.hr_zone.zone) }}
                                >
                                    Zone {healthData.hr_zone.zone}
                                </div>
                                <div className="text-right">
                                    <div className="text-sm text-gray-500">{healthData.hr_zone.name}</div>
                                    <div className="text-xs text-gray-400">{healthData.hr_zone.hr_percent.toFixed(0)}% Max HR</div>
                                </div>
                            </div>

                            {/* Zone Bar */}
                            <div className="flex gap-1 h-3">
                                {[1, 2, 3, 4, 5].map((zone) => (
                                    <div
                                        key={zone}
                                        className={`flex-1 rounded transition-all ${zone <= healthData.hr_zone.zone ? 'opacity-100' : 'opacity-30'
                                            }`}
                                        style={{ backgroundColor: getZoneColor(zone) }}
                                    />
                                ))}
                            </div>
                            <div className="flex justify-between text-xs text-gray-400 mt-1">
                                <span>Rest</span>
                                <span>Fat Burn</span>
                                <span>Cardio</span>
                                <span>Peak</span>
                                <span>Max</span>
                            </div>
                        </>
                    )}
                </div>

                {/* HRV Analysis */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                        <Brain className="w-5 h-5 mr-2 text-indigo-500" />
                        HRV Analysis (Pi Computed)
                    </h3>

                    {healthData?.hrv ? (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-slate-50 p-3 rounded-xl">
                                <div className="text-xs text-gray-500 mb-1">SDNN</div>
                                <div className="text-xl font-semibold text-slate-700">
                                    {healthData.hrv.sdnn.toFixed(1)} <span className="text-xs text-gray-400">ms</span>
                                </div>
                            </div>
                            <div className="bg-slate-50 p-3 rounded-xl">
                                <div className="text-xs text-gray-500 mb-1">RMSSD</div>
                                <div className="text-xl font-semibold text-slate-700">
                                    {healthData.hrv.rmssd.toFixed(1)} <span className="text-xs text-gray-400">ms</span>
                                </div>
                            </div>
                            <div className="col-span-2 bg-gradient-to-r from-green-50 to-red-50 p-3 rounded-xl">
                                <div className="flex justify-between items-center mb-2">
                                    <span className="text-xs text-gray-500">Stress Index</span>
                                    <span className="text-sm font-medium" style={{
                                        color: healthData.hrv.stress_index > 70 ? '#ef4444' :
                                            healthData.hrv.stress_index > 50 ? '#eab308' : '#22c55e'
                                    }}>
                                        {healthData.hrv.stress_index.toFixed(0)}/100
                                    </span>
                                </div>
                                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                    <div
                                        className="h-full rounded-full transition-all"
                                        style={{
                                            width: `${healthData.hrv.stress_index}%`,
                                            background: `linear-gradient(to right, #22c55e, #eab308, #ef4444)`
                                        }}
                                    />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="text-gray-400 text-center py-8">
                            รอข้อมูลเพิ่มเติม...
                        </div>
                    )}
                </div>
            </div>

            {/* Fatigue & VO2 Max */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Fatigue Score */}
                <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-gray-500">Fatigue Score</span>
                        <Zap className="w-5 h-5 text-yellow-500" />
                    </div>
                    <div className="relative h-24 flex items-center justify-center">
                        <svg className="w-24 h-24 transform -rotate-90">
                            <circle
                                cx="48" cy="48" r="40"
                                stroke="#e5e7eb" strokeWidth="8" fill="none"
                            />
                            <circle
                                cx="48" cy="48" r="40"
                                stroke={healthData?.fatigue_score && healthData.fatigue_score > 0.7 ? '#ef4444' : '#22c55e'}
                                strokeWidth="8" fill="none"
                                strokeDasharray={`${(healthData?.fatigue_score || 0) * 251.2} 251.2`}
                                className="transition-all duration-500"
                            />
                        </svg>
                        <div className="absolute text-xl font-bold text-gray-700">
                            {((healthData?.fatigue_score || 0) * 100).toFixed(0)}%
                        </div>
                    </div>
                </div>

                {/* VO2 Max */}
                <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-gray-500">VO2 Max (Estimated)</span>
                        <TrendingUp className="w-5 h-5 text-blue-500" />
                    </div>
                    <div className="text-center py-4">
                        <div className="text-4xl font-bold text-blue-600">
                            {healthData?.vo2_max?.toFixed(1) || '--'}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">ml/kg/min</div>
                    </div>
                </div>

                {/* Health Risk */}
                <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-gray-500">Health Risk</span>
                        <AlertTriangle className="w-5 h-5" style={{ color: getRiskColor(healthData?.health_risk_level || 'LOW') }} />
                    </div>
                    <div className="text-center py-4">
                        <div
                            className="text-2xl font-bold uppercase"
                            style={{ color: getRiskColor(healthData?.health_risk_level || 'LOW') }}
                        >
                            {healthData?.health_risk_level || 'LOW'}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">ระดับความเสี่ยง</div>
                    </div>
                </div>
            </div>

            {/* Alerts & Decisions */}
            {(decisions.length > 0 || alerts.length > 0) && (
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                        <Bell className="w-5 h-5 mr-2 text-amber-500" />
                        การแจ้งเตือน & คำแนะนำ
                    </h3>

                    <div className="space-y-3">
                        {decisions.map((decision, index) => (
                            <div
                                key={index}
                                className={`p-4 rounded-xl border-l-4 ${decision.priority === 'HIGH' || decision.priority === 'CRITICAL'
                                    ? 'bg-red-50 border-red-500'
                                    : decision.priority === 'NORMAL'
                                        ? 'bg-amber-50 border-amber-500'
                                        : 'bg-blue-50 border-blue-500'
                                    }`}
                            >
                                <div className="flex items-start justify-between">
                                    <div>
                                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${decision.priority === 'HIGH' || decision.priority === 'CRITICAL'
                                            ? 'bg-red-100 text-red-700'
                                            : 'bg-amber-100 text-amber-700'
                                            }`}>
                                            {decision.action}
                                        </span>
                                        <p className="mt-2 text-sm text-gray-700">{decision.message}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Processing Info */}
            <div className="text-center text-xs text-gray-400">
                🧠 Pi Processing Time: {healthData?.processing_time_ms?.toFixed(2) || '--'} ms |
                Real-time AI Analysis on Raspberry Pi
            </div>
        </div>
    );
};

export default HealthDashboard;
