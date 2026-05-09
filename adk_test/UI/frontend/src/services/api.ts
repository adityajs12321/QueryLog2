import { ChatSession, ChatMessage } from '@/types/chat';

const API_BASE_URL = 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export type StreamResponse = {
  type: 'connected' | 'response' | 'complete' | 'error';
  message?: string;
  content?: string;
};

export const chatApi = {
  getStreamingUrl(sessionId: string, query: string): string {
    const params = new URLSearchParams({
      session_id: sessionId,
      q: query,
    });
    return `${API_BASE_URL}/stream?${params.toString()}`;
  },

  async fetchSessions(): Promise<ChatSession[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          response.status,
          errorData?.message || 'Failed to fetch sessions'
        );
      }
      const data = await response.json();
      return data.map((session: any) => ({
        ...session,
        createdAt: new Date(session.createdAt),
        updatedAt: new Date(session.updatedAt),
      }));
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(500, 'Failed to fetch sessions');
    }
  },

  async createSession(): Promise<ChatSession> {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: 'adijs',
          appName: 'weather_app',
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          response.status,
          errorData?.message || 'Failed to create session'
        );
      }

      const data = await response.json();
      return {
        ...data,
        createdAt: new Date(data.createdAt),
        updatedAt: new Date(data.updatedAt),
      };
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(500, 'Failed to create session');
    }
  },

  async fetchSessionMessages(sessionId: string): Promise<ChatMessage[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          response.status,
          errorData?.message || 'Failed to fetch session messages'
        );
      }
      const data = await response.json();
      return data.map((message: any) => ({
        ...message,
        timestamp: new Date(message.timestamp),
      }));
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(500, 'Failed to fetch session messages');
    }
  },

  async sendMessage(sessionId: string, content: string): Promise<ChatMessage> {
    try {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          role: 'user',
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          response.status,
          errorData?.message || 'Failed to send message'
        );
      }
      
      const data = await response.json();
      return {
        ...data,
        timestamp: new Date(data.timestamp),
      };
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(500, 'Failed to send message');
    }
  },
};