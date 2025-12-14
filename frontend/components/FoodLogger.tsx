import React, { useState, useRef } from 'react';
import { FoodItem } from '../types';
import { PlusCircle, Trash2, Utensils, Camera, Loader2 } from 'lucide-react';
import { analyzeFoodFromImage } from '../services/geminiService';

interface FoodLoggerProps {
  logs: FoodItem[];
  onAddLog: (log: FoodItem) => void;
  onRemoveLog: (id: string) => void;
  selectedDate: string; // Add selectedDate prop
}

const FoodLogger: React.FC<FoodLoggerProps> = ({ logs, onAddLog, onRemoveLog, selectedDate }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [newFood, setNewFood] = useState({
    name: '',
    calories: '',
    protein: '',
    carbs: '',
    fat: ''
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newFood.name && newFood.calories) {
      const item: FoodItem = {
        id: Date.now().toString(),
        name: newFood.name,
        calories: Number(newFood.calories),
        protein: Number(newFood.protein) || 0,
        carbs: Number(newFood.carbs) || 0,
        fat: Number(newFood.fat) || 0,
        date: selectedDate, // Use the selected date
        timestamp: Date.now()
      };
      onAddLog(item);
      setNewFood({ name: '', calories: '', protein: '', carbs: '', fat: '' });
      setIsOpen(false);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setIsAnalyzing(true);
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64String = reader.result as string;
        const result = await analyzeFoodFromImage(base64String);
        
        if (result) {
          setNewFood({
            name: result.name,
            calories: result.calories.toString(),
            protein: result.protein.toString(),
            carbs: result.carbs.toString(),
            fat: result.fat.toString()
          });
        } else {
          alert('ไม่สามารถวิเคราะห์รูปภาพได้ กรุณาลองใหม่อีกครั้ง');
        }
        setIsAnalyzing(false);
      };
      reader.readAsDataURL(file);
      
      // Reset file input
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Logs are already filtered by parent, but let's just render the list passed in `logs`
  
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
      <div className="p-6 border-b border-gray-100 flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-700 flex items-center">
          <Utensils className="w-5 h-5 mr-2 text-emerald-500" /> บันทึกรายการอาหาร ({new Date(selectedDate).toLocaleDateString('th-TH')})
        </h3>
        <button 
          onClick={() => setIsOpen(!isOpen)}
          className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm px-4 py-2 rounded-full flex items-center transition"
        >
          <PlusCircle className="w-4 h-4 mr-1" /> เพิ่มเมนู
        </button>
      </div>

      {isOpen && (
        <div className="p-6 bg-emerald-50 animate-fade-in-down">
          
          {/* AI Analysis Button */}
          <div className="mb-4">
            <input 
              type="file" 
              ref={fileInputRef}
              accept="image/*"
              className="hidden"
              onChange={handleImageUpload}
            />
            <button 
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isAnalyzing}
              className="w-full bg-indigo-500 hover:bg-indigo-600 text-white py-2 rounded-lg flex items-center justify-center transition shadow-md disabled:opacity-70"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" /> กำลังวิเคราะห์รูปภาพ...
                </>
              ) : (
                <>
                  <Camera className="w-5 h-5 mr-2" /> วิเคราะห์แคลอรี่จากรูปภาพ (AI Scan)
                </>
              )}
            </button>
            <p className="text-xs text-center text-indigo-400 mt-2">
              * ถ่ายรูปอาหารแล้วให้ AI ช่วยกรอกข้อมูลให้คุณอัตโนมัติ
            </p>
          </div>

          <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
            <div className="lg:col-span-1">
              <label className="text-xs font-medium text-gray-500">ชื่อเมนู</label>
              <input 
                type="text" 
                placeholder="ข้าวมันไก่"
                value={newFood.name}
                onChange={e => setNewFood({...newFood, name: e.target.value})}
                className="w-full border border-gray-300 rounded-md p-2 text-sm focus:ring-emerald-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">แคลอรี่ (kcal)</label>
              <input 
                type="number" 
                placeholder="600"
                value={newFood.calories}
                onChange={e => setNewFood({...newFood, calories: e.target.value})}
                className="w-full border border-gray-300 rounded-md p-2 text-sm focus:ring-emerald-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">โปรตีน (g)</label>
              <input 
                type="number" 
                placeholder="20"
                value={newFood.protein}
                onChange={e => setNewFood({...newFood, protein: e.target.value})}
                className="w-full border border-gray-300 rounded-md p-2 text-sm focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
               <label className="text-xs font-medium text-gray-500">คาร์บ (g)</label>
              <input 
                type="number" 
                placeholder="60"
                value={newFood.carbs}
                onChange={e => setNewFood({...newFood, carbs: e.target.value})}
                className="w-full border border-gray-300 rounded-md p-2 text-sm focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div className="flex gap-2">
               <div className="flex-1">
                 <label className="text-xs font-medium text-gray-500">ไขมัน (g)</label>
                  <input 
                    type="number" 
                    placeholder="15"
                    value={newFood.fat}
                    onChange={e => setNewFood({...newFood, fat: e.target.value})}
                    className="w-full border border-gray-300 rounded-md p-2 text-sm focus:ring-emerald-500 focus:outline-none"
                  />
               </div>
               <button 
                type="submit"
                className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-md px-4 h-[38px] mt-auto"
               >
                 บันทึก
               </button>
            </div>
          </form>
        </div>
      )}

      <div className="p-0">
        {logs.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            ยังไม่ได้บันทึกอาหารสำหรับวันที่เลือก
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {logs.map(log => (
              <li key={log.id} className="p-4 hover:bg-slate-50 flex justify-between items-center transition">
                <div>
                  <h4 className="font-medium text-gray-800">{log.name}</h4>
                  <p className="text-xs text-gray-500">
                    {log.calories} kcal | P:{log.protein} C:{log.carbs} F:{log.fat}
                  </p>
                </div>
                <button 
                  onClick={() => onRemoveLog(log.id)}
                  className="text-red-400 hover:text-red-600 p-2"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default FoodLogger;