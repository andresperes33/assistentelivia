import os
import json
from openai import OpenAI
from apps.transactions.models import Transaction
from apps.users.models import User
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

    client = OpenAI(api_key=api_key)
    
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
                        "category": {"type": "string", "description": "Categoria da transação (ex: Limpeza, Canal, Aluguel, Material)."},
                        "amount": {"type": "number", "description": "Valor monetário da transação."},
                        "transaction_type": {"type": "string", "enum": ["receita", "despesa"]},
                        "is_paid": {"type": "boolean", "description": "True se já foi pago/recebido, False se for pendente."}
                    },
                    "required": ["description", "category", "amount", "transaction_type", "is_paid"]
                }
            }
        }
    ]

    system_prompt = f"""Você é o sub-agente especializado em CRIAR transações no banco de dados da Livia.
Seu telefone de trabalho é {user_phone}.

REGRAS DE NEGÓCIO:
1. DESPESA: Sempre status Pago (is_paid=True).
2. RECEITA 'paga' ou 'ganhei': is_paid=True.
3. RECEITA 'a receber' ou 'vou ganhar': is_paid=False.

Extraia as informações e use a ferramenta _save_transaction."""

    # 2. Chamar a OpenAI para extrair dados e decidir pela ferramenta
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
                # Chama a função real do Django
                return _save_transaction(
                    user_phone=user_phone,
                    description=args.get("description"),
                    category=args.get("category"),
                    amount=args.get("amount"),
                    transaction_type=args.get("transaction_type"),
                    is_paid=args.get("is_paid")
                )
    
    return response_message.content or "Desculpe, não consegui entender o registro."
