from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nickname', 'phone', 'create_time']
    search_fields = ['user__username', 'nickname', 'phone']
    list_filter = ['create_time']
