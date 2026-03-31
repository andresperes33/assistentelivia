import random
import string
from django.apps import apps

def generate_transaction_code():
    """Gera o identificador único de 3 caracteres alfanuméricos."""
    Transaction = apps.get_model('transactions', 'Transaction')
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        if not Transaction.objects.filter(transaction_code=code).exists():
            return code
