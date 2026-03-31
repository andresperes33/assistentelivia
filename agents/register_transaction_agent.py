from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
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

    system_prompt = '''Você é o sub-agente de Registro Financeiro de uma assistente chamada Livia para dentistas.

Sua única função é extrair informações da mensagem do dentista para registrar UMA transação (Receita ou Despesa) usando a ferramenta _save_transaction.

REGRAS OBRIGATÓRIAS:
1. Extraia: description, category, amount, transaction_type (receita/despesa) e is_paid (true/false).
2. SE a transação for DESPESA:
   - Assuma sempre is_paid=True (já está paga), a não ser que o usuário diga explicitamente que é "para pagar depois" ou "vence dia X". Não precisa perguntar.
3. SE a transação for RECEITA:
   - Se o usuário NÃO deixou claro se já recebeu o dinheiro ou se vai receber depois: NÃO chame a ferramenta de salvar! Em vez disso, pergunte educadamente e de forma curta: "Só para registrar certinho: essa receita de [valor] já foi recebida ou ainda está a receber?".
   - CUIDADO: Se ele já disse "recebi", "já pagou", "pix", "transferiu", etc, assuma is_paid=True. Se disse "vai pagar", "fiado", "a lançar", is_paid=False.
4. Responda de forma direta e amigável.

Se você chamar a ferramenta _save_transaction, repasse o resultado final da ferramenta pro usuário.'''

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        # Se tivesse histórico de chat, passaria MessagesPlaceholder aqui
        ("human", "Meu telefone é {user_phone}. A mensagem é: {input}")
    ])

    tools = [_save_transaction]
    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    try:
        response = agent_executor.invoke({"user_phone": user_phone, "input": user_message})
        return response["output"]
    except Exception as e:
        return f"Desculpe, ocorreu um erro no registro: {str(e)}"
