import urllib.parse
from config import NEXUS_API_URL


def build_nexus_url(repo, image, encoding=True):
    path = f"v2/{image}/tags"
    if encoding:
        path = urllib.parse.quote(path, safe="")
    return f"{NEXUS_API_URL}#browse/browse:{repo}:{path}"
