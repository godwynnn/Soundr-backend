from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'is_staff', 'is_active', 'is_creator')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_creator')
    search_fields = ('email', 'username')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('is_creator',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('is_creator',)}),
    )
