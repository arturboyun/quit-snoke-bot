"""Main menu as an aiogram_dialog Dialog."""

import datetime
from zoneinfo import ZoneInfo

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, LaunchMode, Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Row, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from bot.db.engine import session_factory
from bot.services.course import (
    ACHIEVEMENT_DEFS,
    check_and_grant_achievements,
    complete_course,
    get_active_course,
    get_course_history,
    get_craving_count,
    get_doses_taken_today,
    get_last_dose_time,
    get_last_relapse_time,
    get_mood_history,
    get_or_create_user,
    get_relapse_stats,
    get_smoking_profile,
    get_today_dose_times,
    get_user_achievements,
    grant_achievement,
    log_craving,
    log_dose,
    log_relapse,
)
from bot.services.schedule import (
    QUIT_DAY,
    build_adaptive_schedule,
    get_course_day,
    get_phase,
    get_progress,
)
from bot.tasks import schedule_next_dose
from bot.utils.texts import (
    achievements_text,
    already_has_course_text,
    confirm_complete_text,
    confirm_start_course_text,
    course_completed_manual_text,
    course_history_text,
    dose_taken_text,
    dose_too_soon_text,
    health_timeline_text,
    help_text,
    menu_text,
    mood_history_text,
    new_achievement_text,
    no_smoking_profile_text,
    progress_text,
    relapse_ask_count_text,
    relapse_logged_text,
    savings_text,
    settings_menu_text,
    sos_craving_text,
    today_schedule_text,
)


class MenuSG(StatesGroup):
    main = State()
    progress = State()
    schedule = State()
    settings = State()
    help = State()
    sos = State()
    savings = State()
    health = State()
    achievements = State()
    relapse = State()
    confirm_start = State()
    confirm_cancel = State()
    confirm_complete = State()
    history = State()
    mood_history = State()


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_user_course_ctx(user_id: int) -> dict:
    """Load user + course context common to many getters."""
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        user = await get_or_create_user(session, user_id)
    has_course = course is not None
    tz = ZoneInfo(user.timezone)
    today = datetime.datetime.now(tz).date()
    day = get_course_day(course.start_date, today) if course else None
    return {
        "course": course,
        "user": user,
        "has_course": has_course,
        "tz": tz,
        "today": today,
        "day": day,
    }


def _money_examples(amount: float) -> list[str]:
    examples = []
    if amount >= 5:
        examples.append(f"☕ {int(amount / 5)} чашек кофе")
    if amount >= 50:
        examples.append(f"🍕 {int(amount / 50)} походов в пиццерию")
    if amount >= 300:
        examples.append(f"🎬 {int(amount / 300)} походов в кино")
    if amount >= 5000:
        examples.append(f"✈️ {int(amount / 5000)} коротких путешествий")
    if not examples:
        examples.append("Пока копишь на первый кофе ☕")
    return examples


# ── Getters ──────────────────────────────────────────────────────────────────


async def main_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    ctx = await _get_user_course_ctx(user_id)
    day = ctx["day"]
    phase = None
    if day and 1 <= day <= 25:
        phase = get_phase(day).phase
    return {
        "has_course": ctx["has_course"],
        "text": menu_text(day, phase) if day and phase else menu_text(),
    }


async def progress_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    ctx = await _get_user_course_ctx(user_id)
    if not ctx["has_course"] or not ctx["day"] or ctx["day"] < 1 or ctx["day"] > 25:
        return {"text": "Нет активного курса или курс завершён."}

    async with session_factory() as session:
        taken = await get_doses_taken_today(session, ctx["course"].id, ctx["today"])
        smoke_free_days = None
        if ctx["day"] >= QUIT_DAY:
            relapse_stats = await get_relapse_stats(session, user_id)
            if relapse_stats["total_cigarettes"] == 0:
                smoke_free_days = max(0, ctx["day"] - QUIT_DAY)

    stats = get_progress(ctx["day"], taken)
    if smoke_free_days is not None:
        stats["smoke_free_days"] = smoke_free_days
    return {"text": progress_text(stats)}


