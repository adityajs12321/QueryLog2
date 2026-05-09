'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { chatApi, StreamResponse } from '@/services/api';
import { useChatHistory } from '@/context/ChatContext';

export const ChatInterface = () => {
  const { state } = useChatHistory();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !state.currentSessionId) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    // Close any existing stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Create a new EventSource for streaming
    const streamUrl = chatApi.getStreamingUrl(state.currentSessionId, input);
    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    let assistantMessage = '';

    eventSource.onmessage = (event) => {
      const data: StreamResponse = JSON.parse(event.data);
      
      switch (data.type) {
        case 'connected':
          console.log('Stream connected');
          break;
        case 'response':
          if (data.content) {
            assistantMessage = data.content;
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              if (lastMessage?.role === 'assistant') {
                lastMessage.content = assistantMessage;
                return newMessages;
              } else {
                return [...newMessages, { role: 'assistant', content: assistantMessage }];
              }
            });
          }
          break;
        case 'complete':
          eventSource.close();
          setIsStreaming(false);
          break;
        case 'error':
          console.error('Stream error:', data.message);
          setIsStreaming(false);
          eventSource.close();
          break;
      }
    };

    eventSource.onerror = () => {
      console.error('Stream connection error');
      setIsStreaming(false);
      eventSource.close();
    };
  };

  // Load messages when session changes
  useEffect(() => {
    const loadSessionMessages = async () => {
      if (state.currentSessionId) {
        try {
          const messages = await chatApi.fetchSessionMessages(state.currentSessionId);
          setMessages(messages.map(msg => ({
            role: msg.role,
            content: msg.content
          })));
        } catch (error) {
          console.error('Failed to load session messages:', error);
        }
      } else {
        setMessages([]); // Clear messages when no session is selected
      }
    };

    loadSessionMessages();

    // Clean up event source
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [state.currentSessionId]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`p-4 rounded-lg text-black ${
              msg.role === 'user' ? 'bg-green-300 ml-12' : 'bg-blue-300 mr-12'
            }`}
          >
            {msg.content}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 p-2 border rounded"
            disabled={isStreaming}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming || !state.currentSessionId}
            className="px-4 py-2 bg-blue-500 text-black rounded disabled:bg-black-100"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
};