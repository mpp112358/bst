#!/usr/bin/env python3

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def printEvent(event, date, startTime):
    pass


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


def printSlots(minuteSlots, minutesPerSlot):
    for slot in range(len(minuteSlots) // minutesPerSlot):
        hour, minute = slotHourAndMin(slot, minutesPerSlot)
        print(f"{hour:02.0f}:{minute:02.0f} ", end="")
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
                print(event["event"]["summary"], end="")
            else:
                print(f"{event['event']['summary']} || ", end="")
        print("\n")


def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
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
        now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        endOfDay = datetime.combine(datetime.utcnow(), time(23, 59)).isoformat() + "Z"
        print(now)
        print(endOfDay)
        print("Getting the upcoming 10 events")
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

        if not events:
            print("No upcoming events found.")
            return

        # Prints the start and name of the next 10 events
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            startTime = datetime.fromisoformat(start).hour
            print(start, startTime, event["summary"])

        now = datetime.combine(datetime.now(), time(0, 0))
        firstSlotTimeVal = now.astimezone(ZoneInfo("Europe/Madrid"))
        print(firstSlotTimeVal)
        minuteSlots = [[] for _ in range(24 * 60)]
        fillMinuteSlots(firstSlotTimeVal, minuteSlots, events)
        printSlots(minuteSlots, 30)

    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
