from django.db import models
from django.conf import settings

class Playlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='playlists')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    cover_image_url = models.URLField(max_length=500, blank=True, null=True)
    songs = models.ManyToManyField('creator.Song', related_name='playlists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} by {self.user.username}"

class FollowedArtist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    artist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'artist')

    def __str__(self):
        return f"{self.user.username} follows {self.artist.username}"

class UserLibrary(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    saved_songs = models.ManyToManyField('creator.Song', related_name='saved_by_users', blank=True)
    saved_playlists = models.ManyToManyField(Playlist, related_name='saved_by_users', blank=True)

    def __str__(self):
        return f"{self.user.email}'s Library"
