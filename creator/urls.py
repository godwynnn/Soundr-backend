from django.urls import path
from .views import creator_dashboard_data, manage_track, manage_podcast, generate_livekit_token, start_stream, end_stream, list_active_streams

urlpatterns = [
    path('dashboard/', creator_dashboard_data, name='creator_dashboard'),
    path('upload/', manage_track, name='creator_upload'),
    path('edit/<int:track_id>/', manage_track, name='creator_edit'),
    path('podcast/upload/', manage_podcast, name='manage_podcast'),
    path('podcast/live-token/', generate_livekit_token, name='generate_livekit_token'),
    path('streams/', list_active_streams, name='list_active_streams'),
    path('streams/start/', start_stream, name='start_stream'),
    path('streams/end/', end_stream, name='end_stream'),
]
