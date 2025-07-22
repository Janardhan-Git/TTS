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
input_mode = st.radio("Choose Input Type", ["Type Text", "Upload .txt File"])

if input_mode == "Type Text":
    user_text = st.text_area("Enter Text to Convert to Speech", height=200)
else:
    uploaded_file = st.file_uploader("Upload a .txt file", type=["txt"])
    user_text = ""
    if uploaded_file is not None:
        user_text = uploaded_file.read().decode("utf-8")
        st.text_area("Preview Uploaded Text", user_text, height=200)

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
    
   #Preview Text
    st.subheader("📄 Preview Text")
    formatted_preview = "<div style='line-height:1.8;'>" + "<br>".join(cleaned_text.split(". ")) + "</div>"
    st.markdown(formatted_preview, unsafe_allow_html=True)

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

# Click-to-read with full sentence support
if user_text:
    escaped_sentences = [s.strip().replace('"', '\"') for s in re.split(r'(?<=[.!?]) +', cleaned_text)]
    sentence_html = "<div style='line-height: 1.8; padding: 10px; border: 1px solid #ccc; border-radius: 8px;'>"
    for sentence in escaped_sentences:
        if sentence:
            sentence_html += f"<span style='cursor:pointer; padding:4px; display:block;' onclick='speakSentence(\"{sentence}\")'>{sentence}</span>"
    sentence_html += "</div>"

    sentence_script = f"""
    <script>
    let synth = window.speechSynthesis;
    let voices = [];

    function populateVoices() {{
        voices = synth.getVoices();
    }}
    populateVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {{
        speechSynthesis.onvoiceschanged = populateVoices;
    }}

    function speakSentence(sentence) {{
        let utterance = new SpeechSynthesisUtterance(sentence);
        let matched = voices.find(v => v.name.includes("{voice_options[voice]}")) || voices[0];
        utterance.voice = matched;
        utterance.rate = {rate_map[rate]};
        synth.cancel();
        synth.speak(utterance);
    }}
    </script>
    """

    st.markdown("### 🎯 Click on a sentence below to read it aloud")
    components.html(sentence_html + sentence_script, height=400)

# Footer
st.markdown("---")
st.caption("🔊 Built with ❤️ by Jana using Edge-TTS and Streamlit")
