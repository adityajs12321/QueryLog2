'use client';

import { useChatHistory } from '@/context/ChatContext';
import { ChatSidebar } from './ChatSidebar';
import { useCallback } from 'react';

export const ChatContainer = ({ children }: { children: React.ReactNode }) => {
  const { state, dispatch, actions } = useChatHistory();

  const handleSessionSelect = useCallback((sessionId: string) => {
    dispatch({ type: 'SET_CURRENT_SESSION', payload: sessionId });
  }, [dispatch]);

  const handleNewChat = useCallback(async () => {
    try {
      await actions.createSession();
    } catch (error) {
      console.error('Failed to create new chat session:', error);
    }
  }, [actions]);

  return (
    <div className="flex h-screen">
      <ChatSidebar
        sessions={state.sessions}
        currentSessionId={state.currentSessionId}
        onSessionSelect={handleSessionSelect}
        onNewChat={handleNewChat}
      />
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
};