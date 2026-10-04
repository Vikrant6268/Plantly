import json
from google import genai
from google.genai import types
import streamlit as st
from twilio.rest import Client as TwilioClient

from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE, SUMMARY_REQUEST_PROMPT

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_twilio_client():
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

twilio_client = get_twilio_client()

gemini_client = get_gemini_client()
MODEL_NAME = "gemini-3.8-flash"

def clean_whatsapp_text(text):
    if not text:
        return "No summary availble."
    text = " ".join(text.split()) # collapse whitespace / newlines
    return text[:1500] + "..." if len(text) > 1500 else text

def send_whatsapp(to_number, user_name, summary):
    try:
        content_variables = json.dumps(
            {"1": user_name, "2": clean_whatsapp_text(summary)}, ensure_ascii=False
            )
        message = twilio_client.messages.create(
           from_= TWILIO_WHATSAPP_FROM,
           to= f"whatsapp:{to_number}",
           content_sid = TWILIO_CONTENT_SID,
           content_variables= content_variables,   
        )
        return true, message.sid
    except Exception as error:
        return False, str(error)
    
        
def render_message(message):
    with st.chat_message(message["role"]):
        if message["content_type"] == "text":
            st.write(message["content"])
        elif message["content_type"] == "image":
            st.image(message["content"])
            
def add_message(role, content_type, content):
    st.session_state.messages.append({"role": role, "content_type": content_type, "content": content})
    render_message(st.session_state.messages[-1])

def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text 
    except Exception as error:
        return f"Sorry something went wrong: {error}"
    
    
    #Step-1: Onboardeing (Username and Email)

if 'onboarded' not in st.session_state:
    st.title("Plantly 🌱")
    st.caption("Welcome to Plantly! Your AI Plant Health Assistant.")
    
    with st.form("onboarding_form"):
        name = st.text_input("Enteryour name")
        Whatsapp_number = st.text_input(
        "Whatsapp number (with country code)",
        placeholder="+91XXXXXXXXXX",
        help="This is the number where you'll receive your plant health summary and updates."
        )
        
        submitted = st.form_submit_button("Get Started")
        
    if submitted:
        if not name.strip() or not Whatsapp_number.strip():
            st.warning("Please enter both your name and WhatsApp number.")
        else:
            st.session_state.name = name.strip()
            st.session_state.Whatsapp_number = Whatsapp_number.strip()
            # activate my Ai model here 
            st.session_state.chat = gemini_client.chats.create(
                model = MODEL_NAME,
                config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()
    st.stop()
# create a chat interface 
header_col, button_col = st.columns([5, 2], vertical_alignment="center")
with header_col:
    st.title("Plantly 🌱")
with button_col:
    send_disabled = len(st.session_state.messages) <=1 
    if st.button("📲 Send to WhatsApp", disabled=send_disabled, use_container_width=True):
        with st.spinner("Generating summary..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
            
        success, info = send_whatsapp(st.session_state.Whatsapp_number, st.session_state.name, summary) 
        if success:
            st.success("Summary sent to WhatsApp successfully!")
        else:
            st.error(f"Failed to send summary to WhatsApp: {info}")            

st.caption(f"Logged in as {st.session_state.name} - updates will be sent to {st.session_state.Whatsapp_number}")

if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)
 
user_input = st.chat_input(
    "Type your message here, or upload a photo of your plant to get started. 🌿",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
   
)  

if user_input:
    photo = user_input.files[0]  if user_input.files else None
    text = user_input.text 
    parts = []
    
    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))
    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif photo is not None:
        parts.append("Please analyze the attached plant photo and provide insights regarding plant health.")
    with st.spinner("Generating response..."):     
        answer = ask_gemini(parts)
    add_message("assistant", "text", answer)   