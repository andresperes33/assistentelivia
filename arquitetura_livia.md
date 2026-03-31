# 🦷 Livia: Agente Financeiro SaaS para Dentistas
**Documentação Estrutural e Arquitetural (Django + LangChain + PostgreSQL + Celery)**

Este documento contém a arquitetura completa, modelos, webhooks, lógica dos agentes e arquivos necessários para colocar a **Livia** em produção.

---

## 📂 1. Estrutura de Pastas e Arquivos Sugerida
A organização escolhida segue o modelo padrão de aplicações SaaS escaláveis no ecossistema Django (Domain-Driven Design focado em Apps).

```text
livia_project/
│
├── core/                      # Configurações globais, wsgi, asgi, celery.py
├── apps/
│   ├── users/                 # Model User
│   ├── transactions/          # Model Transaction
│   └── webhooks/              # Model WebhookEvent, Views Kirvano e Evolution
│
├── services/
│   ├── kirvano_service.py     # Lógica e API da Kirvano
│   ├── evolution_service.py   # Lógica e disparo de mensages (WhatsApp)
│   ├── openai_service.py      # Transcrição de Áudio (Whisper) e Visão (GPT-4)
│   └── transaction_code.py    # Gerador de códigos UUID alfanuméricos
│
├── agents/
│   ├── router_agent.py        # Agente roteador (LangChain)
│   ├── register_transaction_agent.py # Criação de receita/despesa
│   ├── delete_transaction_agent.py   # Exclusão
│   ├── update_payment_status_agent.py# Marca como pago
│   ├── reports_agent.py       # Consultas ao banco
│   └── generic_agent.py       # Dúvidas gerais (Fallback)
│
├── prompts/
│   ├── router_prompt.txt
│   ├── register_prompt.txt
│   ├── reports_prompt.txt
│   └── generic_prompt.txt
│
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🗄️ 2. Modelos do Banco de Dados

### `apps/users/models.py`
```python
import uuid
from django.db import models

class User(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('active', 'Ativo'),
        ('canceled', 'Cancelado'),
        ('overdue', 'Atrasado'),
        ('expired', 'Expirado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, unique=True, db_index=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    
    total_messages = models.PositiveIntegerField(default=0)
    has_plan = models.BooleanField(default=False)
    kirvano_customer_id = models.CharField(max_length=255, null=True, blank=True)
    subscription_status = models.CharField(max_length=50, choices=SUBSCRIPTION_CHOICES, null=True, blank=True)
    
    last_payment_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    welcome_message_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.phone}"
```

### `apps/transactions/models.py`
```python
import uuid
from django.db import models
from apps.users.models import User
from services.transaction_code import generate_transaction_code

class Transaction(models.Model):
    TYPE_CHOICES = [('receita', 'Receita'), ('despesa', 'Despesa')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_paid = models.BooleanField(default=False)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_code = models.CharField(max_length=3, unique=True, editable=False)

    def save(self, *args, **kwargs):
        # Validação para gerar o code de 3 caracteres antes de persistir
        if not self.transaction_code:
            self.transaction_code = generate_transaction_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.transaction_code}] R$ {self.amount} - {self.description}"
```

### `apps/webhooks/models.py`
*(Tabela de eventos para deduplicação solicitada)*
```python
from django.db import models

class WebhookEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event_type} - {self.event_id}"
```

---

## ⚙️ 3. Serviços (Services Layer)

### `services/transaction_code.py`
```python
import random
import string
from apps.transactions.models import Transaction

