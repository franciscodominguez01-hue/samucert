import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-samucert-2026')
    # Usamos 127.0.0.1 explícitamente para WSL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'postgresql://postgres:samucert123@127.0.0.1:5432/samucert'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
