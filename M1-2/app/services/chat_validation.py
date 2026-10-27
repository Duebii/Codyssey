"""Validate model proposals against user-supplied facts, never against guesses."""
from datetime import timedelta
import re

from app.core.openai_client import InvalidModelReply
from app.schemas.conversations import ContextPatch
from app.schemas.plans import ModelReply


def require(condition: bool, field: str | None = None):
    if not condition:
        raise InvalidModelReply(field=field)


def minutes_in_quote(quote: str) -> int | None:
    if re.search(r"(?:~|에서|부터|정도|아마|대략|또는)", quote):
        return None
    normalized = quote
    for word, number in (("한", 1), ("두", 2), ("세", 3), ("네", 4)):
        normalized = re.sub(rf"{word}\s*시간", f"{number}시간", normalized)
    # One duration only: deadline times and alternatives must be clarified.
    values = re.findall(r"(?:(\d+)\s*시간\s*)?(?:(\d+)\s*분)?", normalized)
    durations = [int(hours or 0) * 60 + int(minutes or 0) for hours, minutes in values if hours or minutes]
    return durations[0] if len(durations) == 1 else None


def verified_context(reply: ModelReply, current: ContextPatch, message: str,
                     explicit_patch: ContextPatch | None, today) -> ContextPatch:
    values = current.model_dump(mode="json")
    for field, fact in reply.context_update:
        if fact is None:
            continue
        def check(condition):
            require(condition, field=field)
        value = fact.value
        json_value = [task.model_dump(mode="json") for task in value] if field == "tasks" else value
        # Repeating an already validated form/stored value changes no fact.
        # Only actual changes need a newly grounded quote from this message.
        if json_value == values[field]:
            continue
        check(fact.quote in message)
        # An explicit form value and an inconsistent message require a question.
        if explicit_patch is not None and field in explicit_patch.model_fields_set:
            check(json_value == values[field])
        if value is None:
            check(bool(re.search(r"지워|삭제|초기화|없어|미정|취소|모르", fact.quote)))
        elif field == "available_minutes":
            check(minutes_in_quote(fact.quote) == value)
        elif field in {"goal", "constraints"}:
            check(bool(value) and value in fact.quote)
        else:
            old = {task.id: task for task in current.tasks}
            old_by_title = {task.title: task.id for task in current.tasks}
            new = {task.id: task for task in value}
            if set(old) - set(new):
                check(bool(re.search(r"삭제|빼|제외|대신|교체|비워|지워|만\s*(할|해|하)", fact.quote)))
            for task in value:
                previous = old.get(task.id)
                if previous is not None and previous == task:
                    continue
                check(task.title in fact.quote)
                check(task.title not in old_by_title or old_by_title[task.title] == task.id)
                if task.due_date is not None and (previous is None or previous.due_date != task.due_date):
                    allowed_dates = {today.isoformat()} if "오늘" in fact.quote else set()
                    if "내일" in fact.quote:
                        allowed_dates.add((today + timedelta(days=1)).isoformat())
                    if "모레" in fact.quote:
                        allowed_dates.add((today + timedelta(days=2)).isoformat())
                    check(task.due_date.isoformat() in fact.quote or task.due_date.isoformat() in allowed_dates)
                if previous is not None and previous.due_date is not None and task.due_date is None:
                    check(bool(re.search(r"마감.*(없|취소|미정|삭제|지워)", fact.quote)))
                if task.importance != "unknown" and (previous is None or previous.importance != task.importance):
                    markers = {"high": r"중요|최우선|높|긴급", "medium": r"중간|보통", "low": r"낮|덜 중요"}
                    check(bool(re.search(markers[task.importance], fact.quote)))
                if previous is not None and previous.importance != "unknown" and task.importance == "unknown":
                    check(bool(re.search(r"중요도.*(몰|미정|삭제|지워|초기화)", fact.quote)))
                if task.depends_on and (previous is None or previous.depends_on != task.depends_on):
                    check(bool(re.search(r"먼저|후|선행|끝나|다음", fact.quote)))
                    check(all(new.get(parent) and new[parent].title in fact.quote for parent in task.depends_on))
                if previous is not None and previous.depends_on and not task.depends_on:
                    check(bool(re.search(r"(선행|의존).*(없|취소|삭제|지워)", fact.quote)))
        values[field] = json_value
    return ContextPatch.model_validate(values)


def validate_reply(reply: ModelReply, context: ContextPatch):
    if reply.reply_type == "clarification":
        require(1 <= len(reply.questions) <= 2 and reply.plan is None)
        return
    if reply.reply_type != "plan":
        require(reply.plan is None and bool(reply.content.strip()))
        return
    require(not reply.questions)
    plan = reply.plan
    require(plan is not None and context.available_minutes is not None and bool(context.tasks))
    require(plan.available_minutes == context.available_minutes)
    planned_ids = [item.task_id for item in plan.tasks]
    deferred_ids = [item.task_id for item in plan.deferred]
    all_ids = planned_ids + deferred_ids
    tasks = {task.id: task for task in context.tasks}
    require(len(all_ids) == len(set(all_ids)) and set(all_ids) == set(tasks))
    require([task.priority for task in plan.tasks] == list(range(1, len(plan.tasks) + 1)))
    require(sum(step.minutes for task in plan.tasks for step in task.steps) + plan.buffer_minutes <= plan.available_minutes)
    completed = set()
    for task in plan.tasks:
        require(set(tasks[task.task_id].depends_on) <= completed)
        completed.add(task.task_id)
