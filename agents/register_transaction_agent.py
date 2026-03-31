import os
import json
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.tools import tool
from apps.transactions.models import Transaction
from apps.users.models import User

@tool
def _save_transaction(user_phone: str, description: str, category: str, amount: float, transaction_type: str, is_paid: bool) -> str:
    """Ferramenta para registrar a transação no banco de dados.
    transaction_type deve ser 'receita' ou 'despesa'.
    is_paid deve ser um booleano indicando se foi pago.
    """
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
        
        return f"""✅ *{tipo_formatado} Registrada*

🆔 ID: {t.transaction_code}
💸 Tipo: {tipo_formatado}
💰 Valor: R$ {amount:.2f}
📄 Descrição: {description}
🏷️ Categoria: {category}
📅 Data: {t.created_at.strftime('%d/%m/%Y')}
📌 Status: {status_pagamento}

❌ Para excluir ou editar, envie: {t.transaction_code}"""
    except Exception as e:
        return f"Erro ao registrar: {str(e)}"

def run_register_agent(user_phone: str, user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Erro: OPENAI_API_KEY não configurada."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    system_prompt = f"""# AGENTE DE REGISTRO FINANCEIRO - LÍVIA 🦷
Você é o sub-agente especializado em CRIAR transações no banco de dados.
Seu telefone de trabalho é {user_phone}.

## REGRAS DE NEGÓCIO:
1. DESPESA: Sempre status Pago (is_paid=True).
2. RECEITA "A RECEBER": Sempre registrar com is_paid=False.
3. RECEITA "PAGA": Sempre registrar com is_paid=True.

Use a ferramenta _save_transaction para salvar os dados no banco.
Repasse o resultado da ferramenta EXATAMENTE como ela retornar, sem mudar nada.
"""

    tools = [
        Tool(
            name="_save_transaction",
            func=lambda x: _save_transaction(user_phone=user_phone, **json.loads(x)) if isinstance(x, str) else _save_transaction(user_phone=user_phone, **x),
            description="Registra transação. Input deve ser um JSON dict com: description, category, amount, transaction_type ('receita' ou 'despesa'), is_paid (boolean)"
        )
    ]
    
    agent_executor = initialize_agent(
        tools, 
        llm, 
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        agent_kwargs={{"system_message": system_prompt}}
    )

    try:
        response = agent_executor.run(user_message)
        return response
    except Exception as e:
        return f"Desculpe, ocorreu um erro no registro: {str(e)}"
