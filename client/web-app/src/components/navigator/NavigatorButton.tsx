import React from 'react';
import { useNavigatorStore } from '../../stores/useNavigatorStore';
import { Sparkles } from 'lucide-react';

export const NavigatorButton: React.FC = () => {
  const { openDrawer, isOpen } = useNavigatorStore();

  if (isOpen) return null;

  return (
    <button
      onClick={openDrawer}
      className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-3 bg-[#0F1F38] hover:bg-[#1E4E85] text-white rounded-full shadow-xl hover:shadow-2xl border border-[#2563A6] transition-all duration-200 active:scale-95 group focus:outline-none focus:ring-2 focus:ring-[#2563A6] focus:ring-offset-2"
      aria-label="Ask mondaiy AI Agent"
    >
      <div className="p-1 bg-[#2563A6] text-white rounded-full group-hover:rotate-12 transition-transform">
        <Sparkles className="w-4 h-4 text-[#E1EBFA]" />
      </div>
      <span className="text-xs font-bold tracking-wide">Ask mondaiy</span>
      <span className="w-2 h-2 rounded-full bg-[#2A6B4F] animate-ping" />
    </button>
  );
};
