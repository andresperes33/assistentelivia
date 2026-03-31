import os
import requests
import logging

logger = logging.getLogger(__name__)

def send_whatsapp_message(phone: str, text: str):
    instance_url = os.getenv("EVOLUTION_API_URL")
    api_token = os.getenv("EVOLUTION_API_TOKEN")
    
    if not instance_url or not api_token:
        logger.error("Evolution API URL ou Token não configurados.")
        return None

    instance_name = os.getenv("EVOLUTION_INSTANCE_NAME", "livia-bot")
    url = f"{instance_url}/message/sendText/{instance_name}"
    headers = {"apikey": api_token, "Content-Type": "application/json"}
    
    payload = {
        "number": phone,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Mensagem enviada com sucesso para {phone}.")
        return response.json()
    except Exception as e:
        logger.error(f"Falha ao enviar mensagem para {phone}. Erro: {e}")
        return None
