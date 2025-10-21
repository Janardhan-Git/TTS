import streamlit as st
import edge_tts
import asyncio
import os
import uuid
import re
import json
import docx
import mammoth
import markdown
import PyPDF2
from striprtf.striprtf import rtf_to_text
from langdetect import detect, LangDetectException
import base64
import nest_asyncio
from pydub import AudioSegment
from gtts import gTTS
import requests
import time

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Utility Functions
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Failed to load {file}: {e}")
            return default
    return default

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Failed to save {file}: {e}")

# File Text Extraction
def extract_text_from_file(uploaded_file, file_type):
    try:
        if file_type == "txt":
            return uploaded_file.read().decode("utf-8")
        elif file_type == "pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        elif file_type == "docx":
            document_obj = docx.Document(uploaded_file)
            return "\n".join([para.text for para in document_obj.paragraphs])
        elif file_type == "doc":
            result = mammoth.convert_to_markdown(uploaded_file)
            return result.value
        elif file_type == "md":
            raw_md = uploaded_file.read().decode("utf-8")
            return markdown.markdown(raw_md)
        elif file_type == "rtf":
            raw_rtf = uploaded_file.read().decode("utf-8")
            return rtf_to_text(raw_rtf)
        return ""
    except Exception as e:
        st.error(f"Error processing file: {e}")
        return ""

# Streamlit Page Configuration
st.set_page_config(
    page_title="Text to Speech with Edge-TTS", layout="centered", page_icon="🗣️"
)
st.title("🗣️ Text-to-Speech App with Edge-TTS")

