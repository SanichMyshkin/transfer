import os
from dotenv import load_dotenv

load_dotenv()

NEXUS_API_URL = os.getenv("NEXUS_API_URL")
NEXUS_USERNAME = os.getenv("NEXUS_USERNAME")
NEXUS_PASSWORD = os.getenv("NEXUS_PASSWORD")
DATABASE_URL = os.getenv("DATABASE_URL")
LAUNCH_INTERVAL = int(os.getenv("LAUNCH_INTERVAL", "300"))


def get_auth():
    return (NEXUS_USERNAME, NEXUS_PASSWORD)
