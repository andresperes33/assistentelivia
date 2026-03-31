from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from apps.transactions.models import Transaction
from apps.users.models import User
import os

@tool
def _update_payment_status(user_phone: str, transaction_code: str, is_paid: bool) -> str:
    """Ferramenta para marcar uma transação como paga (true) ou a pagar/receber (false)."""
    user = User.objects.filter(phone=user_phone).first()
    if not user:
        return "Erro: Usuário não encontrado."

    transaction = Transaction.objects.filter(user=user, transaction_code=transaction_code).first()
    if not transaction:
        return f"Desculpe! Nenhuma transação encontrada com o código '{transaction_code}'."
    
    transaction.is_paid = is_paid
    transaction.save()
    status_msg = "PAGO/RECEBIDO" if is_paid else "A Pagar/A Receber"
    return f"Pronto! A transação '{transaction.description}' (ID: {transaction_code}) agora consta com o status: {status_msg}."

def run_update_status_agent(user_phone: str, user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Erro: OPENAI_API_KEY não configurada."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    system_prompt = '''Você é o sub-agente de Atualização Financeira.
Sua função é atualizar o status de pagamento de uma transação usando a ferramenta _update_payment_status.

REGRAS:
1. Para atualizar, é OBRIGATÓRIO informar o código da transação (3 dígitos alfanuméricos) E se a intenção é marcar como PAGA/RECEBIDA (is_paid=True) ou A PAGAR (is_paid=False).
2. Se o usuário NÃO forneceu um código identificador, não tente adivinhar. Peça-o educadamente: "Certo! Para qual código de transação devo aplicar essa baixa?".
3. Após chamar a ferramenta, retorne a mensagem de sucesso ou falha fornecida pro usuário de forma amigável.'''

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Meu telefone é {user_phone}. A mensagem é: {input}")
    ])

    tools = [_update_payment_status]
    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    try:
        response = agent_executor.invoke({"user_phone": user_phone, "input": user_message})
        return response["output"]
    except Exception as e:
        return f"Desculpe, ocorreu um erro ao atualizar o status: {str(e)}"
