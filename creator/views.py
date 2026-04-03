from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .serializers import CreatorDashboardSerializer, TrackUploadSerializer, PodcastUploadSerializer, StreamSerializer
from core.cloudinary_utils import upload_to_cloudinary
from .models import Song, Podcast, Stream
from livekit import api
import os

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def creator_dashboard_data(request):
    """Supplies the dynamic dashboard analytics payload."""
    from django.db.models import Sum
    from django.utils import timezone
    from .models import Song, MonthlySongStats
    
    now = timezone.now()
    
    # 1. Total Plays across all tracks owned by this creator
    user_songs = Song.objects.filter(uploaded_by=request.user)
    total_plays_val = user_songs.aggregate(Sum('total_play_count'))['total_play_count__sum'] or 0
    
    # 2. Monthly Listeners (Total plays this current month from MonthlySongStats)
    monthly_plays_val = MonthlySongStats.objects.filter(
        song__uploaded_by=request.user,
        year=now.year,
        month=now.month
    ).aggregate(Sum('total_plays'))['total_plays__sum'] or 0
    
    # 3. Top Track (one with most plays)
    top_song = user_songs.order_by('-total_play_count').first()
    top_track_data = None
    if top_song:
        top_track_data = {
            "id": top_song.id,
            "title": top_song.title,
            "artist": top_song.artist,
            "audio_file_url": top_song.audio_file_url,
            "cover_image_url": top_song.cover_image_url,
            "duration": top_song.duration,
            "plays": top_song.total_play_count,
            "likes": 0,
            "upload_date": top_song.created_at.strftime("%Y-%m-%d"),
            "artwork": top_song.cover_image_url
        }
    
    # 4. Recent Tracks
    recent_songs = user_songs.order_by('-created_at')[:3]
    recent_tracks_data = [
        {
            "id": s.id,
            "title": s.title,
            "artist": s.artist,
            "audio_file_url": s.audio_file_url,
            "cover_image_url": s.cover_image_url,
            "duration": s.duration,
            "plays": s.total_play_count,
            "likes": 0,
            "upload_date": s.created_at.strftime("%Y-%m-%d"),
            "artwork": s.cover_image_url
        } for s in recent_songs
    ]

    data_payload = {
        "total_plays": f"{total_plays_val:,}",
        "monthly_listeners": f"{monthly_plays_val:,}",
        "total_revenue": "$0.00", # Placeholder
        "top_track": top_track_data,
        "recent_tracks": recent_tracks_data,
        "recent_activity": [] # Placeholder for now
    }
    
    # We use the serializer but since we're giving it raw dicts it might be simpler to just return Response
    return Response(data_payload, status=status.HTTP_200_OK)


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def manage_track(request, track_id=None):
    """
    Handles track creation (POST) and updates (PUT).
    Files are sent to Cloudinary and the returned URLs are stored in the Song model.
    """
    if request.method == 'POST':
        title = request.data.get('title')
        genre = request.data.get('genre', 'other')
        tags = request.data.get('tags', '')
        audio_file = request.FILES.get('audio_file')
        cover_image = request.FILES.get('cover_image')

        if not title:
            return Response({'error': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not audio_file:
            return Response({'error': 'Audio file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not cover_image:
            return Response({'error': 'Cover artwork is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            audio_result = upload_to_cloudinary(audio_file, resource_type='video', folder='soundr/audio')
            cover_result = upload_to_cloudinary(cover_image, resource_type='image', folder='soundr/covers')
        except Exception as e:
            return Response({'error': f'Cloudinary upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        song = Song.objects.create(
            title=title,
            artist=request.user.username,
            genre=genre,
            tags=tags,
            audio_file_url=audio_result['url'],
            cover_image_url=cover_result['url'],
            uploaded_by=request.user,
        )

        serializer = TrackUploadSerializer(song)
        return Response({
            'message': 'Track uploaded successfully!',
            'track': serializer.data
        }, status=status.HTTP_201_CREATED)

    elif request.method == 'PUT':
        try:
            song = Song.objects.get(id=track_id, uploaded_by=request.user)
        except Song.DoesNotExist:
            return Response({'error': 'Track not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        song.title = request.data.get('title', song.title)
        song.genre = request.data.get('genre', song.genre)
        song.tags = request.data.get('tags', song.tags)

        audio_file = request.FILES.get('audio_file')
        cover_image = request.FILES.get('cover_image')

        try:
            if audio_file:
                audio_result = upload_to_cloudinary(audio_file, resource_type='video', folder='soundr/audio')
                song.audio_file_url = audio_result['url']
            
            if cover_image:
                cover_result = upload_to_cloudinary(cover_image, resource_type='image', folder='soundr/covers')
                song.cover_image_url = cover_result['url']
        except Exception as e:
            return Response({'error': f'Cloudinary upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        song.save()
        serializer = TrackUploadSerializer(song)
        return Response({
            'message': 'Track updated successfully!',
            'track': serializer.data
        }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def manage_podcast(request):
    """
    Handles podcast creation.
    Files are sent to Cloudinary and the returned URLs are stored in the Podcast model.
    """
    title = request.data.get('title')
    description = request.data.get('description', '')
    category = request.data.get('category', 'other')
    visibility = request.data.get('visibility', 'public')
    audio_file = request.FILES.get('audio_file')
    cover_image = request.FILES.get('cover_image')

    if not title:
        return Response({'error': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not audio_file:
        return Response({'error': 'Audio file is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not cover_image:
        return Response({'error': 'Cover artwork is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        audio_result = upload_to_cloudinary(audio_file, resource_type='video', folder='soundr/podcasts/audio')
        cover_result = upload_to_cloudinary(cover_image, resource_type='image', folder='soundr/podcasts/covers')
    except Exception as e:
        return Response({'error': f'Cloudinary upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    podcast = Podcast.objects.create(
        title=title,
        description=description,
        category=category,
        visibility=visibility,
        audio_file_url=audio_result['url'],
        cover_image_url=cover_result['url'],
        uploaded_by=request.user,
    )

    serializer = PodcastUploadSerializer(podcast)
    return Response({
        'message': 'Podcast uploaded successfully!',
        'podcast': serializer.data
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_livekit_token(request):
    """
    Generates a LiveKit Access Token for a podcast live session.
    """
    room_name = request.data.get('room', f"live_{request.user.username}_{request.user.id}")
    participant_name = request.user.username

    # Keys would normally be securely read from .env
    api_key = os.getenv('LIVEKIT_API_KEY', 'devkey')
    api_secret = os.getenv('LIVEKIT_API_SECRET', 'secret')
    print(api_key)
    
    # We construct the token manually granting them broadcast publishing capability
    token = api.AccessToken(api_key, api_secret) \
        .with_identity(participant_name) \
        .with_name(participant_name) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_publish_data=True,
            can_subscribe=True,
        ))

    return Response({
        "token": token.to_jwt(),
        "room": room_name,
        "url": os.getenv('LIVEKIT_URL', 'wss://your-livekit-url')
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_stream(request):
    """
    Creates or reactivates a Stream record when a creator goes live.
    Called immediately after generate_livekit_token succeeds on the frontend.
    """
    title = request.data.get('title', f"{request.user.username}'s Live Session")
    room_name = request.data.get('room', f"live_{request.user.username}_{request.user.id}")

    # Upsert — reuse existing room if user goes live again
    stream, _ = Stream.objects.update_or_create(
        host=request.user,
        room_name=room_name,
        defaults={'title': title, 'is_live': True}
    )
    serializer = StreamSerializer(stream)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_stream(request):
    """
    Marks the creator's active stream as offline.
    """
    room_name = request.data.get('room')
    try:
        stream = Stream.objects.get(host=request.user, room_name=room_name)
        stream.is_live = False
        stream.save()
        return Response({'message': 'Stream ended.'}, status=status.HTTP_200_OK)
    except Stream.DoesNotExist:
        return Response({'error': 'Stream not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_active_streams(request):
    """
    Returns all currently live streams — used by the Discover page.
    """
    streams = Stream.objects.filter(is_live=True).select_related('host').order_by('-created_at')
    serializer = StreamSerializer(streams, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
