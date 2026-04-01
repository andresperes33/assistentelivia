from .models import User, UserContext

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('phone', 'name', 'has_plan', 'subscription_status', 'total_messages')
    search_fields = ('phone', 'name', 'email')
    list_filter = ('has_plan', 'subscription_status')

@admin.register(UserContext)
class UserContextAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_action', 'updated_at')
