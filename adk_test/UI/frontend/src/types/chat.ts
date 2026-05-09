export interface ChatSession {
  id: string;
  userId: string;
  appName: string;
  lastMessage?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatMessage {
  id: string;
  sessionId: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
}

export interface ChatHistoryState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  loading: boolean;
  error: string | null;
}