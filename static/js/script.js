document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatbox = document.getElementById('chatbox');
    const sendButton = document.getElementById('sendButton');
    const clearChatButton = document.getElementById('clearChatButton');
    const typingIndicator = document.getElementById('typing-indicator');

    const initialBotMessage = "Ciao! Sono pnAI002, il tuo assistente avanzato. Puoi farmi domande sui documenti caricati o sui dati nel database."; // Messaggio aggiornato

    function addInitialBotMessage() {
         addMessage(initialBotMessage, 'bot');
    }

    function addMessage(text, sender, isError = false) {
        const messageContainer = document.createElement('div');
        messageContainer.classList.add('message-container', sender);

        const avatar = document.createElement('div');
        avatar.classList.add('avatar', sender === 'user' ? 'user-avatar' : 'bot-avatar');
        const icon = document.createElement('i');
        icon.classList.add('fas', sender === 'user' ? 'fa-user' : 'fa-robot');
        avatar.appendChild(icon);

        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message');
        messageBubble.classList.add(sender === 'user' ? 'user-message' : 'bot-message');

        if (isError) {
            messageBubble.classList.add('error-message');
        }

        // Semplice sanitizzazione e gestione a capo
        // Per output contenente tabelle o formattazione complessa da SQL, questo potrebbe non essere sufficiente
        // Potresti aver bisogno di librerie come DOMPurify per output HTML più ricco e sicuro
        // o parsareMarkdown se il bot restituisce markdown.
        const safeText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        messageBubble.innerHTML = safeText.replace(/\n/g, '<br>');

        if (sender === 'user') {
            messageContainer.appendChild(messageBubble);
            messageContainer.appendChild(avatar);
        } else {
            messageContainer.appendChild(avatar);
            messageContainer.appendChild(messageBubble);
        }

        chatbox.appendChild(messageContainer);
        scrollToBottom();
    }

    function showTypingIndicator() {
        typingIndicator.classList.add('typing');
        scrollToBottom();
    }

    function hideTypingIndicator() {
        typingIndicator.classList.remove('typing');
    }

    function scrollToBottom() {
        setTimeout(() => {
             chatbox.scrollTop = chatbox.scrollHeight + 50; // Un po' di più per visibilità
        }, 50);
    }

    chatForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const question = userInput.value.trim();
        if (!question) return;

        addMessage(question, 'user');
        userInput.value = '';
        sendButton.disabled = true;
        userInput.disabled = true;
        clearChatButton.disabled = true;
        showTypingIndicator();

        try {
            const response = await fetch('/ask', { // L'endpoint è '/ask' come definito in app.py
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domanda: question }), // 'domanda' è la chiave attesa da app.py
            });

            hideTypingIndicator(); // Nascondi appena arriva la risposta (anche errore HTTP)

            if (!response.ok) {
                let errorMsg = `Errore Server: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.risposta || errorData.errore || errorMsg; // 'risposta' è la chiave usata da app.py per i messaggi
                } catch (e) { /* Ignora errore parsing JSON del corpo dell'errore */ }
                 throw new Error(errorMsg);
            }

            const data = await response.json();
            addMessage(data.risposta, 'bot'); // 'risposta' è la chiave usata da app.py per i messaggi di successo

        } catch (error) {
            hideTypingIndicator(); // Assicurati sia nascosto in caso di errore fetch
            console.error('Errore nella richiesta /ask:', error);
            addMessage(`Si è verificato un errore: ${error.message}`, 'bot', true);
        } finally {
            sendButton.disabled = false;
            userInput.disabled = false;
            clearChatButton.disabled = false;
            userInput.focus();
        }
    });

    clearChatButton.addEventListener('click', () => {
         chatbox.innerHTML = '';
         hideTypingIndicator();
         addInitialBotMessage();
         userInput.focus();
         console.log("Chat pulita.");
    });

    addInitialBotMessage();
    scrollToBottom();
});