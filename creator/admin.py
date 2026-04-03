from django.contrib import admin
from .models import Song, MonthlySongStats, Podcast, Stream, PodcastLike, PodcastComment,SongLike

admin.site.register([MonthlySongStats,SongLike])

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist', 'genre', 'uploaded_by', 'created_at', 'is_featured', 'is_trending')
    list_filter = ('genre', 'is_featured', 'is_trending', 'created_at')
    search_fields = ('title', 'artist', 'tags')
    readonly_fields = ('created_at',)

@admin.register(Podcast)
class PodcastAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'visibility', 'uploaded_by', 'created_at', 'total_play_count')
    list_filter = ('category', 'visibility', 'created_at')
    search_fields = ('title', 'description', 'uploaded_by__username')
    readonly_fields = ('created_at',)

@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = ('title', 'host', 'room_name', 'is_live', 'created_at')
    list_filter = ('is_live', 'created_at')
    search_fields = ('title', 'host__username', 'room_name')
    readonly_fields = ('created_at',)

@admin.register(PodcastLike)
class PodcastLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'podcast', 'created_at')

@admin.register(PodcastComment)
class PodcastCommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'podcast', 'text', 'created_at')