async def schedule_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    ctx = await _get_user_course_ctx(user_id)
    if not ctx["has_course"] or not ctx["day"] or ctx["day"] < 1 or ctx["day"] > 25:
        return {"text": "Нет активного курса или курс завершён."}

    async with session_factory() as session:
        taken_times = await get_today_dose_times(session, ctx["course"].id, ctx["day"])

    phase_info = get_phase(ctx["day"])
    now = datetime.datetime.now(ctx["tz"])
    slots = build_adaptive_schedule(
        day=ctx["day"],
        sleep_time=ctx["user"].sleep_time,
        wake_time=ctx["user"].wake_time,
        timezone=ctx["user"].timezone,
        taken_times=taken_times,
        now=now,
        course_start_dt=ctx["course"].created_at,
    )
    times = [s.time.strftime("%H:%M") for s in slots]
    taken = sum(1 for s in slots if s.taken)
    now_time = now.strftime("%H:%M")
    return {
        "text": today_schedule_text(
            ctx["day"], phase_info.phase, times, phase_info.target_display, taken,
            now_time=now_time,
        ),
    }


async def settings_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    async with session_factory() as session:
        user = await get_or_create_user(session, user_id)
    return {
        "text": settings_menu_text(
            user.timezone,
            user.wake_time.strftime("%H:%M"),
            user.sleep_time.strftime("%H:%M"),
        ),
    }


async def sos_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    return {"text": dialog_manager.dialog_data.get("sos_text", "")}


async def savings_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    ctx = await _get_user_course_ctx(user_id)
    if not ctx["has_course"]:
        return {"text": "Нет активного курса."}

    async with session_factory() as session:
        profile = await get_smoking_profile(session, user_id)
        relapse_stats = await get_relapse_stats(session, user_id)

    if not profile:
        return {"text": no_smoking_profile_text()}

    day = ctx["day"] or 0
    if relapse_stats["total_cigarettes"] == 0 and day >= QUIT_DAY:
        days_smoke_free = max(0, day - QUIT_DAY)
    else:
        days_smoke_free = 0

    cigarettes_avoided = days_smoke_free * profile.cigarettes_per_day
    cigarettes_avoided = max(0, cigarettes_avoided - relapse_stats["total_cigarettes"])
    price_per_cigarette = profile.pack_price / profile.cigarettes_in_pack
    money_saved = cigarettes_avoided * price_per_cigarette
    examples = _money_examples(money_saved)
    return {"text": savings_text(days_smoke_free, cigarettes_avoided, money_saved, examples)}


async def health_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    ctx = await _get_user_course_ctx(user_id)
    if not ctx["has_course"]:
        return {"text": "Нет активного курса."}

    async with session_factory() as session:
        last_relapse = await get_last_relapse_time(session, user_id)

    now = datetime.datetime.now(ctx["tz"])
    day = ctx["day"] or 0

    if day < QUIT_DAY:
        hours_smoke_free = 0.0
    else:
        quit_date = ctx["course"].start_date + datetime.timedelta(days=QUIT_DAY - 1)
        quit_dt = datetime.datetime.combine(quit_date, datetime.time(0, 0), tzinfo=ctx["tz"])
        if last_relapse is not None:
            last_relapse_aware = (
                last_relapse
                if last_relapse.tzinfo
                else last_relapse.replace(tzinfo=datetime.UTC)
            )
            smoke_free_since = max(quit_dt, last_relapse_aware.astimezone(ctx["tz"]))
        else:
            smoke_free_since = quit_dt
        hours_smoke_free = max(0.0, (now - smoke_free_since).total_seconds() / 3600)

    return {"text": health_timeline_text(hours_smoke_free)}


async def achievements_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    async with session_factory() as session:
        user = await get_or_create_user(session, user_id)
        await check_and_grant_achievements(session, user_id, timezone=user.timezone)
        earned = await get_user_achievements(session, user_id)
        await session.commit()

    earned_list = []
    for a in earned:
        if a.key in ACHIEVEMENT_DEFS:
            title, desc = ACHIEVEMENT_DEFS[a.key]
            earned_list.append((a.key, title, desc))
    return {"text": achievements_text(earned_list, len(ACHIEVEMENT_DEFS))}


async def history_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    async with session_factory() as session:
        courses = await get_course_history(session, user_id)
    return {"text": course_history_text(courses)}


async def mood_history_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    async with session_factory() as session:
        moods = await get_mood_history(session, user_id)
    mood_list = [(m.created_at.strftime("%d.%m"), m.mood) for m in moods]
    return {"text": mood_history_text(mood_list)}


async def confirm_start_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    user_id = dialog_manager.event.from_user.id
    async with session_factory() as session:
        active = await get_active_course(session, user_id)
    if active:
        return {"text": already_has_course_text()}
    return {"text": confirm_start_course_text()}


# ── Button callbacks ─────────────────────────────────────────────────────────


