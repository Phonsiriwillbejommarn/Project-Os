import React, { useState, useRef, useEffect } from 'react';
import { Message, UserProfile, FoodItem } from '../types';
import { sendMessageToGemini } from '../services/geminiService';
import { Send, Bot, User as UserIcon, Loader2, Image as ImageIcon, X, Trash2 } from 'lucide-react';

interface ChatAssistantProps {
  userProfile: UserProfile;
  foodLogs: FoodItem[];
}

const ChatAssistant: React.FC<ChatAssistantProps> = ({ userProfile, foodLogs }) => {
  const INITIAL_MESSAGE: Message = {
      id: 'welcome',
      role: 'model',
      text: `สวัสดีครับคุณ ${userProfile.name}! ผมคือ NutriFriend เพื่อนคู่คิดด้านโภชนาการของคุณ วันนี้มีอะไรให้ช่วยไหมครับ? 
      
📸 คุณสามารถส่งรูปอาหารเพื่อให้ผมช่วยวิเคราะห์แคลอรี่และสารอาหารได้นะครับ
📊 ผมสามารถดูข้อมูลอาหารที่คุณบันทึกในวันนี้เพื่อแนะนำเพิ่มเติมได้ด้วยครับ`,
      timestamp: Date.now()
    };

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedImage, setSelectedImage] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load chat history from localStorage on mount
  useEffect(() => {
    const savedChat = localStorage.getItem(`nutrifriend_chat_${userProfile.name}`);
    if (savedChat) {
      try {
        setMessages(JSON.parse(savedChat));
      } catch (e) {
        setMessages([INITIAL_MESSAGE]);
      }
    } else {
      setMessages([INITIAL_MESSAGE]);
    }
  }, [userProfile.name]);

  // Save chat history whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(`nutrifriend_chat_${userProfile.name}`, JSON.stringify(messages));
    }
    scrollToBottom();
  }, [messages, userProfile.name]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleClearHistory = () => {
    if (window.confirm('คุณต้องการลบประวัติการสนทนาทั้งหมดใช่หรือไม่?')) {
      setMessages([INITIAL_MESSAGE]);
      localStorage.removeItem(`nutrifriend_chat_${userProfile.name}`);
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
    // Reset input so same file can be selected again if needed
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveImage = () => {
    setSelectedImage(undefined);
  };

  const handleSend = async () => {
    if ((!input.trim() && !selectedImage) || isLoading) return;

    // Prepare User Message
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: input.trim(),
      image: selectedImage,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSelectedImage(undefined);
    setIsLoading(true);

    try {
      // Pass text, image, profile, AND foodLogs to the service
      const responseText = await sendMessageToGemini(userMsg.text, userMsg.image, userProfile, foodLogs);
      
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'model',
        text: responseText,
        timestamp: Date.now()
      };
      
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      console.error(error);
      const errorMsg: Message = {
         id: Date.now().toString(),
         role: 'model',
         text: 'ขออภัย เกิดข้อผิดพลาดในการเชื่อมต่อ กรุณาลองใหม่อีกครั้ง',
         timestamp: Date.now()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
      <div className="bg-emerald-600 p-4 text-white flex items-center justify-between">
        <div className="flex items-center">
          <Bot className="w-6 h-6 mr-2" />
          <h3 className="font-semibold">Chat with NutriFriend AI</h3>
        </div>
        <button 
          onClick={handleClearHistory}
          className="text-emerald-100 hover:text-white p-1 hover:bg-emerald-500 rounded-lg transition"
          title="ล้างประวัติแชท"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg) => (
          <div 
            key={msg.id} 
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[80%] rounded-2xl p-4 shadow-sm ${
              msg.role === 'user' 
                ? 'bg-emerald-600 text-white rounded-br-none' 
                : 'bg-white text-gray-800 rounded-bl-none border border-slate-100'
            }`}>
              <div className="flex items-center gap-2 mb-1 opacity-80 text-xs">
                {msg.role === 'user' ? <UserIcon size={12}/> : <Bot size={12}/>}
                <span>{msg.role === 'user' ? 'คุณ' : 'NutriFriend'}</span>
              </div>
              
              {/* Image Rendering */}
              {msg.image && (
                <div className="mb-2">
                  <img 
                    src={msg.image} 
                    alt="User uploaded" 
                    className="max-w-full rounded-lg border border-emerald-500/20 max-h-60 object-cover"
                  />
                </div>
              )}

              <div className="whitespace-pre-wrap leading-relaxed text-sm">
                {msg.text}
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
             <div className="bg-white text-gray-800 rounded-2xl rounded-bl-none border border-slate-100 p-4 shadow-sm flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
                <span className="text-sm text-gray-500">NutriFriend กำลังวิเคราะห์...</span>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-white border-t border-slate-100">
        {/* Image Preview */}
        {selectedImage && (
          <div className="mb-2 flex items-center gap-2">
            <div className="relative">
              <img 
                src={selectedImage} 
                alt="Selected" 
                className="h-16 w-16 object-cover rounded-lg border border-gray-200"
              />
              <button 
                onClick={handleRemoveImage}
                className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 hover:bg-red-600 transition"
              >
                <X size={12} />
              </button>
            </div>
            <span className="text-xs text-gray-500">พร้อมส่งรูปภาพ</span>
          </div>
        )}

        <div className="flex gap-2 items-center">
          <input 
            type="file" 
            ref={fileInputRef}
            accept="image/*"
            onChange={handleImageSelect}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-full transition-colors"
            title="แนบรูปภาพ"
            disabled={isLoading}
          >
            <ImageIcon className="w-6 h-6" />
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={selectedImage ? "ถามเพิ่มเติมเกี่ยวกับรูปนี้..." : "ถามเกี่ยวกับอาหาร..."}
            className="flex-1 border border-gray-200 rounded-full px-4 py-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || (!input.trim() && !selectedImage)}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 text-white p-2 rounded-full transition-all"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatAssistant;