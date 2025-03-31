#!/usr/bin/env python3

import os
from hurry.filesize import size
from dotenv import load_dotenv
import psycopg2

# Загрузка переменных окружения из .env
load_dotenv()


DB_HOST = os.getenv("DB_HOST", "172.18.0.9")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_DB = os.getenv("DB_DB", "nexus")
DB_USER = os.getenv("DB_USER", "nexus")
DB_PASS = os.getenv("DB_PASS", "ahyath1thaem4Aedaemeoph5Aadohb")

if DB_HOST is None or DB_USER is None or DB_PASS is None or DB_DB is None:
    print(
        "Please set the following environment variables:\nNS_DB_HOST\nNS_DB_USER\nNS_DB_PASS\nNS_DB_DB"
    )
    print("Exiting...")
    exit(1)
conn = psycopg2.connect(
    host=DB_HOST, database=DB_DB, user=DB_USER, password=DB_PASS, port=DB_PORT
)
cur = conn.cursor()
cur.execute(
    "SELECT tablename FROM pg_catalog.pg_tables WHERE tablename LIKE '%_content_repository';"
)
content_repository_tables_names = [x[0] for x in cur.fetchall()]
repos_size = {}
for content_repo in content_repository_tables_names:
    repo_type = content_repo.replace("_content_repository", "")
    cur.execute(f"""select r.name, sum(blob_size) from {repo_type}_asset_blob t_ab
        join {repo_type}_asset t_a on t_ab.asset_blob_id = t_a.asset_blob_id
        join {repo_type}_content_repository t_cr on t_cr.repository_id = t_a.repository_id
        join repository r on t_cr.config_repository_id = r.id
        group by r.name;""")
    repos_size.update(dict(cur.fetchall()))
sum = 0
for repo_name in repos_size.keys():
    sum += repos_size[repo_name]
    human_readable_size = size(repos_size[repo_name])
    print(f"{repo_name}: {human_readable_size}")
print(f"Sum: {size(sum)}")
