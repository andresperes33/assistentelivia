from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from apps.transactions.models import Transaction
from apps.users.models import User
import os
from typing import Optional

@tool
def _update_transaction(user_phone: str, transaction_code: str, is_paid: Optional[bool] = None, amount: Optional[float] = None, category: Optional[str] = None, description: Optional[str] = None) -> str:
    """Ferramenta para atualizar os dados de uma transação. Você só precisa preencher os parâmetros que o usuário solicitou mudança (amount, category, description ou is_paid)."""
    user = User.objects.filter(phone=user_phone).first()
    if not user:
        return "Erro: Usuário não encontrado."

    transaction = Transaction.objects.filter(user=user, transaction_code=transaction_code).first()
    if not transaction:
        return f"Desculpe! Nenhuma transação encontrada com o código '{transaction_code}'."
    
    updated_fields = []
    if is_paid is not None:
        transaction.is_paid = is_paid
        updated_fields.append(f"Status={'Pago/Recebido' if is_paid else 'Pendente'}")
    if amount is not None:
        transaction.amount = amount
        updated_fields.append(f"Valor=R${amount:.2f}")
    if category is not None:
        transaction.category = category
        updated_fields.append(f"Categoria={category}")
    if description is not None:
        transaction.description = description
        updated_fields.append(f"Descrição={description}")
        
    if not updated_fields:
        return "Nenhuma alteração foi solicitada."

    transaction.save()
    fields_str = ", ".join(updated_fields)
    return f"Feito! A transação {transaction_code} foi atualizada com sucesso: {fields_str}."

def run_update_agent(user_phone: str, user_message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Erro: OPENAI_API_KEY não configurada."

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    system_prompt = '''Você é o sub-agente de Atualização Financeira.
Sua função é atualizar qualquer dado de uma transação (status de pagamento, valor, categoria ou descrição) recebendo os parâmetros novos através da ferramenta _update_transaction.

REGRAS:
1. Para atualizar, é OBRIGATÓRIO informar o código da transação (3 dígitos alfanuméricos).
2. Se o usuário NÃO forneceu um código identificador, pergunte educadamente: "Certo! Para qual código de 3 letras da transação devo aplicar essa alteração?".
3. Extraia e passe APENAS os campos que o usuário pediu para mudar. Deixe o restante em branco/null na chamada da ferramenta.
4. Repasse o resultado final da ferramenta de forma amigável ao usuário.'''

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Meu telefone é {user_phone}. A mensagem é: {input}")
    ])

    tools = [_update_transaction]
    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    try:
        response = agent_executor.invoke({"user_phone": user_phone, "input": user_message})
        return response["output"]
    except Exception as e:
        return f"Desculpe, ocorreu um erro ao atualizar: {str(e)}"
