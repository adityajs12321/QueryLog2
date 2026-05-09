'use client';

import React, { createContext, useContext, useReducer, ReactNode, useEffect } from 'react';
import { ChatHistoryState, ChatSession, ChatMessage } from '@/types/chat';
import { chatApi } from '@/services/api';

type ChatAction =
  | { type: 'SET_SESSIONS'; payload: ChatSession[] }
  | { type: 'SET_CURRENT_SESSION'; payload: string }
  | { type: 'ADD_SESSION'; payload: ChatSession }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

const initialState: ChatHistoryState = {
  sessions: [],
  currentSessionId: null,
  loading: false,
  error: null,
};

interface ChatContextType {
  state: ChatHistoryState;
  dispatch: React.Dispatch<ChatAction>;
  actions: {
    createSession: () => Promise<ChatSession>;
    sendMessage: (sessionId: string, content: string) => Promise<ChatMessage>;
  };
}

const ChatContext = createContext<ChatContextType | null>(null);

function chatReducer(state: ChatHistoryState, action: ChatAction): ChatHistoryState {
  switch (action.type) {
    case 'SET_SESSIONS':
      return {
        ...state,
        sessions: action.payload,
      };
    case 'SET_CURRENT_SESSION':
      return {
        ...state,
        currentSessionId: action.payload,
      };
    case 'ADD_SESSION':
      return {
        ...state,
        sessions: [action.payload, ...state.sessions],
        currentSessionId: action.payload.id,
      };
    case 'SET_LOADING':
      return {
        ...state,
        loading: action.payload,
      };
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
      };
    default:
      return state;
  }
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);

  useEffect(() => {
    // Fetch initial sessions when the component mounts
    const fetchSessions = async () => {
      try {
        dispatch({ type: 'SET_LOADING', payload: true });
        const sessions = await chatApi.fetchSessions();
        dispatch({ type: 'SET_SESSIONS', payload: sessions });
      } catch (error) {
        dispatch({ type: 'SET_ERROR', payload: 'Failed to fetch sessions' });
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    };

    fetchSessions();
  }, []);

  // Wrap the context value with additional methods
  const contextValue = {
    state,
    dispatch,
    actions: {
      createSession: async () => {
        try {
          dispatch({ type: 'SET_LOADING', payload: true });
          const newSession = await chatApi.createSession();
          dispatch({ type: 'ADD_SESSION', payload: newSession });
          return newSession;
        } catch (error) {
          dispatch({ type: 'SET_ERROR', payload: 'Failed to create session' });
          throw error;
        } finally {
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      },
      sendMessage: async (sessionId: string, content: string) => {
        try {
          const message = await chatApi.sendMessage(sessionId, content);
          return message;
        } catch (error) {
          dispatch({ type: 'SET_ERROR', payload: 'Failed to send message' });
          throw error;
        }
      }
    }
  };

  return (
    <ChatContext.Provider value={contextValue}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChatHistory() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatHistory must be used within a ChatProvider');
  }
  return context;
}