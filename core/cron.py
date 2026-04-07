import os
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

def ping_keep_alive():
    """
    Pings the keep-alive endpoint to prevent the service from sleeping.
    """
    backend_url = os.getenv('BACKEND_URL')
    if not backend_url:
        # Fallback to a common local URL for testing, but in prod it MUST be set
        backend_url = "http://127.0.0.1:8000"
    
    url = f"{backend_url.rstrip('/')}/api/listener/keep-alive/"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"[Cron] Keep-alive ping successful: {response.json().get('status')}")
        else:
            print(f"[Cron] Keep-alive ping failed with status: {response.status_code}")
    except Exception as e:
        print(f"[Cron] Keep-alive ping error: {str(e)}")

def start_scheduler():
    """
    Starts the background scheduler if the environment is production.
    """
    env = os.getenv('ENV', 'dev')
    
    if env == 'prod':
        scheduler = BackgroundScheduler()
        # Run every 10 minutes to keep the service healthy
        scheduler.add_job(ping_keep_alive, 'interval', minutes=10)
        scheduler.start()
        print("[Cron] Background scheduler started (Production mode).")
    else:
        print(f"[Cron] Background scheduler NOT started (Environment: {env}).")
