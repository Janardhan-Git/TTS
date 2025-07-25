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
import mammoth
import markdown
import PyPDF2
import striprtf
from langdetect import detect


def load_lottie(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


st.set_page_config(
    page_title="Text to Speech with Edge-TTS", layout="centered", page_icon="🗣️"
)
st.title("🗣️ Text-to-Speech App with Edge-TTS")

lottie_animation = load_lottie("assets/animation.json")
st_lottie(lottie_animation, height=150, key="header_animation")

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
    </style>
""",
    unsafe_allow_html=True,
)

voice_options = {
    "English - Female": "en-US-JennyNeural",
    "English - Male": "en-US-GuyNeural",
    "Telugu - Male": "te-IN-MohanNeural",
    "Telugu - Female": "te-IN-ShrutiNeural",
}

speed_map = {"Fast": "+25%", "Normal": "+0%", "Slow": "-25%"}
rate_map = {"Fast": 1.25, "Normal": 1.0, "Slow": 0.75}

st.sidebar.header("🔧 Settings")
voice = st.sidebar.selectbox("Select Voice", list(voice_options.keys()))
rate = st.sidebar.selectbox("Select Speed", list(speed_map.keys()))

st.sidebar.subheader("🗣️ Pronunciation Editor (Optional)")
custom_word = st.sidebar.text_input("Word to replace (e.g., OpenAI)")
custom_pronunciation = st.sidebar.text_input(
    "SSML (e.g., <phoneme alphabet='ipa' ph='ˈəʊ.pən.aɪ'>OpenAI</phoneme>)"
)


def extract_text_from_file(uploaded_file, file_type):
    if file_type == "txt":
        return uploaded_file.read().decode("utf-8")
    elif file_type == "pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        return "\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )
    elif file_type == "docx":
        document_obj = docx.Document(uploaded_file)
        return "\n".join([para.text for para in document_obj.paragraphs])
    elif file_type == "doc":
        try:
            result = mammoth.convert_to_markdown(uploaded_file)
            return result.value
        except ValueError:
            return (
                "⚠️ Unable to parse .doc file. Please ensure it's a valid Word document."
            )
    elif file_type == "md":
        raw_md = uploaded_file.read().decode("utf-8")
        return markdown.markdown(raw_md)
    elif file_type == "rtf":
        raw_rtf = uploaded_file.read().decode("utf-8")
        return striprtf.rtf_to_text(raw_rtf)
    return ""


input_mode = st.radio("Choose Input Type", ["Type Text", "Upload File"])
user_text = ""

if input_mode == "Type Text":
    user_text = st.text_area("Enter Text to Convert to Speech", height=200)
else:
    uploaded_file = st.file_uploader(
        "Upload a text file", type=["txt", "pdf", "doc", "docx", "md", "rtf"]
    )
    if uploaded_file is not None:
        file_type = uploaded_file.name.split(".")[-1].lower()
        user_text = extract_text_from_file(uploaded_file, file_type)
        # Only show preview if no text entered/uploaded
        if not user_text.strip():
            st.text_area("📄 Preview Uploaded Text", user_text, height=200)

if user_text:
    try:
        lang = detect(user_text)
        st.sidebar.markdown(f"🌍 Detected Language: **{lang.upper()}**")
        if lang == "te" and not voice.startswith("Telugu"):
            st.warning(
                "⚠️ Telugu text detected. Please select a Telugu voice from sidebar."
            )
        elif lang == "en" and not voice.startswith("English"):
            st.warning(
                "⚠️ English text detected. Please select an English voice from sidebar."
            )
    except:
        st.sidebar.warning("⚠️ Could not detect language")

    if custom_word and custom_pronunciation:
        user_text = user_text.replace(custom_word, custom_pronunciation)


def clean_text(text):
    return re.sub(r"[^\w\s\u0C00-\u0C7F.,!?;:'\"()-]", "", text)


async def generate_speech(text, voice, rate, output_file):
    try:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicate.save(output_file)
    except Exception as e:
        st.error(f"❌ Failed to generate audio: {str(e)}")
        st.code(f"Voice: {voice}\nRate: {rate}\nText: {text[:200]}")
        raise


if user_text:
    cleaned_text = clean_text(user_text)
    # Preview removed after entering/uploading text

    if st.button("🎧 Convert to Speech"):
        output_file = f"{uuid.uuid4().hex}.mp3"
        with st.spinner("Generating audio... Please wait ⏳"):
            asyncio.run(
                generate_speech(
                    cleaned_text, voice_options[voice], speed_map[rate], output_file
                )
            )
        st.success("✅ Conversion Complete!")

        # Play Audio with custom controls (10s skip)
        audio_file = open(output_file, "rb")
        audio_bytes = audio_file.read()
        import base64

        audio_base64 = base64.b64encode(audio_bytes).decode()
        st.markdown(
            f"""
            <audio id="tts-audio" controls style="width:100%;">
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
            <div style="margin-top:8px;">
                <button onclick="var a=document.getElementById('tts-audio'); a.currentTime=Math.max(0,a.currentTime-10);">⏪ 10s</button>
                <button onclick="var a=document.getElementById('tts-audio'); a.currentTime=Math.min(a.duration,a.currentTime+10);">10s ⏩</button>
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
        audio_file.close()
        os.remove(output_file)

if user_text and st.button("🗣️ Read Aloud in Browser"):
    escaped_text = cleaned_text.replace('"', '\\"').replace("\n", " ")
    html_code = f"""
    <script>
    let utterance = null;
    let wordIndex = 0;
    let words = [];
    let spans = [];
    let paused = false;
    let text = `{escaped_text}`;
    function speakText() {{
        utterance = new SpeechSynthesisUtterance(text);
        let allVoices = speechSynthesis.getVoices();
        const preferredVoiceName = `{voice_options[voice]}`;
        const matchedVoice = allVoices.find(v => v.name === preferredVoiceName);
        if (matchedVoice) utterance.voice = matchedVoice;
        utterance.rate = {rate_map[rate]};

        const container = document.getElementById("highlighted-text");
        words = text.split(/\\s+/);
        container.innerHTML = words.map(w => `<span class='word'>${{w}}</span>`).join(" ");
        spans = container.querySelectorAll(".word");
        wordIndex = 0;

        utterance.onboundary = (event) => {{
            if (event.name === 'word') {{
                spans.forEach(span => span.style.background = '');
                if (spans[wordIndex]) {{
                    spans[wordIndex].style.background = 'yellow';
                    wordIndex++;
                }}
            }}
        }};

        utterance.onend = () => {{
            spans.forEach(span => span.style.background = '');
            wordIndex = 0;
        }};

        speechSynthesis.speak(utterance);
    }}

    function skip10s(forward) {{
        if (!utterance) return;
        speechSynthesis.pause();
        if (forward) {{
            wordIndex = Math.min(words.length-1, wordIndex+20);
        }} else {{
            wordIndex = Math.max(0, wordIndex-20);
        }}
        speechSynthesis.cancel();
        let newText = words.slice(wordIndex).join(' ');
        utterance = new SpeechSynthesisUtterance(newText);
        let allVoices = speechSynthesis.getVoices();
        const preferredVoiceName = `{voice_options[voice]}`;
        const matchedVoice = allVoices.find(v => v.name === preferredVoiceName);
        if (matchedVoice) utterance.voice = matchedVoice;
        utterance.rate = {rate_map[rate]};
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
    }}

    function togglePauseResume() {{
        if (!window.speechSynthesis || !utterance) return;
        if (speechSynthesis.speaking && !speechSynthesis.paused) {{
            speechSynthesis.pause();
        }} else if (speechSynthesis.paused) {{
            speechSynthesis.resume();
        }}
    }}

    window.onload = function() {{
        speakText();
    }};
    </script>
    <style>
    #highlighted-text {{ font-size: 18px; line-height: 1.6; margin-top: 10px; }}
    .word {{ padding: 2px; margin-right: 2px; }}
    </style>
    <div id="highlighted-text"></div>
    <div style="margin-top:8px;">
        <button onclick="skip10s(false)">⏪ 10s</button>
        <button onclick="togglePauseResume()">⏯️ Pause/Resume</button>
        <button onclick="skip10s(true)">10s ⏩</button>
    </div>
    """
    components.html(html_code)

if user_text:
    escaped_sentences = re.split(r"(?<=[.!?]) +", cleaned_text.replace("\n", " "))
    js_sentence_click = """
    <div id="sentence-text" style="line-height: 2; padding: 10px; max-height: 300px; overflow-y: auto;">
    """
    for sentence in escaped_sentences:
        clean_sent = sentence.strip().replace('"', '"')
        js_sentence_click += (
            f"<span class='sentence' onclick='speakSentence(\"{clean_sent}\")' style='cursor:pointer; display:block; padding:5px; margin-bottom:8px; border:1px solid #ccc; border-radius:6px;'>"
            + sentence
            + "</span>"
        )
    js_sentence_click += "</div>"

    actual_voice_name = voice_options[voice]
    js_sentence_click += f"""
<script>
let synth = window.speechSynthesis;
let sentenceUtterance = null;
let voicesLoaded = false;
let cachedVoices = [];

function loadVoices() {{
    return new Promise(resolve => {{
        let voices = synth.getVoices();
        if (voices.length !== 0) {{
            voicesLoaded = true;
            cachedVoices = voices;
            resolve(voices);
        }} else {{
            synth.onvoiceschanged = () => {{
                voicesLoaded = true;
                cachedVoices = synth.getVoices();
                resolve(cachedVoices);
            }};
        }}
    }});
}}

function speakSentence(sentence) {{
    if (!voicesLoaded) {{
        loadVoices().then(() => speakSentence(sentence));
        return;
    }}

    synth.cancel();

    sentenceUtterance = new SpeechSynthesisUtterance(sentence);
    const matched = cachedVoices.find(v => v.name.toLowerCase().includes("{actual_voice_name.lower()}")) || cachedVoices[0];
    sentenceUtterance.voice = matched;
    sentenceUtterance.lang = matched.lang;
    sentenceUtterance.rate = {rate_map[rate]};

    document.querySelectorAll('.sentence').forEach(el => el.style.background = '');
    let span = Array.from(document.querySelectorAll('.sentence')).find(el => el.textContent.trim() === sentence.trim());
    if (span) span.style.background = 'yellow';

    sentenceUtterance.onend = () => {{
        if (span) span.style.background = '';
        sentenceUtterance = null;
    }};

    synth.speak(sentenceUtterance);
}}

function togglePauseResume() {{
    if (!window.speechSynthesis || !sentenceUtterance) return;
    if (synth.speaking && !synth.paused) {{
        synth.pause();
    }} else if (synth.paused) {{
        synth.resume();
    }}
}}

function skipSentence(forward) {{
    let sentences = Array.from(document.querySelectorAll('.sentence'));
    let current = sentences.findIndex(el => el.style.background === 'yellow');
    let next = forward ? Math.min(sentences.length-1, current+1) : Math.max(0, current-1);
    if (next !== -1 && next !== current) {{
        sentences[next].click();
    }}
}}

</script>

<div style="margin-top:10px;">
    <button onclick="skipSentence(false)">⏪ Prev</button>
    <button onclick="togglePauseResume()">⏯️ Pause/Resume</button>
    <button onclick="skipSentence(true)">Next ⏩</button>
</div>

<style>
.sentence:hover {{
    background-color: #f0f0f0;
}}
</style>
"""

    st.markdown("### 📌 Click a sentence to read it aloud")
    components.html(js_sentence_click, height=350)

st.markdown("---")
st.caption("🔊 Built with ❤️ by Jana using Edge-TTS and Streamlit")