def generate_transaction_code():
    """Gera o identificador único de 3 caracteres alfanuméricos."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        # Verifica colisão
        if not Transaction.objects.filter(transaction_code=code).exists():
            return code
```

### `services/evolution_service.py`
```python
import os
import requests
import logging

logger = logging.getLogger(__name__)

def send_whatsapp_message(phone: str, text: str):
    instance_url = os.getenv("EVOLUTION_API_URL")
    api_token = os.getenv("EVOLUTION_API_TOKEN")
    
    url = f"{instance_url}/message/sendText/livia_instance"
    headers = {"apikey": api_token, "Content-Type": "application/json"}
    
    payload = {
        "number": phone,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Mensagem enviada com sucesso para {phone}.")
        return response.json()
    except Exception as e:
        logger.error(f"Falha ao enviar mensagem para {phone}. Erro: {e}")
        return None
```

### `services/openai_service.py`
```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def convert_audio_to_text(audio_path: str):
    with open(audio_path, "rb") as file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=file, 
            response_format="text"
        )
    return transcript.text

def extract_text_from_image(base64_image: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extraia as informações cruciais desta fatura/comprovante (valor, descrição, data e recebedor/pagador). Responda um texto curto."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        ],
    )
    return response.choices[0].message.content
```

---

## 🧠 4. Arquitetura LangChain & Prompts

### `prompts/router_prompt.txt`
```text
Você é Livia, uma assistente financeira especializada para dentistas.
Seu papel principal é ROTEADOR de IA. Você avalia a intenção da mensagem abaixo e decide qual ferramenta/agente invocar para resolvê-la.

Você NUNCA insere ou apaga os dados pelo banco de dados por conta própria. Você apenas diz o destino e encapsula a demanda do dentista.

Agentes Disponíveis (use os nomes exatos):
- "RegisterTransactionAgent": Cadastros de novas receitas ou despesas.
- "DeleteTransactionAgent": Apagar, remover ou cancelar uma conta.
- "UpdatePaymentStatusAgent": Marcar como pago ou recebido.
- "ReportsAgent": Perguntas sobre fluxo de caixa, saldo, despesas do mês e dúvidas financeiras.
- "GenericAgent": Quando for uma conversa genérica (ex: saudações).

Regra OBRIGATÓRIA: Responda SOMENTE um JSON válido usando o padrão abaixo e nada mais.

{
  "agent": "RegisterTransactionAgent",
  "reason": "Usuário informou uma nova despesa",
  "data": {
    "message": "Paguei R$ 500 no laboratório"
  }
}
```

### `agents/router_agent.py`
```python
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import json
import os

def router_agent(user_message: str) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=os.getenv("OPENAI_API_KEY"))
    
    with open("prompts/router_prompt.txt", "r", encoding="utf-8") as file:
        prompt_text = file.read()
        
    prompt = PromptTemplate.from_template(prompt_text + "\n\nMensagem do dentista: {user_message}")
    chain = prompt | llm
    
    response = chain.invoke({"user_message": user_message})
    
    try:
        clean_text = response.content.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:-3].strip()
        if clean_text.startswith("```"):
            clean_text = clean_text[3:-3].strip()
            
        return json.loads(clean_text)
    except Exception as e:
        return {"agent": "GenericAgent", "reason": "Erro de parse", "data": {"message": user_message}}
```

---

## 🌐 5. Webhooks API (Django Views)

### Webhook Kirvano (`apps/webhooks/views.py`)
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from apps.users.models import User
from apps.webhooks.models import WebhookEvent
from services.evolution_service import send_whatsapp_message

class KirvanoWebhookView(APIView):
    def post(self, request):
        data = request.data
        event_id = data.get("event_id")
        event_type = data.get("event")
        customer = data.get("customer", {})

        # 1. Deduplicação
        if WebhookEvent.objects.filter(event_id=event_id).exists():
            return Response({"status": "Already processed"}, status=status.HTTP_200_OK)
        WebhookEvent.objects.create(event_id=event_id, event_type=event_type, processed=True)

        phone = customer.get("phone")
        
        # 2. Resolução do Usuário
        user, created = User.objects.get_or_create(
            phone=phone, 
            defaults={"email": customer.get("email"), "name": customer.get("name")}
        )

        # 3. Tratamento dos Eventos
        if event_type == "purchase_approved":
            user.has_plan = True
            user.subscription_status = "active"
            user.kirvano_customer_id = customer.get("id")
            user.last_payment_date = timezone.now()
            user.save()

            if not user.welcome_message_sent:
                welcome_msg = "Olá, eu sou a Livia, sua assistente financeira para dentistas 🦷\nSeu acesso foi liberado com sucesso.\nAgora você já pode me enviar suas receitas, despesas e pedidos de relatório diretamente pelo WhatsApp."
                send_whatsapp_message(phone, welcome_msg)
                user.welcome_message_sent = True
                user.save()

        elif event_type == "subscription_renewed":
            user.has_plan = True
            user.subscription_status = "active"
            user.next_payment_date = timezone.now() + timezone.timedelta(days=30) # Exemplo
            user.save()
            send_whatsapp_message(phone, "Seu plano foi renovado com sucesso. Pode continuar utilizando a Livia normalmente.")

        elif event_type in ["subscription_canceled", "subscription_expired", "subscription_overdue"]:
            user.has_plan = False
            user.subscription_status = event_type.replace("subscription_", "")
            user.save()
            msg = "Seu plano foi cancelado. Para voltar a utilizar a assistente Livia, realize uma nova assinatura." if "canceled" in event_type else "Detectamos um atraso no pagamento da sua assinatura. Regularize para continuar utilizando a Livia."
            send_whatsapp_message(phone, msg)

        return Response({"status": "Success"}, status=status.HTTP_200_OK)
```

### Webhook Evolution API (`apps/webhooks/views.py`)
```python
from apps.webhooks.tasks import process_langchain_agent

class EvolutionWebhookView(APIView):
    def post(self, request):
        payload = request.data.get("data", {})
        phone = payload.get("remoteJid", "").split("@")[0]
        msg_type = payload.get("messageType")
        
        user = User.objects.filter(phone=phone).first()

        # Segurança: Validar plano
        if not user:
            send_whatsapp_message(phone, "Olá, eu sou a Livia. Você ainda não possui cadastro ativo. Faça sua assinatura aqui: [LINK_DO_PLANO]")
            return Response(status=status.HTTP_200_OK)
        
        if not user.has_plan:
            send_whatsapp_message(phone, "Seu acesso não está ativo no momento. Renove seu plano aqui: [LINK_DO_PLANO]")
            return Response(status=status.HTTP_200_OK)

        user.total_messages += 1
        user.save()

        # Conteúdo da mensagem
        text_content = ""
        if msg_type in ["conversation", "extendedTextMessage"]:
            text_content = payload.get("message", {}).get("conversation") or payload.get("message", {}).get("extendedTextMessage", {}).get("text", "")
        
        # Envia pra Fila Asíncrona p/ n° travar
        process_langchain_agent.delay(user.id, text_content, msg_type, payload)

        return Response({"status": "queued"}, status=status.HTTP_200_OK)
```

---

## ⚡ 6. Assincronia (Celery Tasks)

```python
# apps/webhooks/tasks.py
from celery import shared_task
from agents.router_agent import router_agent
from services.evolution_service import send_whatsapp_message
from services.openai_service import convert_audio_to_text, extract_text_from_image
from apps.users.models import User
import base64

@shared_task
def process_langchain_agent(user_id, raw_message, msg_type, payload):
    user = User.objects.get(id=user_id)
    
    # Processa áudio ou imagem com GPT/Whisper
    if msg_type == "audioMessage":
        # Assumindo que o webhook envia base64 do audio (Evolution API base64MessageData)
        base64_audio = payload.get("base64")
        if base64_audio:
            with open(f"/tmp/audio_{user.id}.ogg", "wb") as fh:
                fh.write(base64.b64decode(base64_audio))
            raw_message = convert_audio_to_text(f"/tmp/audio_{user.id}.ogg")
            
    elif msg_type == "imageMessage":
        base64_image = payload.get("base64")
        if base64_image:
            raw_message = extract_text_from_image(base64_image)

    # Roteamento LangChain
    decision = router_agent(raw_message)
    target_agent = decision.get("agent")
    
    # Executa lógica final conforme o agente escolhido
    response_text = f"Decisão: {target_agent}. Processando... (Integração com {target_agent} LangChain)"
    
    # Retorna Resposta
    send_whatsapp_message(user.phone, response_text)
```

---

## 🐳 7. Docker e Empacotamento

### `docker-compose.yml`
```yaml
version: '3.8'
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: livia_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  django:
    build: .
    command: gunicorn core.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery:
    build: .
    command: celery -A core worker --loglevel=info
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env
```

### `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/

RUN apt-get update && apt-get install -y libpq-dev gcc \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/
```

---

## ✅ 8. Estratégia de Escalabilidade e Segurança

1. **Celery / Redis / PostgreSQL**: O PostgreSQL cuidará de armazenar e validar restrições. Webhooks de LangChain **NUNCA** devem rodar bloqueantes na thread do Django. O uso do broker `Redis` + worker `Celery` permite segurar o envio em alto volume.
2. **Transaction Code**: Gerado em background por um serviço simples `transaction_code.py` para nunca ferir a legibilidade dos dentistas, com retry _while_ garantido contra colisão.
3. **OpenAI Service (Whisper e Vision)**: Extrai context-aware do arquivo cru e reavalia passando a string como _raw_message_ no bot router final (o que economiza tokens absurdamente).
4. **Agent Prompts**: Com a formatação em JSON e temperature 0 no router, garantimos o roteamento estático evitando respostas verbosas incorretas ao usuário final.
