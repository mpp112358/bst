#!/usr/bin/env python3
import cmd
import ipdb

from dotenv import load_dotenv
import os

from urllib.parse import quote

from rich.console import Console
from rich.markdown import Markdown

import itertools

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from todoist_api_python.api import TodoistAPI

load_dotenv()
todoistapi = TodoistAPI(os.getenv("TODOIST_API_KEY"))

def noDateTasks(tasks):
    filteredTasks = []
    for task in tasks:
        if not task.due:
            filteredTasks.append(task)
    return filteredTasks

def overdueTasks(tasks):
    filteredTasks = []
    for task in tasks:
        if task.due:
            if task.due.datetime:
                dt = datetime.fromisoformat(task.due.datetime)
                if dt.date() <= datetime.now().date():
                    filteredTasks.append(task)
    return filteredTasks

def tasks(client, taskfilter, quantity):
    "List tasks grouped by due time."
    try:
        tasks = todoistapi.get_tasks()
        if not quantity:
            quantity = len(tasks)
        tasklist = "# No date"
        filteredTasks = noDateTasks(tasks)
        if filteredTasks:
            for task in itertools.islice(filteredTasks, quantity):
                tasklist = tasklist + f"\n- {task.content}"
        tasklist = tasklist + f"\n# Today"
        tTasks = overdueTasks(tasks)
        if tTasks:
            for task in itertools.islice(tTasks, quantity):
                tasklist = tasklist + f"\n- {task.content}"
        tasklist = tasklist + f"\n# All"
        for task in itertools.islice(tasks, quantity):
            tasklist = tasklist + f"\n- {task.content}"
        client.console.print(Markdown(tasklist))
    except Exception as error:
        client.console.print(error)


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def timeToSlotIndex(timeVal, firstSlotTimeVal):
    td = timeVal - firstSlotTimeVal
    return td.days * 24 * 60 + td.seconds // 60


def isAllDay(event):
    return "dateTime" not in event["start"]


def fillMinuteSlots(firstSlotTimeVal, minuteSlots, events):
    for event in events:
        if not isAllDay(event):
            start = event["start"].get("dateTime", event["start"].get("date"))
            startTime = datetime.fromisoformat(start).astimezone(
                ZoneInfo("Europe/Madrid")
            )
            startIndex = timeToSlotIndex(startTime, firstSlotTimeVal)
            end = event["end"].get("dateTime", event["end"].get("date"))
            endTime = datetime.fromisoformat(end).astimezone(ZoneInfo("Europe/Madrid"))
            endIndex = timeToSlotIndex(endTime, firstSlotTimeVal)
            for i in range(max(startIndex, 0), min(endIndex + 1, len(minuteSlots) - 1)):

                minuteSlots[i].append({"type": "mid", "event": event})
            if (
                startIndex >= 0
                and startIndex < len(minuteSlots)
                and len(minuteSlots[startIndex]) > 0
            ):
                minuteSlots[startIndex][-1]["type"] = "beg"
            if (
                endIndex >= 0
                and endIndex < len(minuteSlots)
                and len(minuteSlots[endIndex]) > 0
            ):
                minuteSlots[endIndex][-1]["type"] = "end"


def slotHourAndMin(slotIndex, minutesPerSlot):
    slotsPerHour = 60 // minutesPerSlot
    hour = slotIndex // slotsPerHour
    minutes = minutesPerSlot * (slotIndex % slotsPerHour)
    return hour, minutes


def printSlots(client, minuteSlots, minutesPerSlot):
    for slot in range(len(minuteSlots) // minutesPerSlot):
        hour, minute = slotHourAndMin(slot, minutesPerSlot)
        client.console.print(f"{hour:02.0f}:{minute:02.0f} ", end="")
        zoomedMinuteSlot = minuteSlots[
            slot * minutesPerSlot : slot * minutesPerSlot + minutesPerSlot
        ]
        eventIdsToPrint = set()
        eventsToPrint = []
        for minuteSlot in zoomedMinuteSlot:
            for event in minuteSlot:
                if event["event"]["id"] not in eventIdsToPrint:
                    eventIdsToPrint.add(event["event"]["id"])
                    eventsToPrint.append(event)
        for i, event in enumerate(eventsToPrint):
            dt = event["event"]["start"].get(
                "dateTime", event["event"]["start"].get("date")
            )
            if i == len(eventsToPrint) - 1:
                client.console.print(event["event"]["summary"], end="")
            else:
                client.console.print(f"{event['event']['summary']} || ", end="")
        client.console.print("\n")


def getEvents(fromDatetime=None, toDatetime=None, number=None):
    """Returns a list of events from Google Calendar API
    spanning from 'fromDatetime' to 'toDatetime';
    limiting the list to a maximum of 'number' items if 'number' is not None.
    By default, 'fromDatetime' is now, and 'toDatetime' is the end of today.
    """
    now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
    if not fromDatetime:
        fromDatetime = now
    endOfDay = datetime.combine(datetime.utcnow(), time(23, 59)).isoformat() + "Z"
    if not toDatetime:
        toDatetime = endOfDay

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                # timeMax=endOfDay,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        return events

    except HttpError as error:
        client.console.print(f"An error occurred: {error}")


def today(client, interval=30):
    """Prints today's schedule in the given interval (in minutes)
    """
    events = getEvents()
    if events:
        now = datetime.combine(datetime.now(), time(0, 0))
        firstSlotTimeVal = now.astimezone(ZoneInfo("Europe/Madrid"))
        minuteSlots = [[] for _ in range(24 * 60)]
        fillMinuteSlots(firstSlotTimeVal, minuteSlots, events)
        printSlots(client, minuteSlots, interval)


class CalendarClient(cmd.Cmd):
    intro = "Type 'help' or '?' for commands."
    prompt = "> "

    def __init__(self):
        super().__init__()
        self.console = Console()

    # Command today
    def do_today(self, arg):
        "List today's block schedule: today [n minutes intervals]."
        interval = int(arg) if arg else 30
        today(self, interval)

    def do_tasks(self, args):
        "List not scheduled tasks: tasks."
        parts = args.strip().split() if args else None
        if parts and len(parts) > 1:
            quantitystr = parts[0]
            quantity = int(quantitystr)
        else:
            quantity = None
        if parts and len(parts) > 2:
            taskfilter = " ".join(parts[1:])
        else:
            taskfilter = "no date"
        tasks(self, taskfilter, quantity)

    def do_exit(self, args):
        "Exit the scheduler."
        return True

if __name__ == "__main__":
    CalendarClient().cmdloop()
