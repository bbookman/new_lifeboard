/**
 * Chat functionality for the Lifeboard simple UI
 */

const Chat = {
    // Chat state
    messages: [],
    isLoading: false,
    
    // DOM elements
    messagesContainer: null,
    chatInput: null,
    sendButton: null,
    
    // Initialize chat
    init() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');
        
        if (!this.messagesContainer || !this.chatInput || !this.sendButton) {
            console.error('Chat: Required elements not found');
            return;
        }
        
        this.bindEvents();
        this.loadChatHistory();
    },
    
    // Bind event listeners
    bindEvents() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter key in chat input
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Sample question clicks
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('sample-question')) {
                const question = e.target.dataset.question;
                if (question) {
                    this.chatInput.value = question;
                    this.sendMessage();
                }
            }
        });
        
        // Auto-resize textarea
        this.chatInput.addEventListener('input', () => {
            this.chatInput.style.height = 'auto';
            this.chatInput.style.height = this.chatInput.scrollHeight + 'px';
        });
    },
    
    // Load chat history from API
    async loadChatHistory() {
        try {
            const response = await API.chat.getHistory();
            
            if (response.messages && response.messages.length > 0) {
                // Clear intro message
                this.messagesContainer.innerHTML = '';
                
                // Add each message pair from history
                response.messages.forEach(item => {
                    if (item.user_message) {
                        this.addMessage(item.user_message, true, new Date(item.timestamp));
                    }
                    if (item.assistant_response) {
                        this.addMessage(item.assistant_response, false, new Date(item.timestamp));
                    }
                });
                
                this.scrollToBottom();
            }
        } catch (error) {
            console.error('Failed to load chat history:', error);
        }
    },
    
    // Send a message
    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message || this.isLoading) {
            return;
        }
        
        // Clear input and disable
        this.chatInput.value = '';
        this.chatInput.style.height = 'auto';
        this.setLoading(true);
        
        // Hide intro if it exists
        const intro = this.messagesContainer.querySelector('.chat-intro');
        if (intro) {
            intro.style.display = 'none';
        }
        
        // Add user message
        this.addMessage(message, true);
        
        // Add typing indicator
        this.addTypingIndicator();
        
        try {
            // Send to API
            const response = await API.chat.send(message);
            
            // Remove typing indicator
            this.removeTypingIndicator();
            
            // Add assistant response
            if (response.response) {
                this.addMessage(response.response, false);
            } else {
                this.addMessage('Sorry, I didn\'t receive a proper response.', false);
            }
            
        } catch (error) {
            console.error('Failed to send message:', error);
            
            // Remove typing indicator
            this.removeTypingIndicator();
            
            // Add error message
            this.addMessage(`Sorry, I encountered an error: ${error.message}`, false);
        } finally {
            this.setLoading(false);
        }
    },
    
    // Add a message to the chat
    addMessage(content, isUser = false, timestamp = new Date()) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user' : 'assistant'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'chat-message-content';
        
        const messageHeader = document.createElement('div');
        messageHeader.className = 'message-header';
        messageHeader.innerHTML = `
            <span class="message-sender">${isUser ? 'You' : 'Assistant'}</span>
            <span class="message-time">${Utils.formatTimestamp(timestamp)}</span>
        `;
        
        const messageText = document.createElement('div');
        messageText.className = 'message-text';
        messageText.innerHTML = Utils.simpleMarkdown(Utils.escapeHtml(content));
        
        messageContent.appendChild(messageHeader);
        messageContent.appendChild(messageText);
        messageDiv.appendChild(messageContent);
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    },
    
    // Add typing indicator
    addTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-message assistant';
        typingDiv.id = 'typing-indicator';
        
        const typingContent = document.createElement('div');
        typingContent.className = 'chat-message-content';
        
        const typingAnimation = document.createElement('div');
        typingAnimation.className = 'typing-indicator';
        typingAnimation.innerHTML = '<span></span><span></span><span></span>';
        
        typingContent.appendChild(typingAnimation);
        typingDiv.appendChild(typingContent);
        
        this.messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    },
    
    // Remove typing indicator
    removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    },
    
    // Scroll to bottom of messages
    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    },
    
    // Set loading state
    setLoading(loading) {
        this.isLoading = loading;
        this.sendButton.disabled = loading;
        this.chatInput.disabled = loading;
        
        if (loading) {
            this.sendButton.textContent = 'Sending...';
            this.sendButton.classList.add('loading');
        } else {
            this.sendButton.textContent = 'Send';
            this.sendButton.classList.remove('loading');
            this.chatInput.focus();
        }
    },
    
    // Clear chat history
    async clearHistory() {
        if (!confirm('Are you sure you want to clear all chat history?')) {
            return;
        }
        
        try {
            await API.chat.clearHistory();
            
            // Clear UI
            this.messagesContainer.innerHTML = `
                <div class="chat-intro">
                    <p class="text-muted text-center">Start a conversation to search through your personal data</p>
                    
                    <!-- Sample Questions -->
                    <div class="sample-questions mt-4">
                        <h4 class="text-center mb-4">Try asking:</h4>
                        <button class="sample-question" data-question="What did I discuss about work this week?">
                            What did I discuss about work this week?
                        </button>
                        <button class="sample-question" data-question="Show me conversations about travel plans">
                            Show me conversations about travel plans
                        </button>
                        <button class="sample-question" data-question="What were the main topics in my recent calls?">
                            What were the main topics in my recent calls?
                        </button>
                    </div>
                </div>
            `;
            
            this.messages = [];
            
        } catch (error) {
            console.error('Failed to clear chat history:', error);
            alert('Failed to clear chat history. Please try again.');
        }
    }
};

// Export for use in other modules
window.Chat = Chat;