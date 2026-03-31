from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import json
import os
from pathlib import Path

def router_agent(user_message: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"agent": "GenericAgent", "reason": "No API Key", "data": {"message": user_message}}

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
    
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "router_prompt.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as file:
            prompt_text = file.read()
    except Exception:
        prompt_text = "Retorne JSON mockado para GenericAgent."
        
    prompt = PromptTemplate.from_template(prompt_text + "\n\nMensagem do dentista: {user_message}")
    chain = prompt | llm
    
    try:
        response = chain.invoke({"user_message": user_message})
        clean_text = response.content.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:-3].strip()
        if clean_text.startswith("```"):
            clean_text = clean_text[3:-3].strip()
            
        return json.loads(clean_text)
    except Exception as e:
        return {"agent": "GenericAgent", "reason": "Erro de parse", "data": {"message": user_message}}
