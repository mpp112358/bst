#!/usr/bin/env python3

from todoist_api_python.api import TodoistAPI

api = TodoistAPI("REDACTED")

try:
    tasks = api.get_tasks()
    for task in tasks:
        print(f"{task.due.string if task.due else '-----'} {task.content}")

except Exception as error:
    print(error)
