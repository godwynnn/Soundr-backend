from rest_framework import serializers
from .models import Song, Podcast, Stream

class TrackSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    plays = serializers.IntegerField()
    likes = serializers.IntegerField()
    upload_date = serializers.CharField()
    artwork = serializers.CharField()

class ActivitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()
    message = serializers.CharField()
    time = serializers.CharField()
    icon = serializers.CharField()

class CreatorDashboardSerializer(serializers.Serializer):
    total_plays = serializers.CharField()
    monthly_listeners = serializers.CharField()
    total_revenue = serializers.CharField()
    top_track = TrackSummarySerializer()
    recent_tracks = TrackSummarySerializer(many=True)
    recent_activity = ActivitySerializer(many=True)

class TrackUploadSerializer(serializers.ModelSerializer):
    """Handles creation of new songs via the upload form."""
    class Meta:
        model = Song
        fields = ['id', 'title', 'genre', 'tags', 'cover_image_url', 'audio_file_url', 'uploaded_by', 'created_at']
        read_only_fields = ['id', 'uploaded_by', 'created_at']

class PodcastUploadSerializer(serializers.ModelSerializer):
    """Handles creation of new podcasts via the upload form."""
    class Meta:
        model = Podcast
        fields = ['id', 'title', 'description', 'category', 'visibility', 'cover_image_url', 'audio_file_url', 'uploaded_by', 'created_at']
        read_only_fields = ['id', 'uploaded_by', 'created_at']

class StreamSerializer(serializers.ModelSerializer):
    host_username = serializers.CharField(source='host.username', read_only=True)

    class Meta:
        model = Stream
        fields = ['id', 'room_name', 'title', 'host_username', 'is_live', 'created_at']
        read_only_fields = ['id', 'host_username', 'created_at']
