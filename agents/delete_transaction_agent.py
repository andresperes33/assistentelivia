from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from apps.transactions.models import Transaction
from apps.users.models import User
import os

@tool
def _delete_transaction(user_phone: str, transaction_code: str) -> str:
    """Ferramenta para deletar/apagar uma transação do banco de dados pelo código."""
    user = User.objects.filter(phone=user_phone).first()
    if not user:
        return "Erro: Usuário não encontrado."

    transaction = Transaction.objects.filter(user=user, transaction_code=transaction_code).first()
    if not transaction:
        return f"Desculpe! Nenhuma transação encontrada com o código '{transaction_code}'."
    
    desc = transaction.description
    transaction.delete()
    return f"Transação '{desc}' (ID: {transaction_code}) foi deletada e apagada com sucesso do seu histórico."

def run_delete_agent(user_phone: str, user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Erro: OPENAI_API_KEY não configurada."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    system_prompt = '''Você é o sub-agente de Exclusão Financeira.
Sua única função é deletar transações do banco de dados chamando a ferramenta _delete_transaction.

REGRAS:
1. Para excluir uma transação, é OBRIGATÓRIO informar o código identificador da transação (3 dígitos alfanuméricos, ex: A1B, X9K).
2. Se o usuário NÃO forneceu um código identificador na mensagem: NÃO chame a ferramenta. Responda amigavelmente pedindo o código (ex: "Claro! Para eu excluir, por favor, me informe qual é o código de 3 dígitos da transação que eu te passei quando você registrou.").
3. Se o código foi fornecido, chame a ferramenta _delete_transaction passando o código. Sempre remova espaços e considere caixa alta.
4. Repasse o resultado final da ferramenta de confirmação diretamente para o usuário.'''

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Meu telefone é {user_phone}. A mensagem é: {input}")
    ])

    tools = [_delete_transaction]
    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    try:
        response = agent_executor.invoke({"user_phone": user_phone, "input": user_message})
        return response["output"]
    except Exception as e:
        return f"Desculpe, ocorreu um erro na exclusão: {str(e)}"
