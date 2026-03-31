from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_code', 'user', 'amount', 'type', 'category', 'created_at', 'is_paid')
    list_filter = ('type', 'category', 'created_at', 'is_paid')
    search_fields = ('user__phone', 'description', 'transaction_code')
