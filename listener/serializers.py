from rest_framework import serializers
from .models import UserLibrary, Playlist, FollowedArtist
from creator.models import Song, Podcast, PodcastComment, PodcastLike

class SongSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    is_following_artist = serializers.SerializerMethodField()

    class Meta:
        model = Song
        fields = [
            'id', 'title', 'artist', 'genre', 'tags', 'duration', 
            'cover_image_url', 'audio_file_url', 'uploaded_by', 
            'is_featured', 'is_trending', 'total_play_count', 'hype_count', 
            'created_at', 'is_liked', 'likes_count', 'is_following_artist'
        ]

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_is_following_artist(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # uploaded_by is the user ID of the artist
            return FollowedArtist.objects.filter(user=request.user, artist=obj.uploaded_by).exists()
        return False

class PodcastCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = PodcastComment
        fields = ['id', 'username', 'text', 'created_at']

class PodcastSerializer(serializers.ModelSerializer):
    creator = serializers.CharField(source='uploaded_by.username', read_only=True)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Podcast
        fields = [
            'id', 'title', 'description', 'category', 'visibility', 
            'cover_image_url', 'audio_file_url', 'duration', 'creator', 
            'total_play_count', 'created_at', 'likes_count', 'comments_count', 'is_liked'
        ]

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

class PlaylistSerializer(serializers.ModelSerializer):
    track_count = serializers.SerializerMethodField()
    class Meta:
        model = Playlist
        fields = ['id', 'title', 'description', 'cover_image_url', 'track_count', 'created_at']
    
    def get_track_count(self, obj):
        return obj.songs.count()

class FollowedArtistSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source='artist.username', read_only=True)
    class Meta:
        model = FollowedArtist
        fields = ['id', 'artist_name', 'created_at']

class UserLibrarySerializer(serializers.ModelSerializer):
    saved_songs = SongSerializer(many=True, read_only=True)
    saved_playlists = PlaylistSerializer(many=True, read_only=True)
    class Meta:
        model = UserLibrary
        fields = ['id', 'saved_songs', 'saved_playlists']
