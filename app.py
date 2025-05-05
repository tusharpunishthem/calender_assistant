import gradio as gr
import datetime
import cohere
import speech_recognition as sr
import os
from calendar_assistant import CalendarAssistant
from dotenv import load_dotenv

load_dotenv()

# Initialize
co = cohere.Client(os.getenv("COHERE_API_KEY"))
calendar = CalendarAssistant()

# Voice Input (STT)
def transcribe_audio(audio):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio) as source:
        audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data)

# Parse intent + details from Cohere
def parse_command(text):
    response = co.chat(
        message=text,
        connectors=[{"id": "web-search"}],
        temperature=0.3
    )
    return response.text

# Main Action
def calendar_bot(input_text=None, audio=None):
    if audio:
        try:
            input_text = transcribe_audio(audio)
        except Exception as e:
            return f"🎙️ Voice Error: {e}"

    if not input_text:
        return "❗ Please enter or say something."

    print(f"[USER INPUT] {input_text}")
    parsed = parse_command(input_text)
    print(f"[PARSED] {parsed}")

    # Simple NLP triggers
    text = input_text.lower()

    if "create" in text and "event" in text:
        try:
            summary = input("Event title? ")
            start = input("Start (YYYY-MM-DDTHH:MM:SS): ")
            end = input("End (YYYY-MM-DDTHH:MM:SS): ")
            emails = input("Invite emails (comma-separated): ").split(",")
            calendar.create_event(summary, start, end, emails)
            return f"📅 Event '{summary}' created!"
        except Exception as e:
            return f"❌ Error creating event: {e}"

    elif "today" in text and "event" in text:
        calendar.list_today_events()
        return "✅ Listed today's events."

    elif "tomorrow" in text:
        calendar.list_tomorrow_events()
        return "✅ Listed tomorrow's events."

    elif "free slot" in text or "available time" in text:
        calendar.find_free_slots()
        return "✅ Displayed available free slots."

    elif "week" in text:
        calendar.show_week_events()
        return "✅ Listed this week's events."

    else:
        return f"🤖 Not sure how to help with: '{input_text}'"

# Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("## 🤖 Calendar Assistant — Text or Voice Input")
    with gr.Row():
        txt_input = gr.Textbox(label="Type your command")
        audio_input = gr.Audio(source="upload", type="filepath", label="or Upload Voice Command")

    btn = gr.Button("Execute")
    output = gr.Textbox(label="Assistant Response")

    btn.click(calendar_bot, inputs=[txt_input, audio_input], outputs=output)

if __name__ == "__main__":
    demo.launch()