async def on_take_dose(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    user_id = callback.from_user.id
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, user_id)
        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

        now_time = now.time()
        if user.sleep_time > user.wake_time:
            if now_time < user.wake_time or now_time >= user.sleep_time:
                await callback.answer(
                    "Сейчас время сна — таблетку принимать не нужно", show_alert=True,
                )
                return
        else:
            if user.sleep_time <= now_time < user.wake_time:
                await callback.answer(
                    "Сейчас время сна — таблетку принимать не нужно", show_alert=True,
                )
                return

        phase_info = get_phase(day)
        taken = await get_doses_taken_today(session, course.id, today)
        if taken >= phase_info.target_tablets:
            await callback.answer(
                f"Сегодня уже принято {taken}/{phase_info.target_display} таблеток",
                show_alert=True,
            )
            return

        last_time = await get_last_dose_time(session, course.id, day)
        if last_time is not None:
            last_aware = (
                last_time if last_time.tzinfo else last_time.replace(tzinfo=datetime.UTC)
            )
            elapsed = (
                now.astimezone(datetime.UTC) - last_aware.astimezone(datetime.UTC)
            ).total_seconds()
            min_interval = phase_info.interval_minutes * 60
            if elapsed < min_interval:
                minutes_left = int((min_interval - elapsed) / 60) + 1
                await callback.answer(dose_too_soon_text(minutes_left), show_alert=True)
                return

        await log_dose(
            session,
            course_id=course.id,
            user_id=user_id,
            scheduled_at=now,
            day=day,
            phase=phase_info.phase,
        )
        taken = await get_doses_taken_today(session, course.id, today)
        newly_earned = await check_and_grant_achievements(
            session, user_id, timezone=user.timezone,
        )
        await session.commit()

    next_dt = now + datetime.timedelta(minutes=phase_info.interval_minutes)
    sleep_dt = datetime.datetime.combine(today, user.sleep_time, tzinfo=tz)
    if sleep_dt <= datetime.datetime.combine(today, user.wake_time, tzinfo=tz):
        sleep_dt += datetime.timedelta(days=1)
    next_time = next_dt.strftime("%H:%M") if next_dt < sleep_dt else None

    text = dose_taken_text(taken, phase_info.target_display, next_time)
    for key in newly_earned:
        if key in ACHIEVEMENT_DEFS:
            title, desc = ACHIEVEMENT_DEFS[key]
            text += f"\n\n{new_achievement_text(title, desc)}"

    manager.dialog_data["dose_result"] = text
    await schedule_next_dose.kiq(user_id)
    await callback.answer("✅ Отмечено!")


async def on_sos(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    user_id = callback.from_user.id
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, user_id)
        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()
        day = get_course_day(course.start_date, today)

        relapse_stats = await get_relapse_stats(session, user_id)
        hours_since_last_smoke = None
        if relapse_stats["total_cigarettes"] == 0 and day >= QUIT_DAY:
            days_smoke_free = max(0, day - QUIT_DAY)
        else:
            days_smoke_free = 0
            last_relapse = await get_last_relapse_time(session, user_id)
            if last_relapse is not None:
                lr = (
                    last_relapse
                    if last_relapse.tzinfo
                    else last_relapse.replace(tzinfo=datetime.UTC)
                )
                hours_since_last_smoke = max(
                    0.0,
                    (now.astimezone(datetime.UTC) - lr.astimezone(datetime.UTC)).total_seconds()
                    / 3600,
                )

        await log_craving(session, user_id)
        cravings = await get_craving_count(session, user_id)
        newly_earned = await check_and_grant_achievements(
            session, user_id, timezone=user.timezone,
        )
        await session.commit()

    text = sos_craving_text(days_smoke_free, cravings, hours_since_last_smoke)
    for key in newly_earned:
        if key in ACHIEVEMENT_DEFS:
            title, desc = ACHIEVEMENT_DEFS[key]
            text += f"\n\n{new_achievement_text(title, desc)}"

    manager.dialog_data["sos_text"] = text
    await manager.switch_to(MenuSG.sos)