# Custom CSS for styling
st.markdown(
    """
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
    .audio-controls button {
        background-color: #3b82f6;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px 15px;
        margin: 0 5px;
        cursor: pointer;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Voice and Speed Options
voice_options = {
    "English - Female": "en-US-JennyNeural",
    "English - Male": "en-US-GuyNeural",
    "Telugu - Male": "te-IN-MohanNeural",
    "Telugu - Female": "te-IN-ShrutiNeural",
}
speed_map = {"Fast": "+25%", "Normal": "+0%", "Slow": "-25%"}
rate_map = {"Fast": 1.25, "Normal": 1.0, "Slow": 0.75}

# Sidebar Settings
st.sidebar.header("🔧 Settings")
voice = st.sidebar.selectbox("Select Voice", list(voice_options.keys()))
rate = st.sidebar.selectbox("Select Speed", list(speed_map.keys()))

# Pronunciation Editor
PRON_FILE = "pronunciations.json"
pronunciations = load_json(PRON_FILE, {})

st.sidebar.subheader("🗣️ Pronunciation Editor (Persistent)")
custom_word = st.sidebar.text_input("Word (e.g., OpenAI)")
custom_pronunciation = st.sidebar.text_input("Pronunciation/SSML")

if st.sidebar.button("💾 Save Pronunciation"):
    if custom_word and custom_pronunciation:
        pronunciations[custom_word] = custom_pronunciation
        save_json(PRON_FILE, pronunciations)
        st.sidebar.success(f"Saved pronunciation for '{custom_word}'")

if pronunciations:
    st.sidebar.markdown("### 📌 Stored Pronunciations")
    for word, pron in pronunciations.items():
        st.sidebar.write(f"- **{word}** → {pron}")

# Input Handling
input_mode = st.radio("Choose Input Type", ["Type Text", "Upload File"])
user_text = ""

if input_mode == "Type Text":
    user_text = st.text_area("Enter Text to Convert to Speech", height=200)
else:
    uploaded_file = st.file_uploader(
        "Upload a text file", type=["txt", "pdf", "doc", "docx", "md", "json", "rtf"]
    )
    if uploaded_file is not None:
        file_type = uploaded_file.name.split(".")[-1].lower()
        user_text = extract_text_from_file(uploaded_file, file_type)

# Language Detection and Voice Validation
def validate_language_and_voice(text, selected_voice):
    try:
        lang = detect(text)
        st.sidebar.markdown(f"🌍 Detected Language: **{lang.upper()}**")
        if lang == "te" and not selected_voice.startswith("Telugu"):
            st.warning("⚠️ Telugu text detected. Consider selecting a Telugu voice.")
        elif lang == "en" and not selected_voice.startswith("English"):
            st.warning("⚠️ English text detected. Consider selecting an English voice.")
        return lang
    except LangDetectException:
        st.sidebar.warning("⚠️ Could not detect language")
        return None

# Apply pronunciations once
def apply_pronunciations(text, pronunciations):
    for word, pron in pronunciations.items():
        text = text.replace(word, pron)
    return text

def clean_text(text):
    text = re.sub(r'[#*]', '', text)
    return text

# Async TTS Generation with retries and fallback
async def generate_speech_chunk(text, voice, rate, output_file, lang="en", max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            response = requests.get("https://www.bing.com", timeout=5)
            if response.status_code != 200:
                st.error(f"❌ Network test failed with status {response.status_code}")
                raise Exception("Network connectivity issue")

            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
            await communicate.save(output_file)
            
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                st.info(f"✅ Chunk generated with edge_tts (Attempt {attempt + 1}): {len(text)} chars")
                return True, "edge_tts"
            else:
                raise edge_tts.exceptions.NoAudioReceived("Empty file from edge_tts")
                
        except edge_tts.exceptions.NoAudioReceived as e:
            st.warning(f"⚠️ edge_tts failed (Attempt {attempt + 1}/{max_retries + 1}): {str(e)[:100]}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                fallback_voice = "en-US-AriaNeural" if "en" in lang else "te-IN-SruthikaNeural"
                fallback_rate = "-10%" if attempt == 0 else "+0%"
                st.info(f"🔄 Retrying with voice={fallback_voice}, rate={fallback_rate}")
                continue
            else:
                st.info(f"🔄 Falling back to gTTS (Attempt {attempt + 1}): {len(text)} chars")
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.save(output_file)
                
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return True, "gtts"
                else:
                    raise Exception(f"gTTS failed: Empty file")
                    
        except Exception as e:
            st.error(f"❌ Unexpected error in attempt {attempt + 1}: {str(e)[:100]}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise

# Helper function to run async code safely
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Split text into chunks
def split_text_into_chunks(text, max_chars=4000):
    chunks = []
    current_chunk = ""
    sentences = re.split(r'(?<=[.!?]) +', text)
    for sentence in sentences:
        test_chunk = current_chunk + (" " if current_chunk else "") + sentence
        if len(test_chunk) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk = test_chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# Process and generate speech
if user_text:
    lang = validate_language_and_voice(user_text, voice) or "en"
    processed_text = apply_pronunciations(user_text, pronunciations)
    cleaned_text = clean_text(processed_text)

    if st.button("🎧 Convert to Speech"):
        output_file = f"{uuid.uuid4().hex}.mp3"
        temp_files = []
        failed_chunks = 0
        try:
            with st.spinner("Generating audio... Please wait ⏳"):
                chunks = split_text_into_chunks(cleaned_text)
                st.info(f"📝 Splitting into {len(chunks)} chunks")
                
                for i, chunk in enumerate(chunks):
                    temp_file = f"temp_{i}.mp3"
                    success, method = run_async(
                        generate_speech_chunk(chunk, voice_options[voice], speed_map[rate], temp_file, lang)
                    )
                    if success:
                        temp_files.append(temp_file)
                        st.info(f"Chunk {i+1}/{len(chunks)} ({method}): OK")
                    else:
                        failed_chunks += 1
                        st.error(f"❌ Chunk {i+1} failed completely. Skipping.")
                        if os.path.exists(temp_file):
                            os.remove(temp_file)

                if not temp_files:
                    st.error("❌ All chunks failed. Check network or try shorter text.")
                    st.stop()

                if temp_files:
                    combined = AudioSegment.empty()
                    for temp in temp_files:
                        audio = AudioSegment.from_mp3(temp)
                        combined += audio
                    combined.export(output_file, format="mp3")

                if failed_chunks > 0:
                    st.warning(f"⚠️ {failed_chunks}/{len(chunks)} chunks failed (used fallback where possible).")

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                st.success("✅ Conversion Complete!")
                with open(output_file, "rb") as audio_file:
                    audio_bytes = audio_file.read()
                    audio_base64 = base64.b64encode(audio_bytes).decode()
                    st.markdown(
                        f"""
                        <audio id="tts-audio" controls style="width:100%;">
                            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                            Your browser does not support the audio element.
                        </audio>
                        <div class="audio-controls" style="margin-top:8px;">
                            <button onclick="var a=document.getElementById('tts-audio'); if (!isNaN(a.currentTime)) a.currentTime=Math.max(0,a.currentTime-10);">⏪ 10s</button>
                            <button onclick="var a=document.getElementById('tts-audio'); if (!isNaN(a.currentTime) && !isNaN(a.duration)) a.currentTime=Math.min(a.duration,a.currentTime+10);">10s ⏩</button>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.download_button(
                        label="📥 Download Audio",
                        data=audio_bytes,
                        file_name="converted_speech.mp3",
                        mime="audio/mp3",
                    )
            else:
                st.error("❌ Final audio file is empty. Try again or use shorter text.")
        finally:
            for temp in temp_files:
                if os.path.exists(temp):
                    os.remove(temp)
            if os.path.exists(output_file) and "audio_bytes" not in locals():
                os.remove(output_file)

st.markdown("---")
st.caption("🔊 Built with ❤️ by Jana using Edge-TTS and Streamlit (with gTTS fallback)")