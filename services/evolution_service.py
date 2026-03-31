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
    
    # Limpa a URL para evitar barras duplas (ex: http://api.com//message)
    base_url = instance_url.rstrip('/')
    url = f"{base_url}/message/sendText/{instance_name}"
    
    headers = {"apikey": api_token, "Content-Type": "application/json"}
    
    # Limpa o telefone para garantir que seja apenas números
    clean_phone = "".join(filter(str.isdigit, phone))
    
    payload = {
        "number": clean_phone,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201]:
            logger.error(f"Erro na Evolution ({response.status_code}): {response.text}")
        response.raise_for_status()
        logger.info(f"Mensagem enviada com sucesso para {phone}.")
        return response.json()
    except Exception as e:
        logger.error(f"Falha ao enviar mensagem para {phone}. Erro: {e}")
        return None
