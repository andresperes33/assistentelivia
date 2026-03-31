from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import os

def router_agent(user_message: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"agent": "GenericAgent", "reason": "No API Key", "data": {"message": user_message}}

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key)
    
    system_message = """# AGENTE ROTEADOR INTELIGENTE — SaaS LÍVIA

Você é um agente de **ações financeiras** via WhatsApp para dentistas. Seu trabalho é identificar a intenção do usuário e decidir qual Agente ou Tool Call executar imediatamente.

## ⚠️ REGRA ABSOLUTA DE OUTPUT
Você é um agente de AÇÕES. Responda APENAS um JSON válido.

## 📊 TABELA DE DECISÃO
- "RegisterTransactionAgent": Mensagens de "Ganhei", "Recebi", "Paguei", "Gastei" ou valores em R$.
- "DeleteTransactionAgent": Mensagens pedindo para excluir ou deletar usando um código (ID).
- "UpdateTransactionAgent": Alterar valor, descrição, categoria ou marcar como pago.
- "ReportsAgent": Pedidos de relatório, saldo do mês ou fluxo de caixa.
- "GenericAgent": Saudações básicas (Oi, Tudo bem?) que NÃO falem de dinheiro.

## 🔑 PALAVRAS-CHAVE
Receita: recebi, ganhei, entrou, faturei, lucro, entrada.
Despesa: paguei, gastei, comprei, custo, débito, saiu dinheiro.

## 📋 FORMATO DE RESPOSTA OBRIGATÓRIO (JSON PURO):
{
  "agent": "NOME_DO_AGENTE",
  "reason": "Raciocínio interno resumido",
  "data": { "message": "Texto original" }
}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", "{user_message}"),
    ])
    
    chain = prompt | llm
    
    try:
        # Forçamos o roteamento via código para casos óbvios de ganho/gasto (Blindagem Extra)
        msg_lower = user_message.lower()
        if any(x in msg_lower for x in ["ganhei", "recebi", "paguei", "gastei", "reais", " r$", " r$ "]):
             return {"agent": "RegisterTransactionAgent", "reason": "Filtro de segurança por palavra-chave", "data": {"message": user_message}}

        response = chain.invoke({"user_message": user_message})
        clean_text = response.content.strip()
        
        # Limpezas de Markdown se houver
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
        return json.loads(clean_text)
    except Exception:
        return {"agent": "GenericAgent", "reason": "Default Fallback", "data": {"message": user_message}}
