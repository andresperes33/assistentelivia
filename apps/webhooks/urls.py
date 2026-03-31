from django.urls import path
from .views import KirvanoWebhookView, EvolutionWebhookView

urlpatterns = [
    path('kirvano/', KirvanoWebhookView.as_view(), name='kirvano-webhook'),
    path('evolution/', EvolutionWebhookView.as_view(), name='evolution-webhook'),
]
