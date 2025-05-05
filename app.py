import gradio as gr
from nlp_parser import parse_command_using_cohere

def process_command(user_command):
    return parse_command_using_cohere(user_command)

# Gradio simple app
with gr.Interface(
    fn=process_command,
    inputs=gr.Textbox(label="Enter your calendar command here:"),
    outputs=gr.Textbox(label="Assistant Response"),
    title="Calendar Assistant",
    description="Ask about today's or tomorrow's events."
) as app:
    app.launch(share=True)  # ✅ Important: share=True added
