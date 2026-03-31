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
        if not self.transaction_code:
            self.transaction_code = generate_transaction_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.transaction_code}] R$ {self.amount} - {self.description}"
