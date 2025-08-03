import { useState, useRef, useEffect } from 'react';
import { SectionHeader } from './SectionHeader';

interface ChatMessage {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
}

export const ChatView = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  // Load chat history on component mount
  useEffect(() => {
    loadChatHistory();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadChatHistory = async () => {
    try {
      setLoadingHistory(true);
      const response = await fetch('http://localhost:8000/api/chat/history');
      if (response.ok) {
        const data = await response.json();
        const historyMessages: ChatMessage[] = [];
        
        // Convert API response to chat messages
        data.messages.forEach((item: any) => {
          // Add user message
          if (item.user_message) {
            historyMessages.push({
              id: `user-${item.id}`,
              content: item.user_message,
              isUser: true,
              timestamp: new Date(item.timestamp)
            });
          }
          
          // Add assistant response
          if (item.assistant_response) {
            historyMessages.push({
              id: `assistant-${item.id}`,
              content: item.assistant_response,
              isUser: false,
              timestamp: new Date(item.timestamp)
            });
          }
        });
        
        setMessages(historyMessages);
      } else {
        console.error('Failed to load chat history:', response.statusText);
        // Add welcome message if no history available
        setMessages([{
          id: 'welcome',
          content: 'Welcome to your personal Lifeboard assistant! I can help you explore your digital history, find connections, and plan your next steps. What would you like to know about your data?',
          isUser: false,
          timestamp: new Date()
        }]);
      }
    } catch (error) {
      console.error('Error loading chat history:', error);
      // Add welcome message on error
      setMessages([{
        id: 'welcome',
        content: 'Welcome to your personal Lifeboard assistant! I can help you explore your digital history, find connections, and plan your next steps. What would you like to know about your data?',
        isUser: false,
        timestamp: new Date()
      }]);
    } finally {
      setLoadingHistory(false);
    }
  };
  
  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content: inputValue.trim(),
      isUser: true,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    
    try {
      // Send message to API
      const response = await fetch('http://localhost:8000/api/chat/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userMessage.content }),
      });
      
      if (response.ok) {
        const data = await response.json();
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          content: data.response,
          isUser: false,
          timestamp: new Date(data.timestamp)
        };
        
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        throw new Error(`API request failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        content: 'Sorry, I encountered an error while processing your message. Please try again.',
        isUser: false,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };
  
  const sampleQuestions = [
    "What conversations did I have yesterday?",
    "Show me my most active days this month",
    "What topics do I discuss most often?",
    "Help me plan my week based on my patterns"
  ];
  
  return (
    <div className="chat-view">
      <SectionHeader 
        title="Personal AI Assistant"
        subtitle="Chat with your digital life history"
        accentColor="border-social-accent"
      />
      
      <div className="chat-container">
        {/* Chat Messages */}
        <div className="card chat-messages-container">
          <div className="chat-messages">
            {loadingHistory && (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                Loading chat history...
              </div>
            )}
            
            {!loadingHistory && messages.map((message) => (
              <div
                key={message.id}
                className={`chat-message ${message.isUser ? 'user' : 'assistant'}`}
              >
                <div className="chat-message-content">
                  <div className="message-header">
                    <span className="message-sender">
                      {message.isUser ? 'You' : 'Lifeboard AI'}
                    </span>
                    <span className="message-time">
                      {formatTime(message.timestamp)}
                    </span>
                  </div>
                  <div className="message-text">
                    {message.content}
                  </div>
                </div>
              </div>
            ))}
            
            {!loadingHistory && isLoading && (
              <div className="chat-message assistant">
                <div className="chat-message-content">
                  <div className="message-header">
                    <span className="message-sender">Lifeboard AI</span>
                    <span className="message-time">thinking...</span>
                  </div>
                  <div className="message-text">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>
        
        {/* Sample Questions */}
        {!loadingHistory && messages.length === 0 && (
          <div className="mt-4">
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Try asking me...</h3>
              </div>
              <div className="card-content">
                <div className="sample-questions">
                  {sampleQuestions.map((question, index) => (
                    <button
                      key={index}
                      onClick={() => setInputValue(question)}
                      className="sample-question"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Chat Input */}
        <div className="chat-input-container">
          <div className="card">
            <div className="card-content" style={{ padding: '1rem' }}>
              <div className="chat-input-wrapper">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask me about your digital life..."
                  className="chat-input"
                  rows={3}
                  disabled={isLoading}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || isLoading}
                  className="button button-primary chat-send-button"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};