async def on_confirm_start_course(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    user_id = callback.from_user.id
    async with session_factory() as session:
        active = await get_active_course(session, user_id)
        if active:
            await callback.answer("Курс уже создан", show_alert=True)
            return

        from bot.services.course import start_course

        user = await get_or_create_user(session, user_id)
        today = datetime.datetime.now(ZoneInfo(user.timezone)).date()
        await start_course(session, user_id, today)
        await session.commit()

    from bot.taskiq_broker import schedule_source
    from bot.tasks import schedule_daily_doses, schedule_next_day

    await schedule_source.startup()
    await schedule_daily_doses.kiq(user_id)
    await schedule_next_dose.kiq(user_id)
    await schedule_next_day.kiq(user_id)

    await callback.answer("🚀 Курс начат!")
    await manager.switch_to(MenuSG.main)


async def on_confirm_cancel_course(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    user_id = callback.from_user.id
    async with session_factory() as session:
        active = await get_active_course(session, user_id)
        if not active:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        from bot.models.course import CourseStatus

        active.status = CourseStatus.CANCELLED
        await session.commit()

    await callback.answer("🛑 Курс отменён")
    await manager.switch_to(MenuSG.main)


async def on_confirm_complete_course(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    user_id = callback.from_user.id
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        await complete_course(session, user_id)
        await grant_achievement(session, user_id, "course_completed")
        await session.commit()

    manager.dialog_data["complete_text"] = course_completed_manual_text()
    await callback.answer("✅ Курс завершён!")
    await manager.switch_to(MenuSG.main)


async def on_relapse_count_entered(
    message: Message,
    widget: TextInput,
    manager: DialogManager,
    value: int,
) -> None:
    user_id = message.from_user.id
    async with session_factory() as session:
        await log_relapse(session, user_id, value)
        stats = await get_relapse_stats(session, user_id)
        profile = await get_smoking_profile(session, user_id)
        await session.commit()

    cpd = profile.cigarettes_per_day if profile else None
    manager.dialog_data["relapse_text"] = relapse_logged_text(
        stats["count"], stats["total_cigarettes"], cpd,
    )
    await manager.switch_to(MenuSG.main)


async def on_relapse_count_error(
    message: Message,
    widget: TextInput,
    manager: DialogManager,
    error: ValueError,
) -> None:
    await message.answer("❌ Отправь число от 1 до 100.")


def _validate_relapse_count(text: str) -> int:
    count = int(text.strip())
    if count < 1 or count > 100:
        raise ValueError("Number out of range")
    return count


# ── Settings button callbacks (delegate to existing FSM handlers) ────────────


async def on_settings_timezone(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    from bot.handlers.settings import SettingsStates
    from bot.keyboards.inline import timezone_keyboard
    from bot.utils.texts import ask_timezone_text

    await manager.done()

    state: FSMContext = manager.middleware_data["state"]
    await callback.message.answer(
        ask_timezone_text(), reply_markup=timezone_keyboard(), parse_mode="HTML",
    )
    await state.set_state(SettingsStates.waiting_timezone)


async def on_settings_wake(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    from bot.handlers.settings import SettingsStates
    from bot.utils.texts import ask_wake_time_text

    await manager.done()
    state: FSMContext = manager.middleware_data["state"]
    await callback.message.answer(ask_wake_time_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_wake_time)


async def on_settings_sleep(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    from bot.handlers.settings import SettingsStates
    from bot.utils.texts import ask_sleep_time_text

    await manager.done()
    state: FSMContext = manager.middleware_data["state"]
    await callback.message.answer(ask_sleep_time_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_sleep_time)


async def on_settings_smoking_profile(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    from bot.handlers.settings import SettingsStates
    from bot.utils.texts import ask_cigarettes_per_day_text

    await manager.done()
    state: FSMContext = manager.middleware_data["state"]
    await callback.message.answer(ask_cigarettes_per_day_text(), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_cigarettes_per_day)


# ── Back button ──────────────────────────────────────────────────────────────
BACK_BTN = SwitchTo(Const("◀️ Назад"), id="back", state=MenuSG.main)


# ── Dialog Windows ───────────────────────────────────────────────────────────


menu_dialog = Dialog(
    # ── Main Menu ────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        Button(
            Const("💊 Принять таблетку"),
            id="take_dose",
            on_click=on_take_dose,
            when="has_course",
        ),
        Row(
            SwitchTo(
                Const("🆘 Хочу закурить"),
                id="sos_nav",
                state=MenuSG.sos,
                on_click=on_sos,
                when="has_course",
            ),
            SwitchTo(
                Const("🚬 Я закурил"),
                id="relapse_nav",
                state=MenuSG.relapse,
                when="has_course",
            ),
        ),
        Row(
            SwitchTo(
                Const("📊 Прогресс"),
                id="progress_nav",
                state=MenuSG.progress,
                when="has_course",
            ),
            SwitchTo(
                Const("🕐 Расписание"),
                id="schedule_nav",
                state=MenuSG.schedule,
                when="has_course",
            ),
        ),
        Row(
            SwitchTo(
                Const("💰 Экономия"),
                id="savings_nav",
                state=MenuSG.savings,
                when="has_course",
            ),
            SwitchTo(
                Const("🏥 Здоровье"),
                id="health_nav",
                state=MenuSG.health,
                when="has_course",
            ),
        ),
        Row(
            SwitchTo(
                Const("🏆 Достижения"),
                id="achiev_nav",
                state=MenuSG.achievements,
                when="has_course",
            ),
            SwitchTo(
                Const("📝 Настроение"),
                id="mood_nav",
                state=MenuSG.mood_history,
                when="has_course",
            ),
        ),
        Row(
            SwitchTo(
                Const("✅ Завершить курс"),
                id="complete_nav",
                state=MenuSG.confirm_complete,
                when="has_course",
            ),
            SwitchTo(
                Const("🛑 Отменить курс"),
                id="cancel_nav",
                state=MenuSG.confirm_cancel,
                when="has_course",
            ),
        ),
        SwitchTo(
            Const("🚀 Начать курс"),
            id="start_nav",
            state=MenuSG.confirm_start,
            when=~F["has_course"],
        ),
        Row(
            SwitchTo(Const("📋 История"), id="history_nav", state=MenuSG.history),
            SwitchTo(Const("⚙️ Настройки"), id="settings_nav", state=MenuSG.settings),
        ),
        SwitchTo(Const("❓ Помощь"), id="help_nav", state=MenuSG.help),
        state=MenuSG.main,
        getter=main_getter,
        parse_mode="HTML",
    ),
    # ── Progress ─────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.progress,
        getter=progress_getter,
        parse_mode="HTML",
    ),
    # ── Schedule ─────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.schedule,
        getter=schedule_getter,
        parse_mode="HTML",
    ),
    # ── Settings ─────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        Button(Const("🌍 Часовой пояс"), id="tz_btn", on_click=on_settings_timezone),
        Button(Const("⏰ Время подъёма"), id="wake_btn", on_click=on_settings_wake),
        Button(Const("🌙 Время сна"), id="sleep_btn", on_click=on_settings_sleep),
        Button(
            Const("🚬 Профиль курильщика"),
            id="profile_btn",
            on_click=on_settings_smoking_profile,
        ),
        BACK_BTN,
        state=MenuSG.settings,
        getter=settings_getter,
        parse_mode="HTML",
    ),
    # ── Help ─────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.help,
        getter=lambda **kwargs: {"text": help_text()},
        parse_mode="HTML",
    ),
    # ── SOS ──────────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.sos,
        getter=sos_getter,
        parse_mode="HTML",
    ),
    # ── Savings ──────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.savings,
        getter=savings_getter,
        parse_mode="HTML",
    ),
    # ── Health ───────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.health,
        getter=health_getter,
        parse_mode="HTML",
    ),
    # ── Achievements ─────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.achievements,
        getter=achievements_getter,
        parse_mode="HTML",
    ),
    # ── Relapse ──────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        TextInput(
            id="relapse_input",
            type_factory=_validate_relapse_count,
            on_success=on_relapse_count_entered,
            on_error=on_relapse_count_error,
        ),
        BACK_BTN,
        state=MenuSG.relapse,
        getter=lambda **kwargs: {"text": relapse_ask_count_text()},
        parse_mode="HTML",
    ),
    # ── Confirm Start ────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        Row(
            Button(
                Const("🚀 Начать новый курс"),
                id="confirm_start",
                on_click=on_confirm_start_course,
            ),
            BACK_BTN,
        ),
        state=MenuSG.confirm_start,
        getter=confirm_start_getter,
        parse_mode="HTML",
    ),
    # ── Confirm Cancel ───────────────────────────────────────────────────
    Window(
        Const("Уверен, что хочешь отменить текущий курс?"),
        Row(
            Button(
                Const("🛑 Да, отменить"),
                id="confirm_cancel",
                on_click=on_confirm_cancel_course,
            ),
            BACK_BTN,
        ),
        state=MenuSG.confirm_cancel,
        parse_mode="HTML",
    ),
    # ── Confirm Complete ─────────────────────────────────────────────────
    Window(
        Format("{text}"),
        Row(
            Button(
                Const("✅ Да, завершить"),
                id="confirm_complete",
                on_click=on_confirm_complete_course,
            ),
            BACK_BTN,
        ),
        state=MenuSG.confirm_complete,
        getter=lambda **kwargs: {"text": confirm_complete_text()},
        parse_mode="HTML",
    ),
    # ── History ──────────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.history,
        getter=history_getter,
        parse_mode="HTML",
    ),
    # ── Mood History ─────────────────────────────────────────────────────
    Window(
        Format("{text}"),
        BACK_BTN,
        state=MenuSG.mood_history,
        getter=mood_history_getter,
        parse_mode="HTML",
    ),
    launch_mode=LaunchMode.ROOT,
)
