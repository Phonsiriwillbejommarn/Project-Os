import React, { useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { User, Scale, Ruler, Target, Calendar, Save, X, TrendingDown, TrendingUp, Minus } from 'lucide-react';

interface ProfileEditProps {
    user: UserProfile;
    onSave: (updatedUser: Partial<UserProfile>) => Promise<void>;
    onClose: () => void;
}

interface GoalProgress {
    available: boolean;
    goal?: string;
    start_weight?: number;
    current_weight?: number;
    target_weight?: number;
    timeline?: string;
    weeks_elapsed?: number;
    weeks_remaining?: number;
    progress_percent?: number;
    on_track?: boolean;
    milestones?: Array<{
        week: number;
        month: number;
        target_weight: number;
        achieved: boolean;
    }>;
}

const ProfileEdit: React.FC<ProfileEditProps> = ({ user, onSave, onClose }) => {
    const [formData, setFormData] = useState({
        name: user.name || '',
        weight: user.weight || 0,
        height: user.height || 0,
        target_weight: (user as any).target_weight || 0,
        target_timeline: (user as any).target_timeline || '',
        step_goal: user.stepGoal || 10000
    });
    const [saving, setSaving] = useState(false);
    const [goalProgress, setGoalProgress] = useState<GoalProgress | null>(null);

    // Fetch goal progress
    useEffect(() => {
        const fetchGoalProgress = async () => {
            try {
                const res = await fetch(`/users/${user.id}/goal-progress`);
                if (res.ok) {
                    const data = await res.json();
                    setGoalProgress(data);
                    if (data.target_weight) {
                        setFormData(prev => ({ ...prev, target_weight: data.target_weight }));
                    }
                }
            } catch (e) {
                console.error('Failed to fetch goal progress:', e);
            }
        };
        fetchGoalProgress();
    }, [user.id]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: name === 'name' || name === 'target_timeline' ? value : parseFloat(value) || 0
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await onSave({
                name: formData.name,
                weight: formData.weight,
                height: formData.height,
                stepGoal: formData.step_goal,
                ...({
                    target_weight: formData.target_weight,
                    target_timeline: formData.target_timeline
                } as any)
            });
            onClose();
        } catch (e) {
            console.error('Failed to save:', e);
        } finally {
            setSaving(false);
        }
    };

    const getGoalIcon = () => {
        const goalStr = String(user.goal);
        if (goalStr.includes('Lose')) return <TrendingDown className="w-5 h-5 text-red-500" />;
        if (goalStr.includes('Gain')) return <TrendingUp className="w-5 h-5 text-green-500" />;
        return <Minus className="w-5 h-5 text-blue-500" />;
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b">
                    <h2 className="text-lg font-semibold text-gray-800 flex items-center">
                        <User className="w-5 h-5 mr-2 text-emerald-500" />
                        แก้ไขข้อมูลส่วนตัว
                    </h2>
                    <button onClick={onClose} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-4 space-y-4">
                    {/* Name */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">ชื่อ</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                        />
                    </div>

                    {/* Weight & Height */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                <Scale className="w-4 h-4 inline mr-1" />
                                น้ำหนักปัจจุบัน (kg)
                            </label>
                            <input
                                type="number"
                                name="weight"
                                value={formData.weight}
                                onChange={handleChange}
                                step="0.1"
                                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                <Ruler className="w-4 h-4 inline mr-1" />
                                ส่วนสูง (cm)
                            </label>
                            <input
                                type="number"
                                name="height"
                                value={formData.height}
                                onChange={handleChange}
                                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                            />
                        </div>
                    </div>

                    {/* Target Weight */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            <Target className="w-4 h-4 inline mr-1" />
                            น้ำหนักเป้าหมาย (kg)
                        </label>
                        <input
                            type="number"
                            name="target_weight"
                            value={formData.target_weight}
                            onChange={handleChange}
                            step="0.1"
                            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                        />
                    </div>

                    {/* Timeline */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            <Calendar className="w-4 h-4 inline mr-1" />
                            ระยะเวลาเป้าหมาย
                        </label>
                        <select
                            name="target_timeline"
                            value={formData.target_timeline}
                            onChange={handleChange}
                            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                        >
                            <option value="">-- เลือก --</option>
                            <option value="1 week">1 สัปดาห์</option>
                            <option value="2 weeks">2 สัปดาห์</option>
                            <option value="1 month">1 เดือน</option>
                            <option value="3 months">3 เดือน</option>
                        </select>
                    </div>

                    {/* Step Goal */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            เป้าหมายก้าวเดิน / วัน
                        </label>
                        <input
                            type="number"
                            name="step_goal"
                            value={formData.step_goal}
                            onChange={handleChange}
                            step="1000"
                            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-emerald-500"
                        />
                    </div>

                    {/* Buttons */}
                    <div className="flex gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                        >
                            ยกเลิก
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="flex-1 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50 flex items-center justify-center"
                        >
                            <Save className="w-4 h-4 mr-2" />
                            {saving ? 'กำลังบันทึก...' : 'บันทึก'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ProfileEdit;
