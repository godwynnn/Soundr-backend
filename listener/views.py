from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from creator.models import Song, Stream, Podcast, PodcastLike, PodcastComment
from .serializers import SongSerializer, PodcastSerializer, PodcastCommentSerializer
from livekit import api
import os
from listener.models import FollowedArtist,Playlist,UserLibrary
from pgvector.django import CosineDistance
from creator.embeddingUtils import get_embedding
from django.conf import settings

@api_view(['GET'])
@permission_classes([AllowAny])
def list_public_podcasts(request):
    """
    Fetches all public podcasts for discovery.
    """
    podcasts = Podcast.objects.filter(visibility='public').order_by('-created_at')
    return Response(PodcastSerializer(podcasts, many=True).data)

@api_view(['GET'])
@permission_classes([AllowAny])
def landing_page_data(request):
    """
    Fetches real data for the landing page:
    - Featured songs (Hero)
    - Trending songs (Most Played)
    - Recently added songs
    """
    featured_songs = Song.objects.filter(is_featured=True)[:5]
    # 'Trending' now means most played
    trending_songs = Song.objects.all().order_by('-total_play_count')[:15]
    recently_added = Song.objects.order_by('-created_at')[:15]

    return Response({
        "featured": SongSerializer(featured_songs, many=True).data,
        "trending": SongSerializer(trending_songs, many=True).data,
        "latest": SongSerializer(recently_added, many=True).data,
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def song_detail_data(request, song_id):
    """Fetches real song detail and related tracks."""
    song = get_object_or_404(Song, id=song_id)
    
    # Use serializer with request context to get 'is_liked' and 'likes_count'
    serializer = SongSerializer(song, context={'request': request})
    song_data = serializer.data
    
    # Simple logic for 'up next': different songs in the same genre
    up_next = Song.objects.filter(genre=song.genre).exclude(id=song.id)[:5]
    
    # Mock comments for now unless a Comment model is requested
    comments = [
        {
            "id": 1, 
            "user": "Jay Design",
            "avatar_text": "JD",
            "time_ago": "2 hours ago",
            "text": f"That bass drop in {song.title} literally changed my life.!",
            "likes": 24
        },
        {
            "id": 2, 
            "user": "NeonRider",
            "avatar_text": "NR",
            "time_ago": "1 day ago",
            "text": "Getting major Blade Runner vibes from this artwork.",
            "likes": 8
        }
    ]

    return Response({
        **song_data,
        "up_next": SongSerializer(up_next, many=True).data,
        "comments": comments,
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def increment_play(request, song_id):
    """
    Increments the total play count of a song and updates its MonthlySongStats.
    """
    from creator.models import MonthlySongStats
    from django.utils import timezone
    
    song = get_object_or_404(Song, id=song_id)
    song.total_play_count += 1
    song.save()
    
    # Update monthly stats
    now = timezone.now()
    stats, created = MonthlySongStats.objects.get_or_create(
        song=song,
        year=now.year,
        month=now.month
    )
    stats.total_plays += 1
    # For now, unique_listeners could be handled by session/IP tracking if needed,
    # but for simplicity we increment it once per session or similar.
    # To strictly follow "unique_listeners", we'd need a separate log of unique ids.
    # For this task, we increment total_plays as requested.
    stats.save()
    
    return Response({
        "message": "Play counted",
        "total_play_count": song.total_play_count,
        "monthly_plays": stats.total_plays
    })


vector_search_supported = True  # or your actual check for vector search support




@api_view(['GET'])
@permission_classes([AllowAny])
def search_songs(request):
    """
    Search songs using vector embeddings if supported; fallback to traditional search.
    """
    query = request.query_params.get('q', '')
    if len(query) < 2:
        return Response([])

    vector_results = []

    # # ✅ Only attempt vector search if DB supports it
    # if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3' and vector_search_supported:
    #     query_embedding = get_embedding(query)
    #     vector_results = list(
    #         Song.objects
    #         .annotate(distance=CosineDistance("embedding", query_embedding))
    #         .order_by("distance")
    #     )

    # if vector_results:
    #     return Response(SongSerializer(vector_results, many=True).data)

    # Fallback: traditional query search
    from django.db.models import Q
    traditional_results = Song.objects.filter(
        Q(title__icontains=query) | Q(artist__icontains=query)
    )[:10]

    return Response(SongSerializer(traditional_results, many=True).data)





@api_view(['GET'])
@permission_classes([AllowAny])
def list_songs_by_type(request, category):
    """
    Returns a full list of songs for a specific category:
    - trending: Most played
    - latest: Newest
    - featured: Hand-picked highlights
    """
    if category == 'trending':
        songs = Song.objects.all().order_by('-total_play_count')
    elif category == 'latest':
        songs = Song.objects.all().order_by('-created_at')
    elif category == 'featured':
        songs = Song.objects.filter(is_featured=True)
    else:
        # Fallback to all songs
        songs = Song.objects.all()

    # In a real app, we'd add pagination here (e.g. using rest_framework.pagination)
    # For now, we return them all as requested for the 'View All' page.
    return Response(SongSerializer(songs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_stream_token(request):
    """
    Generates a subscribe-only LiveKit token so a listener can join a live session.
    They can hear/watch the host but cannot publish their own tracks.
    """
    room_name = request.data.get('room')
    if not room_name:
        return Response({'error': 'Room name is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Verify the stream actually exists and is live
    try:
        stream = Stream.objects.get(room_name=room_name, is_live=True)
    except Stream.DoesNotExist:
        return Response({'error': 'This stream is no longer live.'}, status=status.HTTP_404_NOT_FOUND)

    api_key = os.getenv('LIVEKIT_API_KEY', 'devkey')
    api_secret = os.getenv('LIVEKIT_API_SECRET', 'secret')

    token = api.AccessToken(api_key, api_secret) \
        .with_identity(request.user.username) \
        .with_name(request.user.username) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=False,
            can_publish_data=False,
            can_subscribe=True,
        ))

    return Response({
        "token": token.to_jwt(),
        "room": room_name,
        "stream_title": stream.title,
        "host": stream.host.username,
        "url": os.getenv('LIVEKIT_URL', 'wss://your-livekit-url')
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def podcast_detail_data(request, podcast_id):
    """Fetches podcast detail, likes count, and comments."""
    podcast = get_object_or_404(Podcast, id=podcast_id)
    comments = podcast.comments.all().order_by('-created_at')
    
    return Response({
        "podcast": PodcastSerializer(podcast, context={'request': request}).data,
        "comments": PodcastCommentSerializer(comments, many=True).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_podcast_like(request, podcast_id):
    """Liking/Unliking a podcast."""
    podcast = get_object_or_404(Podcast, id=podcast_id)
    like_qs = PodcastLike.objects.filter(user=request.user, podcast=podcast)
    
    if like_qs.exists():
        like_qs.delete()
        liked = False
    else:
        PodcastLike.objects.create(user=request.user, podcast=podcast)
        liked = True
        
    return Response({
        "liked": liked,
        "likes_count": podcast.likes.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_podcast_comment(request, podcast_id):
    """Posting a comment on a podcast."""
    podcast = get_object_or_404(Podcast, id=podcast_id)
    text = request.data.get('text')
    
    if not text:
        return Response({"error": "Comment text is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    comment = PodcastComment.objects.create(
        user=request.user,
        podcast=podcast,
        text=text
    )
    
    return Response(PodcastCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_library_all(request):
    """
    Unified view for the user library.
    Returns:
    - liked_songs (saved_songs)
    - playlists (owned by user and saved)
    - followed_artists
    """
    library, created = UserLibrary.objects.get_or_create(user=request.user)
    
    # Serializers
    from .serializers import (
        SongSerializer, PlaylistSerializer, FollowedArtistSerializer
    )
    
    liked_songs = library.saved_songs.all()
    # Playlists: User's own + saved playlists
    owned_playlists = Playlist.objects.filter(user=request.user)
    saved_playlists = library.saved_playlists.all()
    all_playlists = (owned_playlists | saved_playlists).distinct()
    
    followed_artists = FollowedArtist.objects.filter(user=request.user)
    
    return Response({
        "liked_songs": SongSerializer(liked_songs, many=True).data,
        "playlists": PlaylistSerializer(all_playlists, many=True).data,
        "followed_artists": FollowedArtistSerializer(followed_artists, many=True).data,
        "recent_downloads": [] # Mocked for now as requested
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_song_like(request, song_id):
    """Liking/Unliking a song."""
    from creator.models import SongLike
    song = get_object_or_404(Song, id=song_id)
    like_qs = SongLike.objects.filter(user=request.user, song=song)
    
    if like_qs.exists():
        like_qs.delete()
        liked = False
        # Also remove from UserLibrary saved_songs for consistency
        library, _ = UserLibrary.objects.get_or_create(user=request.user)
        library.saved_songs.remove(song)
    else:
        SongLike.objects.create(user=request.user, song=song)
        liked = True
        # Also add to UserLibrary saved_songs for consistency
        library, _ = UserLibrary.objects.get_or_create(user=request.user)
        library.saved_songs.add(song)
        
    return Response({
        "liked": liked,
        "likes_count": song.likes.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hype_song(request, song_id):
    """
    Increment hype count for a song by consuming 1 Hype Point from the user's wallet.
    """
    from payment.models import Wallet, Transaction
    from django.db import transaction as db_transaction
    import uuid

    song = get_object_or_404(Song, id=song_id)
    
    if song.uploaded_by == request.user:
        return Response({"error": "You cannot hype your own tracks."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with db_transaction.atomic():
            # Get user wallet
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            
            if wallet.hype_points < 1:
                return Response({"error": "Insufficient Hype Points. Please visit the Earnings Dashboard to buy more."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Deduct point
            wallet.hype_points -= 1
            wallet.save()
            
            # Increment song hype
            song.hype_count += 1
            song.save()
            
            # Record Transaction
            Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                amount=0,
                currency="NGN",
                transaction_type="hype_spend",
                payment_method="wallet",
                status="success",
                reference=f"hype-{uuid.uuid4().hex[:12]}",
                description=f"Used 1 Hype Point on {song.title} by {song.artist}"
            )
            
            return Response({
                "message": f"Successfully hyped {song.title}!",
                "hype_count": song.hype_count,
                "remaining_hype_points": wallet.hype_points
            }, status=status.HTTP_200_OK)

    except Wallet.DoesNotExist:
        return Response({"error": "Wallet not found. Please visit the Earnings page to initialize your wallet."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_follow_artist(request, artist_id):
    """ Toggles follow/unfollow for an artist. """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    artist = get_object_or_404(User, id=artist_id)
    
    if artist == request.user:
        return Response({"error": "You cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)
        
    follow_qs = FollowedArtist.objects.filter(user=request.user, artist=artist)
    
    if follow_qs.exists():
        follow_qs.delete()
        followed = False
        message = f"Unfollowed {artist.username}"
    else:
        FollowedArtist.objects.create(user=request.user, artist=artist)
        followed = True
        message = f"Following {artist.username}"
        
    return Response({
        "followed": followed,
        "message": message,
        "artist_id": artist_id
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([AllowAny])
def trending_hype_chart(request):
    """
    Returns songs ordered by hype_count, optionally filtered by genre.
    """
    genre = request.query_params.get('genre', 'All')
    
    songs = Song.objects.all().order_by('-hype_count')
    
    if genre and genre != 'All':
        # Simple case-insensitive match for genre
        songs = songs.filter(genre__iexact=genre)
    
    # Return top 50 ranked songs
    songs = songs[:50]
    
    return Response(SongSerializer(songs, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def trending_hype_chart(request):
    """
    Returns songs ordered by hype_count, optionally filtered by genre.
    """
    genre = request.query_params.get('genre', 'All')
    
    songs = Song.objects.all().order_by('-hype_count')
    
    if genre and genre != 'All':
        songs = songs.filter(genre__iexact=genre)
    
    songs = songs[:50]
    
    return Response(SongSerializer(songs, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def keep_alive(request):
    """
    Simple endpoint to keep the backend live.
    """
    print("keep soundr live")
    return Response({"status": "keep soundr live"}, status=status.HTTP_200_OK)
