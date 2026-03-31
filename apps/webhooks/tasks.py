from celery import shared_task
from agents.router_agent import router_agent
from services.evolution_service import send_whatsapp_message
from services.openai_service import convert_audio_to_text, extract_text_from_image
from apps.users.models import User
import base64

@shared_task
def process_langchain_agent(user_id, raw_message, msg_type, payload):
    user = User.objects.get(id=user_id)
    
    if msg_type == "audioMessage":
        base64_audio = payload.get("base64")
        if base64_audio:
            path = f"/tmp/audio_{user.id}.ogg"
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(base64_audio))
            raw_message = convert_audio_to_text(path)
            
    elif msg_type == "imageMessage":
        base64_image = payload.get("base64")
        if base64_image:
            raw_message = extract_text_from_image(base64_image)

    decision = router_agent(raw_message)
    target_agent = decision.get("agent")
    
    # Roteamento real para o Sub-Agente LangChain criado
    if target_agent == "RegisterTransactionAgent":
        from agents.register_transaction_agent import run_register_agent
        response_text = run_register_agent(user.phone, raw_message)
        
    elif target_agent == "DeleteTransactionAgent":
        from agents.delete_transaction_agent import run_delete_agent
        response_text = run_delete_agent(user.phone, raw_message)
        
    elif target_agent == "UpdateTransactionAgent":
        from agents.update_transaction_agent import run_update_agent
        response_text = run_update_agent(user.phone, raw_message)
        
    else:
        response_text = f"Entendi sua intenção como '{target_agent}', mas ainda não fui programada para realizar essa tarefa! (Integração pendente)"
    
    send_whatsapp_message(user.phone, response_text)
