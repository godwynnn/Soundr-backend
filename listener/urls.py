from .views import (
    landing_page_data, song_detail_data, increment_play, 
    search_songs, list_songs_by_type, join_stream_token, 
    list_public_podcasts, podcast_detail_data, toggle_podcast_like, add_podcast_comment,
    user_library_all, toggle_song_like, hype_song, toggle_follow_artist, keep_alive
)
from django.urls import path
urlpatterns = [
    path('landing/', landing_page_data, name='landing-page'),
    path('songs/<int:song_id>/', song_detail_data, name='song-detail'),
    path('songs/<int:song_id>/play/', increment_play, name='increment-play'),
    path('songs/list/<str:category>/', list_songs_by_type, name='list-songs-by-type'),
    path('search/', search_songs, name='search-songs'),
    path('podcasts/', list_public_podcasts, name='list-public-podcasts'),
    path('podcasts/<int:podcast_id>/', podcast_detail_data, name='podcast-detail'),
    path('podcasts/<int:podcast_id>/like/', toggle_podcast_like, name='podcast-like'),
    path('podcasts/<int:podcast_id>/comment/', add_podcast_comment, name='podcast-comment'),
    path('streams/join-token/', join_stream_token, name='join-stream-token'),
    path('library/', user_library_all, name='user-library-all'),
    path('songs/<int:song_id>/like/', toggle_song_like, name='song-like'),
    path('songs/<int:song_id>/hype/', hype_song, name='song-hype'),
    path('artists/<int:artist_id>/follow/', toggle_follow_artist, name='follow-artist'),
    path('keep-alive/', keep_alive, name='keep-alive'),
]
