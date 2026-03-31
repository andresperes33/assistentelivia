import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def convert_audio_to_text(audio_path: str):
    if not client: return ""
    with open(audio_path, "rb") as file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=file, 
            response_format="text"
        )
    return transcript

def extract_text_from_image(base64_image: str):
    if not client: return ""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extraia as informações cruciais desta fatura/comprovante (valor, descrição, data e recebedor/pagador). Responda um texto curto."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        ],
    )
    return response.choices[0].message.content
