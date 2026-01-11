import React from 'react';
import { UserProfile, DailyStats, FoodItem } from '../types';
import {
    Heart, Footprints, Flame, Target, Utensils, Zap,
    TrendingUp, Activity, CheckCircle
} from 'lucide-react';

interface OverviewDashboardProps {
    user: UserProfile;
    stats: DailyStats;
    healthData: {
        heart_rate: number;
        steps: number;
        calories_burned: number;
        activity: string;
        battery: number;
        fatigue_score?: number;
    } | null;
    navigateToNutrition: () => void;
    navigateToHealth: () => void;
}

const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
    user, stats, healthData, navigateToNutrition, navigateToHealth
}) => {
    const targetCalories = user.targetCalories || 2000;
    const remainingCalories = targetCalories - stats.calories;
    const calPercentage = Math.min(100, (stats.calories / targetCalories) * 100);

    // Fatigue score calculation
    const fatigueScore = healthData?.fatigue_score ||
        (healthData?.heart_rate ? Math.min(1, (healthData.heart_rate - 60) / 100) : 0);

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="text-center mb-6">
                <h2 className="text-2xl font-bold text-gray-800">
                    สวัสดี, {user.name || 'คุณ'}! 👋
                </h2>
                <p className="text-gray-500 text-sm mt-1">
                    นี่คือสรุปภาพรวมสุขภาพและโภชนาการของคุณวันนี้
                </p>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Calories Today */}
                <div
                    className="bg-gradient-to-br from-emerald-50 to-green-50 p-5 rounded-2xl shadow-sm border border-emerald-100 cursor-pointer hover:shadow-md transition-shadow"
                    onClick={navigateToNutrition}
                >
                    <div className="flex items-center justify-between mb-2">
                        <Utensils className="w-6 h-6 text-emerald-500" />
                        <span className="text-xs text-emerald-400">kcal</span>
                    </div>
                    <div className="text-3xl font-bold text-emerald-600">
                        {stats.calories.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">กินไปแล้ว</div>
                </div>

                {/* Remaining */}
                <div
                    className="bg-gradient-to-br from-blue-50 to-indigo-50 p-5 rounded-2xl shadow-sm border border-blue-100 cursor-pointer hover:shadow-md transition-shadow"
                    onClick={navigateToNutrition}
                >
                    <div className="flex items-center justify-between mb-2">
                        <Target className="w-6 h-6 text-blue-500" />
                        <span className="text-xs text-blue-400">kcal</span>
                    </div>
                    <div className={`text-3xl font-bold ${remainingCalories < 0 ? 'text-red-500' : 'text-blue-600'}`}>
                        {remainingCalories.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">ทานได้อีก</div>
                </div>

                {/* Heart Rate */}
                <div
                    className="bg-gradient-to-br from-red-50 to-pink-50 p-5 rounded-2xl shadow-sm border border-red-100 cursor-pointer hover:shadow-md transition-shadow"
                    onClick={navigateToHealth}
                >
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
                <div
                    className="bg-gradient-to-br from-purple-50 to-violet-50 p-5 rounded-2xl shadow-sm border border-purple-100 cursor-pointer hover:shadow-md transition-shadow"
                    onClick={navigateToHealth}
                >
                    <div className="flex items-center justify-between mb-2">
                        <Footprints className="w-6 h-6 text-purple-500" />
                        <span className="text-xs text-purple-400">Steps</span>
                    </div>
                    <div className="text-3xl font-bold text-purple-600">
                        {healthData?.steps?.toLocaleString() || '--'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">ก้าววันนี้</div>
                </div>
            </div>

            {/* Progress Section */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Nutrition Progress */}
                <div
                    className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 cursor-pointer hover:shadow-md transition-shadow"
                    onClick={navigateToNutrition}
                >
                    <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                        <CheckCircle className="w-5 h-5 mr-2 text-emerald-500" />
                        ความคืบหน้าโภชนาการ
                    </h3>

                    {/* Calories Progress Bar */}
                    <div className="mb-4">
                        <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-600">{stats.calories} / {targetCalories} kcal</span>
                            <span className="font-semibold text-emerald-600">{Math.round(calPercentage)}%</span>
                        </div>
                        <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all duration-500 ${remainingCalories < 0 ? 'bg-red-500' : 'bg-emerald-500'}`}
                                style={{ width: `${calPercentage}%` }}
                            />
                        </div>
                    </div>

                    {/* Macros Summary */}
                    <div className="grid grid-cols-3 gap-3 text-center">
                        <div className="bg-amber-50 p-2 rounded-lg">
                            <div className="text-lg font-bold text-amber-600">{stats.carbs}g</div>
                            <div className="text-xs text-gray-500">คาร์บ</div>
                        </div>
                        <div className="bg-emerald-50 p-2 rounded-lg">
                            <div className="text-lg font-bold text-emerald-600">{stats.protein}g</div>
                            <div className="text-xs text-gray-500">โปรตีน</div>
                        </div>
                        <div className="bg-red-50 p-2 rounded-lg">
                            <div className="text-lg font-bold text-red-500">{stats.fat}g</div>
                            <div className="text-xs text-gray-500">ไขมัน</div>
                        </div>
                    </div>

                    <div className="mt-4 text-center">
                        <span className="text-xs text-blue-500 hover:underline">ดูรายละเอียด →</span>
                    </div>
                </div>

                {/* Health Progress */}
                <div
                    className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 cursor-pointer hover:shadow-md transition-shadow"
                    onClick={navigateToHealth}
                >
                    <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                        <Activity className="w-5 h-5 mr-2 text-purple-500" />
                        สรุปสุขภาพ
                    </h3>

                    {/* Steps Progress */}
                    <div className="mb-4">
                        <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-600">{healthData?.steps?.toLocaleString() || 0} / 10,000 ก้าว</span>
                            <span className="font-semibold text-purple-600">
                                {Math.min(100, Math.round(((healthData?.steps || 0) / 10000) * 100))}%
                            </span>
                        </div>
                        <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-purple-500 rounded-full transition-all duration-500"
                                style={{ width: `${Math.min(100, ((healthData?.steps || 0) / 10000) * 100)}%` }}
                            />
                        </div>
                    </div>

                    {/* Health Stats */}
                    <div className="grid grid-cols-3 gap-3 text-center">
                        <div className="bg-orange-50 p-2 rounded-lg">
                            <div className="text-lg font-bold text-orange-600">
                                {healthData?.calories_burned?.toFixed(0) || '--'}
                            </div>
                            <div className="text-xs text-gray-500">kcal เบิร์น</div>
                        </div>
                        <div className="bg-indigo-50 p-2 rounded-lg">
                            <div className="text-lg font-bold text-indigo-600 capitalize">
                                {healthData?.activity?.replace('_', ' ') || '--'}
                            </div>
                            <div className="text-xs text-gray-500">กิจกรรม</div>
                        </div>
                        <div className="bg-yellow-50 p-2 rounded-lg">
                            <div className="text-lg font-bold text-yellow-600">
                                {(fatigueScore * 100).toFixed(0)}%
                            </div>
                            <div className="text-xs text-gray-500">เหนื่อยล้า</div>
                        </div>
                    </div>

                    <div className="mt-4 text-center">
                        <span className="text-xs text-blue-500 hover:underline">ดูรายละเอียด →</span>
                    </div>
                </div>
            </div>

            {/* Watch Connection Status */}
            <div className="bg-gradient-to-r from-slate-50 to-slate-100 p-4 rounded-2xl border border-slate-200 text-center">
                <div className="flex items-center justify-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${healthData?.heart_rate ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                    <span className="text-sm text-gray-600">
                        {healthData?.heart_rate
                            ? `⌚ นาฬิกาเชื่อมต่อแล้ว (แบตเตอรี่ ${healthData.battery}%)`
                            : '⚠️ ยังไม่ได้เชื่อมต่อนาฬิกา'}
                    </span>
                </div>
            </div>
        </div>
    );
};

export default OverviewDashboard;
