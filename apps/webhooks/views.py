from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from apps.users.models import User
from apps.webhooks.models import WebhookEvent
from services.evolution_service import send_whatsapp_message
from apps.webhooks.tasks import process_langchain_agent

class KirvanoWebhookView(APIView):
    def post(self, request):
        data = request.data
        event_id = data.get("event_id")
        event_type = data.get("event")
        customer = data.get("customer", {})

        if WebhookEvent.objects.filter(event_id=event_id).exists():
            return Response({"status": "Already processed"}, status=status.HTTP_200_OK)
        WebhookEvent.objects.create(event_id=event_id, event_type=event_type, processed=True)

        phone = customer.get("phone")
        
        user, created = User.objects.get_or_create(
            phone=phone, 
            defaults={"email": customer.get("email"), "name": customer.get("name")}
        )

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
            user.next_payment_date = timezone.now() + timezone.timedelta(days=30)
            user.save()
            send_whatsapp_message(phone, "Seu plano foi renovado com sucesso. Pode continuar utilizando a Livia normalmente.")

        elif event_type in ["subscription_canceled", "subscription_expired", "subscription_overdue"]:
            user.has_plan = False
            user.subscription_status = event_type.replace("subscription_", "")
            user.save()
            msg = "Seu plano foi cancelado. Para voltar a utilizar a assistente Livia, realize uma nova assinatura." if "canceled" in event_type else "Detectamos um atraso no pagamento da sua assinatura. Regularize para continuar utilizando a Livia."
            send_whatsapp_message(phone, msg)

        return Response({"status": "Success"}, status=status.HTTP_200_OK)

class EvolutionWebhookView(APIView):
    def post(self, request):
        payload = request.data.get("data", {})
        phone = payload.get("remoteJid", "").split("@")[0]
        msg_type = payload.get("messageType")
        
        user = User.objects.filter(phone=phone).first()

        if not user:
            send_whatsapp_message(phone, "Olá, eu sou a Livia. Você ainda não possui cadastro ativo. Faça sua assinatura aqui: [LINK_DO_PLANO]")
            return Response(status=status.HTTP_200_OK)
        
        if not user.has_plan:
            send_whatsapp_message(phone, "Seu acesso não está ativo no momento. Renove seu plano aqui: [LINK_DO_PLANO]")
            return Response(status=status.HTTP_200_OK)

        user.total_messages += 1
        user.save()

        text_content = ""
        if msg_type in ["conversation", "extendedTextMessage"]:
            text_content = payload.get("message", {}).get("conversation") or payload.get("message", {}).get("extendedTextMessage", {}).get("text", "")
        
        process_langchain_agent.delay(user.id, text_content, msg_type, payload)

        return Response({"status": "queued"}, status=status.HTTP_200_OK)
