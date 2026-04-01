import os
import json
from openai import OpenAI
from apps.transactions.models import Transaction
from apps.users.models import User, UserContext
from django.utils import timezone
import pytz

def _save_transaction(user_phone: str, description: str, category: str, amount: float, transaction_type: str, is_paid: bool) -> str:
    """Ferramenta para registrar a transação no banco de dados."""
    user = User.objects.filter(phone=user_phone).first()
    if not user:
        return "Erro: Usuário não encontrado."

    try:
        t = Transaction.objects.create(
            user=user,
            description=description,
            category=category,
            amount=amount,
            type=transaction_type,
            is_paid=is_paid
        )
        status_pagamento = "Pago" if is_paid else "A receber"
        tipo_formatado = transaction_type.capitalize()
        
        # Forçar fuso horário de São Paulo para o ticket
        tz = pytz.timezone('America/Sao_Paulo')
        data_br = timezone.now().astimezone(tz).strftime('%d/%m/%Y')
        
        # Limpar o contexto após salvar com sucesso
        UserContext.objects.filter(user=user).delete()
        
        return f"""✅ *{tipo_formatado} Registrada*

🆔 ID: {t.transaction_code}
💸 Tipo: {tipo_formatado}
💰 Valor: R$ {amount:.2f}
📄 Descrição: {description}
🏷️ Categoria: {category}
📅 Data: {data_br}
📌 Status: {status_pagamento}

❌ Para excluir ou editar, envie: {t.transaction_code}"""
    except Exception as e:
        return f"Erro ao registrar: {str(e)}"

def run_register_agent(user_phone: str, user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Erro: OPENAI_API_KEY não configurada."

    user = User.objects.filter(phone=user_phone).first()
    client = OpenAI(api_key=api_key)
    context, _ = UserContext.objects.get_or_create(user=user)
    
    # 1. Se o usuário já respondeu a pergunta anterior (pago ou a receber)
    msg_lower = user_message.lower()
    if context.pending_data and context.last_action == "AWAITING_PAYMENT_STATUS":
        is_paid = None
        if any(x in msg_lower for x in ["pago", "recebi", "já caiu", "já pagou", "ja recebi", "pix", "transferência"]):
            is_paid = True
        elif any(x in msg_lower for x in ["receber", "pendente", "aberto", "a receber", "fiado", "vou receber"]):
            is_paid = False
            
        if is_paid is not None:
            data = context.pending_data
            return _save_transaction(
                user_phone=user_phone,
                description=data.get("description"),
                category=data.get("category"),
                amount=data.get("amount"),
                transaction_type=data.get("transaction_type"),
                is_paid=is_paid
            )

    # 2. Se for uma mensagem nova de registro
    extraction_prompt = f"""Extraia valor, descrição, categoria (NOME DA LINHA ou PACIENTE) e tipo (receita/despesa) desta mensagem: '{user_message}'.
    REGRAS DE CATEGORIA: NUNCA USE 'receita' ou 'despesa' como categoria. Se não houver nome de clínica, use a descrição curta.
    Retorne apenas JSON: {{"amount": float, "description": str, "category": str, "transaction_type": "receita"|"despesa"}}"""
    
    extract_res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": extraction_prompt}],
        response_format={"type": "json_object"}
    )
    extracted = json.loads(extract_res.choices[0].message.content)

    # 3. Decisão de fluxo
    if extracted.get("transaction_type") == "despesa":
        # Despesas registramos direto como Pago
        return _save_transaction(
            user_phone=user_phone,
            description=extracted.get("description"),
            category=extracted.get("category"),
            amount=extracted.get("amount"),
            transaction_type="despesa",
            is_paid=True
        )
    else:
        # Receita: SEMPRE PERGUNTAR (Mesmo se disser 'recebi' na primeira frase por enquanto, para garantir fluxo)
        context.pending_data = extracted
        context.last_action = "AWAITING_PAYMENT_STATUS"
        context.save()
        val = extracted.get("amount")
        return f"Para registrar certinho: essa receita de R$ {val:.2f} já foi recebida ou ainda está a receber?"
