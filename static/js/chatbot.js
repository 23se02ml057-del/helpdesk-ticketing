/**
 * AI Chatbot Widget
 * Handles chat functionality, loading states, and error handling
 */

(function() {
    'use strict';

    let conversationHistory = [];
    let isWaitingForResponse = false;

    const t = window.i18n ? function(key) { return i18n.t(key); } : function(key) { return key; };

    // DOM Elements
    const toggleBtn = document.getElementById('chatbot-toggle');
    const closeBtn = document.getElementById('chatbot-close');
    const clearBtn = document.getElementById('chatbot-clear');
    const chatWindow = document.getElementById('chatbot-window');
    const messagesContainer = document.getElementById('chatbot-messages');
    const loadingIndicator = document.getElementById('chatbot-loading');
    const chatForm = document.getElementById('chatbot-form');
    const chatInput = document.getElementById('chatbot-input');

    // Initialize
    function init() {
        if (!toggleBtn || !chatWindow) return;

        toggleBtn.addEventListener('click', toggleChat);
        closeBtn.addEventListener('click', closeChat);
        clearBtn.addEventListener('click', clearChat);
        chatForm.addEventListener('submit', handleSubmit);

        // Load chat history from server
        loadChatHistory();

        // Focus input when chat opens
        toggleBtn.addEventListener('click', function() {
            setTimeout(() => chatInput.focus(), 300);
        });
    }

    // Toggle chat window
    function toggleChat() {
        const isOpen = chatWindow.classList.contains('open');
        if (isOpen) {
            closeChat();
        } else {
            openChat();
        }
    }

    // Open chat window
    function openChat() {
        chatWindow.classList.add('open');
        toggleBtn.classList.add('hidden');
        chatInput.focus();
    }

    // Close chat window
    function closeChat() {
        chatWindow.classList.remove('open');
        toggleBtn.classList.remove('hidden');
    }

    // Clear chat history
    function clearChat() {
        if (!confirm(t('clear_chat_history'))) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const headers = { 'Content-Type': 'application/json' };
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        fetch('/api/chatbot/clear', {
            method: 'POST',
            headers: headers,
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                messagesContainer.innerHTML = `
                    <div class="chatbot-message chatbot-message-ai">
                        <div class="chatbot-avatar">
                            <i class="fa-solid fa-robot"></i>
                        </div>
                        <div class="chatbot-bubble">
                            ${t('chat_history_cleared')}
                        </div>
                    </div>
                `;
                conversationHistory = [];
            }
        })
        .catch(error => {
            console.error('Error clearing chat:', error);
        });
    }

    // Load chat history from server
    function loadChatHistory() {
        fetch('/api/chatbot/history')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.history.length > 0) {
                    messagesContainer.innerHTML = '';
                    data.history.forEach(msg => {
                        addMessageToUI(msg.role, msg.message, false);
                        conversationHistory.push({
                            role: msg.role,
                            content: msg.message
                        });
                    });
                    scrollToBottom();
                }
            })
            .catch(error => {
                console.error('Error loading chat history:', error);
            });
    }

    // Handle form submit
    function handleSubmit(e) {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message || isWaitingForResponse) return;

        // Add user message to UI
        addMessageToUI('user', message);
        conversationHistory.push({ role: 'user', content: message });

        // Clear input
        chatInput.value = '';

        // Show loading
        showLoading();

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const headers = {
            'Content-Type': 'application/json',
        };
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        // Send to server
        fetch('/api/chatbot/send', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                message: message,
                history: conversationHistory.slice(0, -1)
            })
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();

            if (data.success) {
                addMessageToUI('ai', data.response);
                conversationHistory.push({ role: 'assistant', content: data.response });
            } else {
                addMessageToUI('ai', t('error_prefix') + data.error, true);
            }

            scrollToBottom();
        })
        .catch(error => {
            hideLoading();
            addMessageToUI('ai', t('network_error'), true);
            scrollToBottom();
            console.error('Chat error:', error);
        });
    }

    // Add message to UI
    function addMessageToUI(role, text, isError) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chatbot-message ' + (role === 'user' ? 'chatbot-message-user' : 'chatbot-message-ai');

        const avatar = document.createElement('div');
        avatar.className = 'chatbot-avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';

        const bubble = document.createElement('div');
        bubble.className = 'chatbot-bubble';
        if (isError) {
            bubble.classList.add('chatbot-error');
        }
        bubble.textContent = text;

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(bubble);
        messagesContainer.appendChild(messageDiv);
    }

    // Show loading indicator
    function showLoading() {
        isWaitingForResponse = true;
        loadingIndicator.style.display = 'flex';
        chatInput.disabled = true;
        scrollToBottom();
    }

    // Hide loading indicator
    function hideLoading() {
        isWaitingForResponse = false;
        loadingIndicator.style.display = 'none';
        chatInput.disabled = false;
        chatInput.focus();
    }

    // Scroll to bottom of messages
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
