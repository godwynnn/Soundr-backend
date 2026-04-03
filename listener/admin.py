from django.contrib import admin
from .models import UserLibrary

@admin.register(UserLibrary)
class UserLibraryAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__email',)
    filter_horizontal = ('saved_songs',)
