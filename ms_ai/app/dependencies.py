# backend/dependencies.py
import os

from dotenv import find_dotenv, load_dotenv
from fastapi import Header, HTTPException, status

from .exercise_manager import get_step

load_dotenv(find_dotenv())

API_KEY: str = os.getenv("API_KEY", "your-super-secret-key-123")


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
