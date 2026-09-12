import React, { useRef, useEffect } from 'react';
import { useNavigatorStore } from '../../stores/useNavigatorStore';
import { Drawer } from '../ui/Drawer';
import { ChatMessage } from './ChatMessage';
import { SuggestedQuestion } from './SuggestedQuestion';
import { Button } from '../ui/Button';
import { Sparkles, Send, ShieldCheck, Loader2 } from 'lucide-react';

export const NavigatorDrawer: React.FC = () => {
  const {
    isOpen,
    closeDrawer,
    messages,
    suggestedQuestions,
    inputMessage,
    setInputMessage,
    sendMessage,
    askSuggestedQuestion,
    isTyping,
  } = useNavigatorStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen, isTyping]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Drawer
      isOpen={isOpen}
      onClose={closeDrawer}
      position="right"
      width="lg"
      title={
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-[#0F1F38] text-white rounded-lg">
            <Sparkles className="w-4 h-4 text-[#E1EBFA]" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-[#0F1F38] font-heading">
              Ask mondaiy AI Assistant
            </h3>
            <p className="text-[10px] text-[#2A6B4F] font-semibold flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" /> Grounded in Connected Sources
            </p>
          </div>
        </div>
      }
      footer={
        <div className="space-y-3">
          {/* Suggested Questions Carousel */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            {suggestedQuestions.map((q, i) => (
              <SuggestedQuestion
                key={i}
                question={q}
                onClick={() => askSuggestedQuestion(q)}
              />
            ))}
          </div>

          {/* Input box */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask mondaiy about deadlines, updates, or conflicts..."
              className="flex-1 px-3.5 py-2.5 text-xs bg-[#EDF2FB] border border-[#D5DDEB] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563A6] focus:bg-white text-[#0F1F38] placeholder-[#8B98AB]"
            />
            <Button
              variant="primary"
              size="md"
              icon={<Send className="w-4 h-4" />}
              onClick={() => sendMessage()}
              disabled={!inputMessage.trim()}
            >
              Send
            </Button>
          </div>

          <p className="text-[10px] text-[#8B98AB] text-center">
            mondaiy generates traceable responses from your connected sources. Persistent actions require explicit confirmation.
          </p>
        </div>
      }
    >
      <div className="space-y-4">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {isTyping && (
          <div className="flex items-center gap-2 text-xs text-[#5A6A85] p-3 bg-[#EBEFF8] rounded-xl max-w-xs animate-pulse">
            <Loader2 className="w-4 h-4 text-[#2563A6] animate-spin" />
            <span>mondaiy is reviewing source evidence...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </Drawer>
  );
};
