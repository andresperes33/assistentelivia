from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.tools import tool
from apps.transactions.models import Transaction
from apps.users.models import User
import os

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
        status_pagamento = "Pago/Recebido" if is_paid else "A Pagar/A Receber"
        return f"Transação registrada com sucesso! ID: {t.transaction_code}. Categoria: {category}, Valor: R${amount:.2f}, Status: {status_pagamento}."
    except Exception as e:
        return f"Erro ao registrar: {str(e)}"

def run_register_agent(user_phone: str, user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Erro: OPENAI_API_KEY não configurada."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    system_prompt = '''# AGENTE DE REGISTRO FINANCEIRO - LÍVIA 🦷
Você é o sub-agente especializado em CRIAR transações no banco de dados.

## SUAS FERRAMENTAS:
- Use _save_transaction para salvar os dados.

## REGRAS DE NEGÓCIO:
1. DESPESA: Sempre status Pago (is_paid=True).
2. RECEITA "A RECEBER": Sempre registrar com is_paid=False.
3. RECEITA "PAGA": Sempre registrar com is_paid=True.
4. Se não souber se a RECEITA é paga ou a receber, pergunte: "Só para registrar certinho: essa receita de [valor] já foi recebida ou ainda está a receber?".

## FORMATO DE RESPOSTA OBRIGATÓRIO APÓS SALVAR:
✅ *[Tipo] Registrada*

🆔 ID: [transaction_code]
💸 Tipo: [Receita/Despesa]
💰 Valor: R$ [valor]
📄 Descrição: [descrição]
🏷️ Categoria: [categoria]
📅 Data: [data_atual]
📌 Status: [Pago / A receber]

❌ Para excluir ou editar, envie: [transaction_code]
'''

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Telefone do usuário: {user_phone}\nMensagem: {input}")
    ])

    tools = [_save_transaction]
    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    try:
        response = agent_executor.invoke({"user_phone": user_phone, "input": user_message})
        return response["output"]
    except Exception as e:
        return f"Desculpe, ocorreu um erro no registro: {str(e)}"
