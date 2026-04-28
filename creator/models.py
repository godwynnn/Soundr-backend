from django.db import models
from django.conf import settings
from pgvector.django import VectorField
from creator.embeddingUtils import get_embedding

class Song(models.Model):
    GENRE_CHOICES = [
        ('afrobeats', 'Afrobeats'),
        ('hiphop', 'Hip-Hop'),
        ('rnb', 'R&B'),
        ('gospel', 'Gospel'),
        ('pop', 'Pop'),
        ('electronic', 'Electronic'),
        ('rock', 'Rock'),
        ('jazz', 'Jazz'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    genre = models.CharField(max_length=100, choices=GENRE_CHOICES, default='other')
    tags = models.CharField(max_length=500, blank=True, default='')  # Comma-separated tags
    duration = models.CharField(max_length=10, blank=True, default='0:00')
    cover_image_url = models.URLField(max_length=500, blank=True, null=True)
    audio_file_url = models.URLField(max_length=500, blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_songs',
        null=True,
        blank=True
    )
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    total_play_count = models.PositiveIntegerField(default=0)
    hype_count = models.PositiveIntegerField(default=0)
    # embedding = VectorField(dimensions=768,null=True,
    #     blank=True
    # )  # adjust to Gemini output size
    embedding = VectorField(dimensions=3072, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



    def build_embedding_text(self):
        return f"{self.title} is a {self.genre} song by {self.artist}"

    def save(self, *args, **kwargs):
        # Only generate embedding if it's missing or empty
        if self.embedding is None or len(self.embedding) == 0:
            print('ok')
            text = self.build_embedding_text()

            try:
                self.embedding = get_embedding(text)
            except Exception as e:
                # Optional: log error instead of breaking save
                print(f"Embedding generation failed: {e}")

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} - {self.artist}"

class MonthlySongStats(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='monthly_stats')
    year = models.IntegerField()
    month = models.IntegerField()
    total_plays = models.BigIntegerField(default=0)
    unique_listeners = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ("song", "year", "month")
        indexes = [
            models.Index(fields=["year", "month"]),
        ]

    def __str__(self):
        return f"{self.song.title} - {self.year}/{self.month}"

class Podcast(models.Model):
    CATEGORY_CHOICES = [
        ('entertainment', 'Entertainment'),
        ('education', 'Education'),
        ('news', 'News'),
        ('technology', 'Technology'),
        ('music', 'Music'),
        ('other', 'Other'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('unlisted', 'Unlisted'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='other')
    visibility = models.CharField(max_length=50, choices=VISIBILITY_CHOICES, default='public')
    cover_image_url = models.URLField(max_length=500, blank=True, null=True)
    audio_file_url = models.URLField(max_length=500, blank=True, null=True)
    duration = models.CharField(max_length=10, blank=True, default='0:00')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_podcasts'
    )
    total_play_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Stream(models.Model):
    room_name = models.CharField(max_length=255, unique=True)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='host_stream'
    )
    title = models.CharField(max_length=255)
    is_live = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SongLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'song')

    def __str__(self):
        return f"{self.user.username} liked {self.song.title}"


class PodcastLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    podcast = models.ForeignKey(Podcast, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'podcast')

    def __str__(self):
        return f"{self.user.username} liked {self.podcast.title}"


class PodcastComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    podcast = models.ForeignKey(Podcast, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on {self.podcast.title}"

class SongComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on {self.song.title}"