import requests
import yaml

# Настройки
GITLAB_TOKEN = 'your_token'
GITLAB_URL = 'https://gitlab.com'
GROUP_ID = 'your_group_id_or_path'  # например 'my-group'

HEADERS = {'PRIVATE-TOKEN': GITLAB_TOKEN}
TARGET_FILES = ['.gitlab-ci.yml', 'config/app.yaml']
DEFAULT_BRANCH = 'main'

def get_projects_in_group(group_id):
    url = f"{GITLAB_URL}/api/v4/groups/{group_id}/projects"
    response = requests.get(url, headers=HEADERS)
    return response.json() if response.status_code == 200 else []

def get_file_content(project_id, file_path, ref=DEFAULT_BRANCH):
    url = f"{GITLAB_URL}/api/v4/projects/{requests.utils.quote(str(project_id), safe='')}/repository/files/{requests.utils.quote(file_path, safe='')}/raw"
    params = {'ref': ref}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        return response.text
    return None

def parse_yaml(content):
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"Ошибка разбора YAML: {e}")
        return None

def main():
    projects = get_projects_in_group(GROUP_ID)
    for project in projects:
        print(f"📦 {project['name']}")
        for file_path in TARGET_FILES:
            content = get_file_content(project['id'], file_path)
            if content:
                data = parse_yaml(content)
                print(f"🔹 Файл: {file_path}")
                print(data)
            else:
                print(f"⚠️ Файл {file_path} не найден")

if __name__ == "__main__":
    main()
