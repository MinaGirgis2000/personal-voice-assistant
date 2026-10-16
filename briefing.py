"""Briefing data, scheduling rules, and a speech-friendly fallback."""

from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Event(Record):
    title: str = Field(min_length=1, max_length=200)
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def check_end(self):
        if self.end <= self.start:
            raise ValueError("Event end must be after start.")
        return self


class Task(Record):
    title: str = Field(min_length=1, max_length=200)
    due: AwareDatetime | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    estimated_minutes: int = Field(ge=1, le=1440)
    completed: bool = False


class BriefingData(Record):
    is_demo: bool = True
    updated_at: AwareDatetime
    events: list[Event] = Field(default_factory=list, max_length=200)
    tasks: list[Task] = Field(default_factory=list, max_length=200)


def clock(value: datetime, zone: ZoneInfo) -> str:
    return value.astimezone(zone).strftime("%I:%M %p").lstrip("0")


def build_context(data: BriefingData, now: datetime, zone: ZoneInfo,
                  available_minutes: int) -> dict:
    """Filter in local time; preserve events spanning midnight and ongoing shifts."""
    local_now = now.astimezone(zone)
    tomorrow = datetime.combine(local_now.date() + timedelta(days=1),
                                datetime.min.time(), tzinfo=zone)
    events = sorted(
        (event for event in data.events if event.end > now and event.start < tomorrow),
        key=lambda event: event.start,
    )
    pending = [task for task in data.tasks if not task.completed]
    priorities = {"high": 0, "medium": 1, "low": 2}
    far_future = now + timedelta(days=36500)
    pending.sort(key=lambda task: (
        0 if task.due and task.due < now else 1,
        priorities[task.priority], task.due or far_future,
    ))
    active = [event for event in events if event.start <= now < event.end]
    future = [event for event in events if event.start > now]
    window = available_minutes
    if future:
        # A small transition buffer, not an estimate of commute time.
        window = min(window, max(0, int((future[0].start - now).total_seconds() // 60) - 10))
    if active:
        window = 0
    candidate = next((task for task in pending if task.estimated_minutes <= window), None)

    def task_record(task):
        if task.due is None:
            due_label = "no due date entered"
        elif task.due < now:
            due_label = "overdue"
        elif task.due.astimezone(zone).date() == local_now.date():
            due_label = f"due today at {clock(task.due, zone)}"
        else:
            due_label = "due " + task.due.astimezone(zone).strftime("%b %d at %I:%M %p")
        return {"title": task.title, "due": due_label,
                "priority": task.priority, "estimated_minutes": task.estimated_minutes}

    return {
        "date": local_now.strftime("%A, %B %d"),
        "time": clock(now, zone),
        "timezone": str(zone),
        "events": [{"title": event.title, "start": clock(event.start, zone),
                    "end": clock(event.end, zone), "ongoing": event in active}
                   for event in events[:5]],
        "tasks": [task_record(task) for task in pending[:3]],
        "active_event": active[0].title if active else None,
        "available_minutes": window,
        "suggested_task": task_record(candidate) if candidate else None,
    }


def template_briefing(context: dict, mode: str) -> str:
    parts = [f"Here's your update for {context['date']}."]
    if context["events"]:
        for event in context["events"]:
            if event["ongoing"]:
                parts.append(f"{event['title']} is scheduled now, until {event['end']}.")
            else:
                parts.append(f"{event['title']} runs from {event['start']} to {event['end']}.")
    else:
        parts.append("There are no remaining events in your manually entered schedule today.")
    for task in context["tasks"]:
        parts.append(f"{task['title']}: {task['due']}, {task['priority']} priority.")
    if not context["tasks"]:
        parts.append("There are no unfinished tasks in your manual list.")
    if mode == "now":
        if context["active_event"]:
            parts.append("Your calendar shows you're busy now. Check in when you're free.")
        elif context["suggested_task"]:
            task = context["suggested_task"]
            parts.append(f"For your {context['available_minutes']} minute window, consider "
                         f"{task['title']}, estimated at {task['estimated_minutes']} minutes.")
        else:
            parts.append("No unfinished task fits the time window using the estimates entered.")
    return " ".join(parts)


def sample_data(now: datetime, zone: ZoneInfo) -> BriefingData:
    """Fictional examples for the setup day; never inferred personal information."""
    today = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    return BriefingData(
        is_demo=True, updated_at=now,
        events=[Event(title="Example work shift", start=today + timedelta(hours=6),
                      end=today + timedelta(hours=9, minutes=30)),
                Event(title="Example lecture", start=today + timedelta(hours=11),
                      end=today + timedelta(hours=12, minutes=20))],
        tasks=[Task(title="Example lab analysis", due=today + timedelta(hours=23),
                    priority="high", estimated_minutes=45),
               Task(title="Example email follow-up", due=today + timedelta(days=1, hours=17),
                    priority="medium", estimated_minutes=10)],
    )
