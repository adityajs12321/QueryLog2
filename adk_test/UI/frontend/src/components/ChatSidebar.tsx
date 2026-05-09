'use client';

import { useCallback } from 'react';
import { ChatSession } from '@/types/chat';

interface ChatSidebarProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewChat: () => void;
}

export const ChatSidebar = ({
  sessions,
  currentSessionId,
  onSessionSelect,
  onNewChat,
}: ChatSidebarProps) => {
  const formatDate = useCallback((date: Date) => {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  }, []);

  return (
    <aside className="w-64 h-screen bg-gray-900 text-white p-4 flex flex-col">
      <button
        onClick={onNewChat}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded mb-4 transition-colors"
      >
        New Chat
      </button>

      <div className="flex-1 overflow-y-auto">
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => onSessionSelect(session.id)}
            className={`p-3 rounded-lg mb-2 cursor-pointer transition-colors ${
              currentSessionId === session.id
                ? 'bg-gray-700'
                : 'hover:bg-gray-800'
            }`}
          >
            <div className="font-medium truncate">
              {session.lastMessage || 'New Conversation'}
            </div>
            <div className="text-sm text-gray-400">
              {formatDate(session.createdAt)}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
};