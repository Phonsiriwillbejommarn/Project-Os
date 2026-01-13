import React, { useState, useEffect, useCallback, useRef } from 'react';
import { HealthData, HealthDecision, HealthSummary, HealthAlert as HealthAlertType } from '../types';
import {
    Heart, Activity, Flame, TrendingUp, AlertTriangle, Zap,
    Brain, Footprints, Bell, CheckCircle, XCircle, Wifi, WifiOff, Watch, Battery, Settings, Save
} from 'lucide-react';

interface HealthDashboardProps {
    userId: number;
    stepGoal: number;
    onStepGoalChange: (newGoal: number) => void;
}

interface WatchStatus {
    available: boolean;
    connected: boolean;
    hr: number;
    steps: number;
    battery: number;
    last_update: number;
}

interface DailyHealthData {
    date: string;
    day_name: string;
    avg_heart_rate: number;
    max_heart_rate: number;
    steps: number;
    calories_burned: number;
}

interface HealthHistory {
    period_start: string;
    period_end: string;
    daily_data: DailyHealthData[];
    summary: {
        total_steps: number;
        avg_daily_steps: number;
        avg_heart_rate: number;
        total_calories_burned: number;
    };
}

const HealthDashboard: React.FC<HealthDashboardProps> = ({ userId, stepGoal, onStepGoalChange }) => {
    // State
    const [connected, setConnected] = useState(false);
    const [healthData, setHealthData] = useState<HealthData | null>(null);
    const [decisions, setDecisions] = useState<HealthDecision[]>([]);
    const [alerts, setAlerts] = useState<HealthAlertType[]>([]);
    const [summary, setSummary] = useState<HealthSummary | null>(null);
    const [mode, setMode] = useState<'mock' | 'watch'>('watch');
    const [watchStatus, setWatchStatus] = useState<WatchStatus | null>(null);
    const [connecting, setConnecting] = useState(false);
    const [editingStepGoal, setEditingStepGoal] = useState(false);
    const [tempStepGoal, setTempStepGoal] = useState(stepGoal);
    const [healthHistory, setHealthHistory] = useState<HealthHistory | null>(null);
    const [chartType, setChartType] = useState<'steps' | 'hr' | 'calories'>('steps');

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

                if (data.connected && (data.steps > 0 || data.battery > 0)) {
                    // Convert watch data to HealthData format
                    const watchHealth: HealthData = {
                        timestamp: data.last_update || Date.now() / 1000,
                        heart_rate: data.hr,
                        steps: data.steps,
                        activity: data.hr < 80 ? 'resting' : data.hr < 100 ? 'walking' : 'light_exercise',
                        anomaly_detected: false,
                        fatigue_score: data.hr > 0 ? Math.min(1, (data.hr - 60) / 100) : 0,
                        calories_burned: data.steps * 0.04,
                        hr_zone: {
                            zone: data.hr < 100 ? 1 : data.hr < 120 ? 2 : data.hr < 140 ? 3 : 4,
                            name: data.hr < 100 ? 'พักผ่อน' : data.hr < 120 ? 'เผาผลาญไขมัน' : data.hr < 140 ? 'คาร์ดิโอ' : 'Peak',
                            hr_percent: data.hr > 0 ? (data.hr / 190) * 100 : 0
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

    // Fetch 7-day health history
    const fetchHealthHistory = useCallback(async () => {
        try {
            const res = await fetch(`/users/${userId}/health/history?days=7`);
            if (res.ok) {
                const data = await res.json();
                setHealthHistory(data);
            }
        } catch (error) {
            console.error('Failed to fetch health history:', error);
        }
    }, [userId]);

    // Fetch health history on mount
    useEffect(() => {
        fetchHealthHistory();
    }, [fetchHealthHistory]);

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
        const baseHr = 70 + Math.floor(Math.random() * 30);
        const mockHealth: HealthData = {
            timestamp: Date.now() / 1000,
            heart_rate: baseHr,
            steps: 5000 + Math.floor(Math.random() * 3000),
            activity: ['resting', 'walking', 'light_exercise'][Math.floor(Math.random() * 3)],
            hrv: {
                sdnn: 40 + Math.random() * 30,
                rmssd: 30 + Math.random() * 25,
                pnn50: 10 + Math.random() * 20,
                stress_index: 30 + Math.random() * 40
            },
            anomaly_detected: false,
            fatigue_score: 0.2 + Math.random() * 0.4,
            vo2_max: 35 + Math.random() * 15,
            calories_burned: 200 + Math.random() * 300,
            hr_zone: {
                zone: baseHr < 100 ? 1 : baseHr < 120 ? 2 : 3,
                name: baseHr < 100 ? 'พักผ่อน' : baseHr < 120 ? 'เผาผลาญไขมัน' : 'คาร์ดิโอ',
                hr_percent: (baseHr / 190) * 100
            },
            health_risk_level: 'LOW',
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
    }, []);

    // WebSocket connection for real-time updates
    useEffect(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }

        if (mode === 'mock') {
            generateMockData();
            intervalRef.current = setInterval(generateMockData, 2000);
        } else {
            // Watch mode - use WebSocket for real-time ML processing
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            // Connect to ML Health Engine endpoint
            const wsUrl = `${wsProtocol}//${window.location.host}/ws/health/${userId}`;

            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                setConnected(true);
                // Start sending watch data to ML engine
                fetchWatchStatus().then(() => {
                    if (watchStatus && watchStatus.hr > 0) {
                        ws.send(JSON.stringify({
                            hr: watchStatus.hr,
                            steps: watchStatus.steps,
                            accel_x: 0,
                            accel_y: 0,
                            accel_z: 9.8
                        }));
                    }
                });
            };

            ws.onmessage = (event) => {
                try {
                    const response = JSON.parse(event.data);

                    // Handle ML-processed health data from backend
                    if (response.health_data) {
                        const mlData = response.health_data;

                        // Use ML-processed data directly!
                        const mlHealthData: HealthData = {
                            timestamp: mlData.timestamp,
                            heart_rate: mlData.heart_rate,
                            steps: mlData.steps,
                            activity: mlData.activity,
                            hrv: mlData.hrv,               // 🧠 ML: HRV Analysis
                            anomaly_detected: mlData.anomaly_detected,  // 🧠 ML: IsolationForest
                            fatigue_score: mlData.fatigue_score,        // 🧠 ML: Fatigue Prediction
                            vo2_max: mlData.vo2_max,       // 🧠 ML: VO2 Max Estimation
                            calories_burned: mlData.calories_burned,    // 🧠 ML: Advanced Calorie
                            hr_zone: mlData.hr_zone,
                            health_risk_level: mlData.health_risk_level,
                            processing_time_ms: mlData.processing_time_ms
                        };

                        setHealthData(mlHealthData);
                        setConnected(true);

                        setSummary({
                            avg_heart_rate: mlData.heart_rate,
                            total_steps: mlData.steps,
                            total_calories: mlData.calories_burned
                        });

                        // Handle AI decisions/alerts
                        if (response.decisions && response.decisions.length > 0) {
                            setDecisions(response.decisions);
                        }
                    }

                    // Also handle legacy watch_update format for compatibility
                    if (response.type === 'watch_update') {
                        setWatchStatus({
                            available: true,
                            connected: response.connected,
                            hr: response.hr,
                            steps: response.steps,
                            battery: response.battery,
                            last_update: response.last_update
                        });

                        // Send to ML engine for processing
                        if (response.hr > 0 && ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({
                                hr: response.hr,
                                steps: response.steps,
                                accel_x: 0,
                                accel_y: 0,
                                accel_z: 9.8
                            }));
                        }
                    }
                } catch (err) {
                    console.error('WebSocket parse error:', err);
                }
            };

            ws.onerror = () => {
                // Fallback to HTTP polling (no ML processing)
                fetchWatchStatus();
                intervalRef.current = setInterval(fetchWatchStatus, 5000);
            };

            ws.onclose = () => {
                setConnected(false);
                // Fallback to HTTP polling if still in watch mode
                fetchWatchStatus();
                intervalRef.current = setInterval(fetchWatchStatus, 5000);
            };

            // Periodically fetch watch data and send to ML engine via WebSocket
            const sendWatchDataToML = async () => {
                try {
                    const res = await fetch('/watch/status');
                    if (res.ok) {
                        const data = await res.json();
                        if (data.connected && data.hr > 0 && ws.readyState === WebSocket.OPEN) {
                            // Send to ML Engine via WebSocket
                            ws.send(JSON.stringify({
                                hr: data.hr,
                                steps: data.steps,
                                accel_x: 0,
                                accel_y: 0,
                                accel_z: 9.8
                            }));

                            // Update watch status
                            setWatchStatus({
                                available: true,
                                connected: data.connected,
                                hr: data.hr,
                                steps: data.steps,
                                battery: data.battery,
                                last_update: data.last_update
                            });
                        }
                    }
                } catch (err) {
                    // Ignore fetch errors
                }
            };

            // Send immediately on connect and then every 1 second
            sendWatchDataToML();
            intervalRef.current = setInterval(sendWatchDataToML, 1000);
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
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
            </div>

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

                {/* Fatigue Score */}
                <div className="bg-gradient-to-br from-emerald-50 to-green-50 p-5 rounded-2xl shadow-sm border border-emerald-100">
                    <div className="flex items-center justify-between mb-2">
                        <Zap className="w-6 h-6 text-yellow-500" />
                        <span className="text-xs text-emerald-400">Fatigue</span>
                    </div>
                    <div className="text-3xl font-bold text-emerald-600">
                        {((healthData?.fatigue_score || 0) * 100).toFixed(0)}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1">ความเหนื่อยล้า</div>
                </div>
            </div>

            {/* HR Zone & AI Insights */}
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
                                        className={`flex-1 rounded transition-all ${zone <= healthData.hr_zone.zone ? 'opacity-100' : 'opacity-30'}`}
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

                {/* AI Health Insights */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                        <Brain className="w-5 h-5 mr-2 text-indigo-500" />
                        ✨ สรุปข้อมูลสุขภาพ
                    </h3>

                    <div className="space-y-3">
                        {/* Activity Analysis */}
                        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 p-3 rounded-xl">
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-xs text-gray-500">กิจกรรมที่ AI วิเคราะห์</span>
                                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                                    {healthData?.heart_rate && healthData.heart_rate > 0 ? 'Real-time' : 'รอข้อมูล'}
                                </span>
                            </div>
                            <div className="text-lg font-semibold text-indigo-700 capitalize">
                                {healthData?.activity?.replace('_', ' ') || 'รอข้อมูล HR'}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">
                                {healthData?.heart_rate && healthData.heart_rate > 0
                                    ? `วิเคราะห์จาก HR ${healthData.heart_rate} BPM`
                                    : 'เปิดหน้าจอ HR บนนาฬิกาเพื่อดูข้อมูล'}
                            </div>
                        </div>

                        {/* Step Goal Progress */}
                        <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-3 rounded-xl">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-gray-500">เป้าหมาย Steps วันนี้</span>
                                <span className="text-sm font-medium text-blue-700">
                                    {healthData?.steps?.toLocaleString() || 0} / {stepGoal.toLocaleString()}
                                </span>
                            </div>
                            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                    className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-600 transition-all duration-500"
                                    style={{ width: `${Math.min(100, ((healthData?.steps || 0) / stepGoal) * 100)}%` }}
                                />
                            </div>
                            <div className="text-xs text-gray-400 mt-1">
                                {healthData?.steps && healthData.steps >= 10000
                                    ? '🎉 ถึงเป้าหมายแล้ว!'
                                    : `อีก ${(10000 - (healthData?.steps || 0)).toLocaleString()} ก้าว`}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* 🧠 ML Analysis Section */}
            <div className="bg-gradient-to-br from-purple-50 via-indigo-50 to-blue-50 p-6 rounded-2xl shadow-sm border border-purple-100">
                <h3 className="text-lg font-semibold text-purple-700 mb-4 flex items-center">
                    <Brain className="w-5 h-5 mr-2" />
                    วิเคราะห์ Heart Rate
                </h3>

                {/* Anomaly Detection */}
                <div className={`p-5 rounded-xl ${healthData?.anomaly_detected ? 'bg-red-100 border-2 border-red-400' : 'bg-green-50 border border-green-200'}`}>
                    <div className="flex items-center gap-3 mb-2">
                        <AlertTriangle className={`w-6 h-6 ${healthData?.anomaly_detected ? 'text-red-500' : 'text-green-500'}`} />
                        <span className="text-sm font-medium text-gray-700">Anomaly Detection</span>
                    </div>
                    <div className={`text-2xl font-bold ${healthData?.anomaly_detected ? 'text-red-600' : 'text-green-600'}`}>
                        {healthData?.anomaly_detected ? '⚠️ ตรวจพบความผิดปกติ' : '✓ สถานะปกติ'}
                    </div>
                    <div className="text-xs text-gray-400 mt-2">ตรวจจับค่าผิดปกติจากอัตราการเต้นของหัวใจ</div>
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

            {/* Step Goal Settings - Moved above chart */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                    <Settings className="w-5 h-5 mr-2 text-gray-500" />
                    ตั้งค่าเป้าหมาย
                </h3>

                <div className="flex items-center justify-between">
                    <div>
                        <label className="text-sm text-gray-600">เป้าหมายก้าวเดินต่อวัน</label>
                        <p className="text-xs text-gray-400">แนะนำ: 8,000 - 12,000 ก้าว</p>
                    </div>

                    {editingStepGoal ? (
                        <div className="flex items-center gap-2">
                            <input
                                type="number"
                                value={tempStepGoal}
                                onChange={(e) => setTempStepGoal(parseInt(e.target.value) || 0)}
                                className="w-24 px-3 py-2 border rounded-lg text-right focus:ring-2 focus:ring-blue-500"
                                min={1000}
                                max={50000}
                                step={1000}
                            />
                            <button
                                onClick={() => {
                                    onStepGoalChange(tempStepGoal);
                                    setEditingStepGoal(false);
                                }}
                                className="p-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                            >
                                <Save className="w-4 h-4" />
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={() => {
                                setTempStepGoal(stepGoal);
                                setEditingStepGoal(true);
                            }}
                            className="px-4 py-2 bg-gray-100 rounded-lg text-gray-700 hover:bg-gray-200 font-medium"
                        >
                            {stepGoal.toLocaleString()} ก้าว
                        </button>
                    )}
                </div>
            </div>

            {/* Walking Statistics - Bar Chart */}
            {healthHistory && (
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-emerald-600 flex items-center">
                            📅 สรุป 7 วันย้อนหลัง
                        </h3>
                        <span className="text-sm text-emerald-500 font-medium">
                            เฉลี่ย {healthHistory.summary.avg_daily_steps.toLocaleString()} ก้าว/วัน
                        </span>
                    </div>

                    {/* Bar Chart */}
                    <div className="relative">
                        {/* Y-Axis Labels */}
                        {(() => {
                            const maxSteps = Math.max(...healthHistory.daily_data.map(d => d.steps), stepGoal);
                            const yMax = Math.ceil(maxSteps / 2500) * 2500;
                            const yLabels = [yMax, yMax * 0.75, yMax * 0.5, yMax * 0.25, 0];

                            return (
                                <div className="flex">
                                    {/* Y Axis */}
                                    <div className="w-12 flex flex-col justify-between text-right pr-2 text-xs text-gray-400" style={{ height: '200px' }}>
                                        {yLabels.map((val, i) => (
                                            <span key={i}>{val.toLocaleString()}</span>
                                        ))}
                                    </div>

                                    {/* Chart Area */}
                                    <div className="flex-1 relative" style={{ height: '200px' }}>
                                        {/* Grid Lines */}
                                        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                                            {[0, 1, 2, 3, 4].map(i => (
                                                <div key={i} className="border-t border-gray-100 w-full" />
                                            ))}
                                        </div>

                                        {/* Target Line */}
                                        <div
                                            className="absolute w-full border-t-2 border-dashed border-gray-300 z-10"
                                            style={{ bottom: `${(stepGoal / yMax) * 100}%` }}
                                        />

                                        {/* Bars */}
                                        <div className="absolute inset-0 flex items-end justify-around px-2">
                                            {healthHistory.daily_data.map((day, index) => {
                                                const chartHeight = 200; // Chart height in pixels
                                                const heightPx = (day.steps / yMax) * chartHeight;
                                                const isOverGoal = day.steps >= stepGoal;

                                                return (
                                                    <div key={index} className="flex flex-col items-center" style={{ width: '12%' }}>
                                                        <div
                                                            className={`w-full rounded-t-lg transition-all ${isOverGoal ? 'bg-red-400' : 'bg-emerald-400'}`}
                                                            style={{ height: `${Math.max(heightPx, day.steps > 0 ? 4 : 0)}px` }}
                                                        />
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>
                            );
                        })()}

                        {/* X-Axis Labels */}
                        <div className="flex mt-2 pl-12">
                            {healthHistory.daily_data.map((day, index) => {
                                const thaiDaysShort = ['อา.', 'จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.'];
                                const dayOfWeek = new Date(day.date).getDay();
                                return (
                                    <div key={index} className="flex-1 text-center text-xs text-gray-500">
                                        {thaiDaysShort[dayOfWeek]}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Legend */}
                    <div className="flex items-center justify-center gap-6 mt-4 text-xs">
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded bg-emerald-400" />
                            <span className="text-gray-500">ก้าวเดิน</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-4 border-t-2 border-dashed border-gray-400" />
                            <span className="text-gray-500">เป้าหมาย ({stepGoal.toLocaleString()})</span>
                        </div>
                    </div>

                    {/* Summary Stats */}
                    <div className="grid grid-cols-2 gap-4 mt-4">
                        <div className="bg-gradient-to-br from-blue-50 to-cyan-50 p-4 rounded-xl">
                            <div className="text-xs text-blue-600 mb-1">รวมก้าวเดิน</div>
                            <div className="text-2xl font-bold text-blue-700">
                                {healthHistory.summary.total_steps.toLocaleString()}
                            </div>
                        </div>
                        <div className="bg-gradient-to-br from-orange-50 to-red-50 p-4 rounded-xl">
                            <div className="text-xs text-orange-600 mb-1">เผาผลาญแคลอรี่</div>
                            <div className="text-2xl font-bold text-orange-700">
                                {healthHistory.summary.total_calories_burned.toLocaleString()} kcal
                            </div>
                        </div>
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
