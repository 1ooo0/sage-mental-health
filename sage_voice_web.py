"""
Sage - Voice Mental Health Companion (Web Version)
==================================================
Users speak in their browser. Sage listens, understands, and speaks back.

SETUP:
    pip3 install fastapi uvicorn python-multipart requests

RUN:
    python sage_voice_web.py

Then open: http://localhost:8000
"""

import os
import json
import tempfile
import requests
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
import uvicorn

# =============================================================================
# CONFIGURATION - Read API keys from environment variables (set in Render)
# =============================================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Use DeepSeek if available, otherwise fallback to Groq
if DEEPSEEK_API_KEY:
    CURRENT_MODEL = "deepseek-chat"
    API_BASE = "https://api.deepseek.com/v1"
    USE_DEEPSEEK = True
elif GROQ_API_KEY:
    CURRENT_MODEL = "openai/gpt-oss-20b"
    API_BASE = "https://api.groq.com/openai/v1"
    USE_DEEPSEEK = False
else:
    CURRENT_MODEL = None
    API_BASE = None
    USE_DEEPSEEK = False

AGENT_NAME = "Sage"

# Crisis resources
CRISIS_KEYWORDS = [
    "kill myself", "suicide", "suicidal", "end my life", "want to die",
    "hurt myself", "self-harm", "cutting", "overdose", "not worth living",
    "better off dead", "end it all", "can't go on", "no reason to live"
]

CRISIS_RESPONSE = """I'm really concerned about what you just shared. Your life matters, and there are people who want to help right now.

Please reach out immediately:
• US: Call or text 988 (Suicide & Crisis Lifeline)
• UK: Call Samaritans at 116 123
• India: Call Kiran Helpline at 1800-599-0019
• Anywhere: Visit findahelpline.com

If you're in immediate danger, please call your local emergency number.

You don't have to go through this alone."""

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(title="Sage - Voice Mental Health Companion")

