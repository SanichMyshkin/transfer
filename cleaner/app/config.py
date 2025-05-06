import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")

PREFIX_RETENTION = {
    "dev": timedelta(days=7),
    "test": timedelta(days=14),
    "release": timedelta(days=90),
    "master": timedelta(days=180),
}

DEFAULT_RETENTION = timedelta(days=30)
RESERVED_MINIMUM = 2
