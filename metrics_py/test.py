import requests


delete = 'blobstore.delete-temp-files'
compact = 'blobstore.compact'

repositories = requests.get('http://sanich.space/service/rest/v1/repositorySettings', auth=('admin', 'admin123')).json()
tasks = requests.get('http://sanich.space/service/rest/v1/tasks', auth=('admin', 'admin123')).json()

tasks = tasks['items']

task_map = dict()

compact_list = list()
delete_list = list()

for task in tasks:
    if task.get('type') == delete:
        if task.get('message'):
            name = task.get('message').split()[1]
            print(f'{name} - блоб в строке {task.get("message")}')
    if task.get('type') == compact:
        if task.get('message'):
            name = task.get('message').split()[1]
            print(f'{name} - блоб в строке {task.get("message")}')