import os
import json
from openai import OpenAI
from apps.transactions.models import Transaction
from apps.users.models import User, UserContext
from django.utils import timezone

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
        data_atual = timezone.now().strftime('%d/%m/%Y')
        
        # Limpar o contexto após salvar com sucesso
        UserContext.objects.filter(user=user).delete()
        
        return f"""✅ *{tipo_formatado} Registrada*

🆔 ID: {t.transaction_code}
💸 Tipo: {tipo_formatado}
💰 Valor: R$ {amount:.2f}
📄 Descrição: {description}
🏷️ Categoria: {category}
📅 Data: {data_atual}
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
    
    # Se chegamos aqui e o usuário respondeu algo como "pago" ou "a receber",
    # precisamos recuperar o que ele tentou registrar antes.
    context, _ = UserContext.objects.get_or_create(user=user)
    
    # 1. Definir a ferramenta de registro
    tools = [
        {
            "type": "function",
            "function": {
                "name": "_save_transaction",
                "description": "Registra uma receita ou despesa no financeiro do dentista.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "Descrição do que foi ganho ou gasto."},
                        "category": {"type": "string", "description": "Categoria da transação."},
                        "amount": {"type": "number", "description": "Valor monetário."},
                        "transaction_type": {"type": "string", "enum": ["receita", "despesa"]},
                        "is_paid": {"type": "boolean", "description": "True se já foi pago/recebido, False se for pendente."}
                    },
                    "required": ["description", "category", "amount", "transaction_type", "is_paid"]
                }
            }
        }
    ]

    system_prompt = f"""Você é o sub-agente de Registro Financeiro da Livia. 🦷⚙️
Seu telefone de trabalho é {user_phone}.

REGRAS OBRIGATÓRIAS:
1. DESPESA: Sempre status Pago (is_paid=True). Registre direto.
2. RECEITA:
   - SE o usuário disser "pago", "recebi", "já caiu", "confirmado": use is_paid=True e REGISTRE.
   - SE o usuário disser "a receber", "vou ganhar", "pendente": use is_paid=False e REGISTRE.
   - SE você ainda não souber o status, NÃO chame a ferramenta.

CONTEXTO PENDENTE: {context.pending_data if context.pending_data else "Nenhum"}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        for tool_call in tool_calls:
            if tool_call.function.name == "_save_transaction":
                args = json.loads(tool_call.function.arguments)
                return _save_transaction(
                    user_phone=user_phone,
                    description=args.get("description"),
                    category=args.get("category"),
                    amount=args.get("amount"),
                    transaction_type=args.get("transaction_type"),
                    is_paid=args.get("is_paid")
                )
    
    # Se ele não chamou a ferramenta, vamos tentar salvar o contexto do que ele tentou fazer
    # Usamos uma chamada extra rápida para extrair os dados básicos se eles ainda não estiverem no contexto
    if not context.pending_data:
        extraction_prompt = "Extraia o valor, descrição, categoria e tipo (receita/despesa) desta mensagem em JSON: " + user_message
        extract_res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": extraction_prompt}],
            response_format={"type": "json_object"}
        )
        context.pending_data = json.loads(extract_res.choices[0].message.content)
        context.last_action = "AWAITING_PAYMENT_STATUS"
        context.save()

    return response_message.content or "Para registrar certinho: essa receita já foi recebida ou ainda está a receber?"
