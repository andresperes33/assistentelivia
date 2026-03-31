from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('phone', 'name', 'has_plan', 'subscription_status', 'total_messages')
    search_fields = ('phone', 'name', 'email')
    list_filter = ('has_plan', 'subscription_status')
