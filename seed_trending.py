import os
import django
import random

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from creator.models import Song

def seed_trending():
    songs = Song.objects.all()
    if not songs.exists():
        print("No songs found to seed.")
        return

    genres = ['afrobeats', 'hiphop', 'rnb', 'gospel', 'pop', 'electronic', 'rock', 'jazz']
    images = [
        '/trending/banner1.png',
        '/trending/banner2.png',
        '/trending/banner3.png',
        '/trending/banner4.png',
        '/trending/banner5.png',
    ]

    for i, song in enumerate(songs):
        # Update hype count to something visible
        song.hype_count = random.randint(100, 5000000)
        
        # Ensure genre is set
        if not song.genre or song.genre == 'other':
            song.genre = random.choice(genres)
        
        # Assign one of the local generated images
        song.cover_image_url = images[i % len(images)]
        
        song.save()
        print(f"Updated {song.title} - Hype: {song.hype_count}, Genre: {song.genre}")

if __name__ == "__main__":
    seed_trending()