# =============================================================================
# HTML PAGE WITH VOICE INTERFACE
# =============================================================================

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sage - Voice Mental Health Companion</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #e8f5e9 0%, #e3f2fd 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            width: 100%;
            background: white;
            border-radius: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2d6a4f 0%, #40916c 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 28px; margin-bottom: 8px; }
        .header p { opacity: 0.9; font-size: 14px; }
        .status-bar {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            gap: 15px;
        }
        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #666;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ccc;
        }
        .status-dot.active { background: #2d6a4f; animation: pulse 2s infinite; }
        .status-dot.speaking { background: #40916c; animation: pulse 1s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .chat-area {
            height: 350px;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .message {
            max-width: 80%;
            padding: 14px 18px;
            border-radius: 20px;
            font-size: 15px;
            line-height: 1.5;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.sage {
            background: #e8f5e9;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .message.user {
            background: #d4edda;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .message.crisis {
            background: #fff3cd;
            border: 2px solid #ffc107;
            align-self: center;
            max-width: 95%;
        }
        .controls {
            padding: 20px;
            background: #f8f9fa;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .mic-button {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #2d6a4f 0%, #40916c 100%);
            color: white;
            font-size: 32px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(45, 106, 79, 0.3);
        }
        .mic-button:hover { transform: scale(1.05); }
        .mic-button.recording {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            animation: pulse 1s infinite;
        }
        .text-input-area {
            display: flex;
            gap: 10px;
        }
        .text-input {
            flex: 1;
            padding: 14px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 15px;
            outline: none;
        }
        .text-input:focus { border-color: #2d6a4f; }
        .send-btn {
            padding: 14px 24px;
            background: #2d6a4f;
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 15px;
            cursor: pointer;
        }
        .send-btn:hover { background: #1b4332; }
        .disclaimer {
            text-align: center;
            padding: 15px;
            font-size: 12px;
            color: #888;
            background: #f8f9fa;
        }
        .typing {
            display: flex;
            gap: 5px;
            padding: 10px 15px;
            align-self: flex-start;
        }
        .typing-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #2d6a4f;
            animation: typingBounce 1.4s infinite;
        }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingBounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }
        .speak-btn {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 18px;
            margin-left: 8px;
            opacity: 0.6;
        }
        .speak-btn:hover { opacity: 1; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Sage</h1>
            <p>Your Voice Mental Health Companion</p>
        </div>
        <div class="status-bar">
            <div class="status">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Ready to listen</span>
            </div>
        </div>
        <div class="chat-area" id="chatArea">
            <div class="message sage">Hello, I'm Sage. I'm here to listen and support you. How are you feeling today? You can speak or type.</div>
        </div>
        <div class="controls">
            <button class="mic-button" id="micBtn" onclick="toggleRecording()">🎙️</button>
            <div class="text-input-area">
                <input type="text" class="text-input" id="textInput" placeholder="Or type how you're feeling..." onkeypress="if(event.key==='Enter')sendText()">
                <button class="send-btn" onclick="sendText()">Send</button>
            </div>
        </div>
        <div class="disclaimer">
            I'm an AI companion, not a therapist. For crisis support, call 988 (US) or visit findahelpline.com
        </div>
    </div>
    <script>
        let isRecording = false;
        let mediaRecorder = null;
        let audioChunks = [];
        const micBtn = document.getElementById('micBtn');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const chatArea = document.getElementById('chatArea');
        const textInput = document.getElementById('textInput');

        function setStatus(state, text) {
            statusDot.className = 'status-dot ' + state;
            statusText.textContent = text;
        }

        function addMessage(text, sender, msgId) {
            const div = document.createElement('div');
            div.className = 'message ' + sender;
            div.id = msgId || '';
            const textSpan = document.createElement('span');
            textSpan.textContent = text;
            div.appendChild(textSpan);
            if (sender === 'sage' || sender === 'crisis') {
                const speakBtn = document.createElement('button');
                speakBtn.className = 'speak-btn';
                speakBtn.textContent = '🔊';
                speakBtn.onclick = () => speakMessage(text);
                div.appendChild(speakBtn);
            }
            chatArea.appendChild(div);
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        function addTyping() {
            const div = document.createElement('div');
            div.className = 'typing';
            div.id = 'typingIndicator';
            div.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
            chatArea.appendChild(div);
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        function removeTyping() {
            const typing = document.getElementById('typingIndicator');
            if (typing) typing.remove();
        }

        function speakMessage(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 0.9;
                utterance.pitch = 1;
                utterance.volume = 1;
                const voices = window.speechSynthesis.getVoices();
                const preferredVoices = ['Samantha', 'Google US English', 'Microsoft Zira'];
                for (const name of preferredVoices) {
                    const voice = voices.find(v => v.name.includes(name));
                    if (voice) { utterance.voice = voice; break; }
                }
                setStatus('speaking', 'Sage is speaking...');
                utterance.onend = () => { setStatus('', 'Ready to listen'); };
                window.speechSynthesis.speak(utterance);
            } else {
                alert('Text-to-speech not supported in your browser');
            }
        }

        async function toggleRecording() {
            if (isRecording) { stopRecording(); } else { startRecording(); }
        }

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                mediaRecorder.ondataavailable = (e) => { audioChunks.push(e.data); };
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    await sendAudio(audioBlob);
                };
                mediaRecorder.start();
                isRecording = true;
                micBtn.classList.add('recording');
                micBtn.textContent = '⏹️';
                setStatus('active', 'Listening... speak now');
            } catch (err) {
                alert('Could not access microphone. Please type instead.');
                setStatus('error', 'Microphone unavailable');
            }
        }

        function stopRecording() {
            if (mediaRecorder && isRecording) {
                mediaRecorder.stop();
                isRecording = false;
                micBtn.classList.remove('recording');
                micBtn.textContent = '🎙️';
                setStatus('active', 'Processing...');
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
        }

        async function sendAudio(audioBlob) {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');
            addTyping();
            try {
                const response = await fetch('/voice-chat', { method: 'POST', body: formData });
                const data = await response.json();
                removeTyping();
                const msgId = 'msg-' + Date.now();
                addMessage(data.reply, data.crisis ? 'crisis' : 'sage', msgId);
                if (!data.crisis) { speakMessage(data.reply); }
                setStatus('', 'Ready to listen');
            } catch (err) {
                removeTyping();
                addMessage("I'm sorry, I had trouble understanding. Could you try again?", 'sage');
                setStatus('error', 'Error occurred');
            }
        }

        async function sendText() {
            const message = textInput.value.trim();
            if (!message) return;
            addMessage(message, 'user');
            textInput.value = '';
            addTyping();
            setStatus('active', 'Sage is thinking...');
            try {
                const response = await fetch('/text-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
                const data = await response.json();
                removeTyping();
                const msgId = 'msg-' + Date.now();
                addMessage(data.reply, data.crisis ? 'crisis' : 'sage', msgId);
                if (!data.crisis) { speakMessage(data.reply); }
                setStatus('', 'Ready to listen');
            } catch (err) {
                removeTyping();
                addMessage("I'm sorry, I had trouble responding. Could you try again?", 'sage');
                setStatus('error', 'Error occurred');
            }
        }

        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = () => {
                console.log('Voices loaded:', window.speechSynthesis.getVoices().length);
            };
        }
    </script>
</body>
</html>
"""

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.post("/text-chat")
async def text_chat(message: str = Form(...)):
    """Handle text messages."""
    return process_message(message)

@app.post("/voice-chat")
async def voice_chat(audio: UploadFile = File(...)):
    """Handle voice messages."""
    temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    content = await audio.read()
    with open(temp_audio.name, "wb") as f:
        f.write(content)

    try:
        # Transcribe with Groq Whisper (free, no key needed for this part if using DeepSeek)
        # Actually we need Groq key for Whisper, or use DeepSeek's audio API
        # For now, let's use a simple approach - return text input fallback
        # In production, you'd use DeepSeek's audio API or keep Groq for Whisper

        # Try Groq Whisper first
        if GROQ_API_KEY:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            with open(temp_audio.name, 'rb') as f:
                files = {
                    'file': ('audio.wav', f, 'audio/wav'),
                    'model': (None, 'whisper-large-v3')
                }
                response = requests.post(url, headers=headers, files=files, timeout=30)

            os.unlink(temp_audio.name)

            if response.status_code == 200:
                transcript = response.json().get('text', '').strip()
                return process_message(transcript, is_voice=True)

        os.unlink(temp_audio.name)
        return {"reply": "Voice transcription requires a Groq API key. Please type your message instead.", "crisis": False}

    except Exception as e:
        try:
            os.unlink(temp_audio.name)
        except:
            pass
        return {"reply": "I had trouble processing your voice. Could you try typing?", "crisis": False}

# =============================================================================
# MESSAGE PROCESSING
# =============================================================================

def process_message(user_text, is_voice=False):
    """Process user message with DeepSeek or Groq AI."""

    # Check for crisis
    text_lower = user_text.lower()
    is_crisis = any(keyword in text_lower for keyword in CRISIS_KEYWORDS)

    if is_crisis:
        return {"reply": CRISIS_RESPONSE, "crisis": True}

    # If no API key configured, use built-in responses
    if not CURRENT_MODEL:
        return built_in_brain(user_text)

    # Get AI response
    try:
        url = f"{API_BASE}/chat/completions"

        if USE_DEEPSEEK:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
        else:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }

        system_prompt = """You are Sage, a compassionate mental health companion. You are NOT a therapist or doctor.
Be warm, empathetic, and non-judgmental. Validate feelings before offering suggestions.
Keep responses concise (3-5 sentences). Suggest one practical coping technique when relevant."""

        data = {
            "model": CURRENT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.6,
            "max_tokens": 250
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        reply = result['choices'][0]['message']['content']

        return {"reply": reply, "crisis": False}

    except Exception as e:
        return built_in_brain(user_text)

# =============================================================================
# BUILT-IN BRAIN (Fallback)
# =============================================================================

def built_in_brain(user_text):
    """Built-in responses when no AI API is available."""
    text_lower = user_text.lower()

    if any(w in text_lower for w in ["sad", "depressed", "down", "unhappy"]):
        return {"reply": "I'm sorry you're feeling this way. It's okay to not be okay. Try the 5-4-3-2-1 grounding technique: name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, and 1 you taste.", "crisis": False}

    if any(w in text_lower for w in ["anxious", "anxiety", "worried", "nervous", "stress"]):
        return {"reply": "Anxiety can feel overwhelming. Let's try box breathing: breathe in for 4 seconds, hold for 4, out for 4, hold for 4. Repeat 5 times. This activates your calm response.", "crisis": False}

    if any(w in text_lower for w in ["hello", "hi", "hey"]):
        return {"reply": "Hello! I'm Sage. How can I support you today?", "crisis": False}

    if "time" in text_lower:
        return {"reply": f"The current time is {datetime.now().strftime('%I:%M %p')}.", "crisis": False}

    if "joke" in text_lower:
        return {"reply": "Why don't scientists trust atoms? Because they make up everything!", "crisis": False}

    return {"reply": "I'm here for you. Could you tell me more about what you're feeling?", "crisis": False}

# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Sage - Voice Mental Health Companion (Web)")
    print("=" * 70)
    print("Open your browser and go to: http://localhost:8000")
    print("Press Ctrl+C to stop")
    print("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=8000)