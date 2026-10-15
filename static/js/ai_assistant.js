document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chatMessages');
    const userMessageInput = document.getElementById('userMessage');
    const typingIndicator = document.getElementById('typingIndicator');
    let conversationHistory = [];
    let isFirstMessage = true;

    const t = window.i18n ? function(key) { return i18n.t(key); } : function(key) { return key; };

    window.sendMessage = async function() {
        const message = userMessageInput.value.trim();
        if (!message) return;

        if (isFirstMessage) {
            document.getElementById('welcomeMessage').style.display = 'none';
            isFirstMessage = false;
        }

        addMessage('user', message);
        conversationHistory.push({ role: 'user', content: message });
        userMessageInput.value = '';
        showTyping();

        try {
            const response = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    history: conversationHistory.slice(0, -1)
                })
            });

            const data = await response.json();
            hideTyping();

            if (data.success) {
                addMessage('ai', data.response);
                conversationHistory.push({ role: 'assistant', content: data.response });
            } else {
                addMessage('ai', t('error_prefix') + data.error);
            }
        } catch (error) {
            hideTyping();
            addMessage('ai', t('network_error'));
        }
    };

    window.sendQuickMessage = function(text) {
        userMessageInput.value = text;
        sendMessage();
    };

    function addMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ' + sender;

        const label = document.createElement('div');
        label.className = 'message-label';
        label.textContent = sender === 'user' ? t('you') : t('ai_assistant');

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = text;

        messageDiv.appendChild(label);
        messageDiv.appendChild(bubble);
        chatMessages.insertBefore(messageDiv, typingIndicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTyping() {
        typingIndicator.classList.add('active');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function hideTyping() {
        typingIndicator.classList.remove('active');
    }

    checkAIHealth();
});

async function checkAIHealth() {
    const t = window.i18n ? function(key) { return i18n.t(key); } : function(key) { return key; };

    try {
        const response = await fetch('/api/ai/health');
        const data = await response.json();
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        const model = document.getElementById('modelInfo');

        if (data.success) {
            dot.classList.remove('error', 'checking');
            text.textContent = t('ai_service_active');
            if (data.model) model.textContent = t('model_colon') + data.model;
        } else {
            dot.classList.add('error');
            text.textContent = data.message || t('ai_service_error');
        }
    } catch (error) {
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        dot.classList.add('error');
        text.textContent = t('cannot_connect_ai');
    }
}
