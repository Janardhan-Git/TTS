import streamlit as st 
import edge_tts
import asyncio
import os
import uuid
import time
import re
from streamlit import markdown
import streamlit.components.v1 as components  
from streamlit_lottie import st_lottie
import json
import docx

# Define the loader function
        
def load_lottie(filepath):
    with open(filepath, "r") as f:
           return json.load(f)
            
# Set page title
st.set_page_config(page_title="🗣️ Text to Speech with Edge-TTS", layout="centered")
st.title("🗣️ Text-to-Speech App with Edge-TTS")

# Load and show animation
lottie_animation = load_lottie("assets/animation.json")
st_lottie(lottie_animation, height=150, key="header_animation")

st.markdown("""
    <style>
    .main {
        background-color: #f9f9f9;
    }
    h1 {
        color: #3c3c3c;
        font-family: 'Segoe UI', sans-serif;
    }
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        height: 3em;
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# Voice options
voice_options = {
    "English - Female": "en-US-JennyNeural",
    "English - Male": "en-US-GuyNeural",
    "Telugu - Male": "te-IN-MohanNeural",
    "Telugu - Female": "te-IN-ShrutiNeural"
}

# Speed options
speed_map = {
    "Fast": "+25%",
    "Normal": "+0%",
    "Slow": "-25%"
}

rate_map = {
    "Fast": 1.25,
    "Normal": 1.0,
    "Slow": 0.75
}

# Sidebar options
st.sidebar.header("🔧 Settings")
voice = st.sidebar.selectbox("Select Voice", list(voice_options.keys()))
rate = st.sidebar.selectbox("Select Speed", list(speed_map.keys()))

# Pronunciation Editor
st.sidebar.subheader("🗣️ Pronunciation Editor (Optional)")
custom_word = st.sidebar.text_input("Word to replace (e.g., OpenAI)")
custom_pronunciation = st.sidebar.text_input("SSML (e.g., <phoneme alphabet='ipa' ph='ˈəʊ.pən.aɪ'>OpenAI</phoneme>)")

# Text input or file upload
def extract_text_from_file(uploaded_file, file_type):
    if file_type == "txt":
        return uploaded_file.read().decode("utf-8")

    elif file_type == "pdf":
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

    elif file_type == "docx":
        doc = docx.Document(uploaded_file)
        return "\n".join([para.text for para in doc.paragraphs])

    return ""

# --- Input section ---
input_mode = st.radio("Choose Input Type", ["Type Text", "Upload File"])
user_text = ""

if input_mode == "Type Text":
    user_text = st.text_area("Enter Text to Convert to Speech", height=200)

else:
    uploaded_file = st.file_uploader("Upload a text file", type=["txt", "pdf", "docx"])
    if uploaded_file is not None:
        file_type = uploaded_file.name.split(".")[-1].lower()
        user_text = extract_text_from_file(uploaded_file, file_type)
        st.text_area("📄 Preview Uploaded Text", user_text, height=200)

# Clean text to avoid reading symbols like ###
def clean_text(text):
    return re.sub(r'[#!*\-]+', '', text)

# Generate speech file using Edge TTS
async def generate_speech(text, voice, rate, output_file):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(output_file)

# Convert text to speech and allow download
if user_text:
    cleaned_text = clean_text(user_text)
    st.subheader("📄 Preview Text")
    paragraphs = [para.strip() for para in cleaned_text.split('\n') if para.strip() != '']
    for para in paragraphs:
        st.markdown(f"<p style='margin-bottom:15px'>{para}</p>", unsafe_allow_html=True)

    if st.button("🎧 Convert to Speech"):
        output_file = f"{uuid.uuid4().hex}.mp3"
        with st.spinner("Generating audio... Please wait ⏳"):
            asyncio.run(generate_speech(cleaned_text, voice_options[voice], speed_map[rate], output_file))
        st.success("✅ Conversion Complete!")
        audio_file = open(output_file, "rb")
        audio_bytes = audio_file.read()
        st.audio(audio_bytes, format="audio/mp3")
        st.download_button(label="📥 Download Audio", data=audio_bytes, file_name="converted_speech.mp3", mime="audio/mp3")
        audio_file.close()
        os.remove(output_file)

# 🔊 Read Aloud in Browser with Highlighting
if st.button("🗣️ Read Aloud in Browser"):
    escaped_text = cleaned_text.replace("\"", "\\\"").replace('\n', ' ')
    html_code = f"""
    <script>
    const text = `{escaped_text}`;
    const utterance = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.onvoiceschanged = () => {{
        let allVoices = speechSynthesis.getVoices();
        const preferredVoiceName = `{voice_options[voice]}`;
        const matchedVoice = allVoices.find(v => v.name === preferredVoiceName);
        if (matchedVoice) utterance.voice = matchedVoice;
        utterance.rate = {rate_map[rate]};

        const container = document.getElementById("highlighted-text");
        const words = text.split(/\s+/);
        container.innerHTML = words.map(w => `<span class='word'>${{w}}</span>`).join(" ");
        const spans = container.querySelectorAll(".word");
        let wordIndex = 0;

        utterance.onboundary = (event) => {{
            if (event.name === 'word') {{
                spans.forEach(span => span.style.background = '');
                if (spans[wordIndex]) {{
                    spans[wordIndex].style.background = 'yellow';
                    wordIndex++;
                }}
            }}
        }};

        speechSynthesis.speak(utterance);
    }};
    </script>
    <style>
    #highlighted-text {{ font-size: 18px; line-height: 1.6; margin-top: 10px; }}
    .word {{ padding: 2px; margin-right: 2px; }}
    </style>
    <div id="highlighted-text"></div>
    """
    components.html(html_code)

# 💬 Click sentence to read it aloud with highlight and pause/resume support
if user_text:
    escaped_sentences = re.split(r'(?<=[.!?]) +', cleaned_text.replace('\n', ' '))
    js_sentence_click = """
    <div id="sentence-text" style="line-height: 2; padding: 10px;">
    """
    for sentence in escaped_sentences:
        clean_sent = sentence.strip().replace('"', '\"')
        js_sentence_click += f"<span class='sentence' onclick='speakSentence(\"{clean_sent}\")' style='cursor:pointer; display:block; padding:5px; margin-bottom:8px; border:1px solid #ccc; border-radius:6px;'>" + sentence + "</span>"
    js_sentence_click += "</div>"

    js_sentence_click += f"""
    <script>
    let synth = window.speechSynthesis;
    let sentenceUtterance = null;
    let paused = false;

    function speakSentence(sentence) {{
        if (sentenceUtterance && synth.speaking) synth.cancel();
        sentenceUtterance = new SpeechSynthesisUtterance(sentence);
        let voices = synth.getVoices();
        let matched = voices.find(v => v.name.includes("{voice_options[voice]}")) || voices[0];
        sentenceUtterance.voice = matched;
        sentenceUtterance.rate = {rate_map[rate]};
        document.querySelectorAll('.sentence').forEach(el => el.style.background = '');
        let span = Array.from(document.querySelectorAll('.sentence')).find(el => el.textContent.trim() === sentence.trim());
        if (span) span.style.background = 'yellow';
        sentenceUtterance.onend = () => {{
            if (span) span.style.background = '';
        }};
        synth.speak(sentenceUtterance);
    }}

    function togglePauseResume() {{
        if (synth.speaking && !synth.paused) {{
            synth.pause();
        }} else if (synth.paused) {{
            synth.resume();
        }}
    }}
    </script>
    <button onclick="togglePauseResume()" style="margin-top:10px; padding:8px 15px; background:#f59e0b; color:white; border:none; border-radius:6px;">⏯️ Pause/Resume</button>
    <style>
    .sentence:hover {{ background-color: #f0f0f0; }}
    </style>
    """
    st.markdown("### 📌 Click a sentence to read it aloud")
    components.html(js_sentence_click, height=500)

# Footer
st.markdown("---")
st.caption("🔊 Built with ❤️ by Jana using Edge-TTS and Streamlit")
