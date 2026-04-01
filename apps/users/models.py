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


class UserContext(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='context')
    last_action = models.CharField(max_length=100, null=True, blank=True)
    pending_data = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Context for {self.user.name}"
