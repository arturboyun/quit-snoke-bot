"""Main menu: inline keyboard with quick access to all features."""

import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db.engine import session_factory
from bot.keyboards.inline import (
    MenuCallback,
    confirm_cancel_keyboard,
    confirm_start_keyboard,
    main_menu_keyboard,
    settings_keyboard,
)
from bot.services.course import (
    ACHIEVEMENT_DEFS,
    check_and_grant_achievements,
    complete_course,
    get_active_course,
    get_course_history,
    get_craving_count,
    get_doses_taken_today,
    get_last_dose_time,
    get_mood_history,
    get_or_create_user,
    get_relapse_stats,
    get_smoking_profile,
    get_user_achievements,
    grant_achievement,
    log_craving,
    log_dose,
    log_relapse,
    start_course,
)
from bot.services.schedule import (
    QUIT_DAY,
    calculate_dose_times,
    get_course_day,
    get_phase,
    get_progress,
)
from bot.taskiq_broker import schedule_source
from bot.tasks import schedule_daily_doses, schedule_next_day
from bot.utils.texts import (
    achievements_text,
    already_has_course_text,
    course_completed_manual_text,
    course_history_text,
    course_started_text,
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

router = Router()


class RelapseStates(StatesGroup):
    waiting_cigarette_count = State()


async def _safe_edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, parse_mode="HTML", **kwargs)
    except TelegramBadRequest:
        pass


async def _menu_kb(user_id: int) -> main_menu_keyboard:
    async with session_factory() as session:
        course = await get_active_course(session, user_id)
    return main_menu_keyboard(has_course=course is not None)


@router.callback_query(MenuCallback.filter(F.action == "back"))
async def on_menu_back(callback: CallbackQuery) -> None:
    kb = await _menu_kb(callback.from_user.id)
    await _safe_edit(callback, menu_text(), reply_markup=kb)
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "start_course"))
async def on_menu_start_course(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if active:
            await _safe_edit(
                callback,
                already_has_course_text(),
                reply_markup=confirm_start_keyboard(),
            )
            await callback.answer()
            return

        user = await get_or_create_user(session, callback.from_user.id)
        today = datetime.datetime.now(ZoneInfo(user.timezone)).date()
        await start_course(session, callback.from_user.id, today)
        await session.commit()

    await _safe_edit(
        callback,
        course_started_text(today.isoformat()),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()

    await schedule_source.startup()
    await schedule_daily_doses.kiq(callback.from_user.id)
    await schedule_next_day.kiq(callback.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "cancel_course"))
async def on_menu_cancel_course(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        active = await get_active_course(session, callback.from_user.id)
        if not active:
            await callback.answer("Нет активного курса", show_alert=True)
            return

    await _safe_edit(
        callback,
        "Уверен, что хочешь отменить текущий курс?",
        reply_markup=confirm_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "take_dose"))
async def on_menu_take_dose(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        now = datetime.datetime.now(tz)
        today = now.date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

        phase_info = get_phase(day)

        taken = await get_doses_taken_today(session, course.id, today)
        if taken >= phase_info.target_tablets:
            await callback.answer(
                f"Сегодня уже принято {taken}/{phase_info.target_display} таблеток",
                show_alert=True,
            )
            return

        # Check minimum interval since last dose
        last_time = await get_last_dose_time(session, course.id, day)
        if last_time is not None:
            last_aware = last_time if last_time.tzinfo else last_time.replace(tzinfo=datetime.UTC)
            elapsed = (
                now.astimezone(datetime.UTC) - last_aware.astimezone(datetime.UTC)
            ).total_seconds()
            min_interval = phase_info.interval_minutes * 60
            if elapsed < min_interval:
                minutes_left = int((min_interval - elapsed) / 60) + 1
                await callback.answer(
                    dose_too_soon_text(minutes_left),
                    show_alert=True,
                )
                return

        await log_dose(
            session,
            course_id=course.id,
            user_id=callback.from_user.id,
            scheduled_at=now,
            day=day,
            phase=phase_info.phase,
        )
        taken = await get_doses_taken_today(session, course.id, today)
        newly_earned = await check_and_grant_achievements(
            session, callback.from_user.id, timezone=user.timezone
        )
        await session.commit()

    text = dose_taken_text(taken, phase_info.target_display)
    for key in newly_earned:
        if key in ACHIEVEMENT_DEFS:
            title, desc = ACHIEVEMENT_DEFS[key]
            text += f"\n\n{new_achievement_text(title, desc)}"

    await _safe_edit(
        callback,
        text,
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer("✅ Отмечено!")


@router.callback_query(MenuCallback.filter(F.action == "progress"))
async def on_menu_progress(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

        taken = await get_doses_taken_today(session, course.id, today)

    stats = get_progress(day, taken)
    if day >= QUIT_DAY:
        stats["smoke_free_days"] = max(0, day - QUIT_DAY)
    await _safe_edit(
        callback,
        progress_text(stats),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "schedule"))
async def on_menu_schedule(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)

        if day < 1 or day > 25:
            await callback.answer("Курс завершён", show_alert=True)
            return

    phase_info = get_phase(day)
    slots = calculate_dose_times(
        day=day,
        wake_time=user.wake_time,
        sleep_time=user.sleep_time,
        course_start_date=course.start_date,
        timezone=user.timezone,
    )
    times = [s.time.strftime("%H:%M") for s in slots]

    await _safe_edit(
        callback,
        today_schedule_text(day, phase_info.phase, times, phase_info.target_display),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "settings"))
async def on_menu_settings(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        user = await get_or_create_user(session, callback.from_user.id)

    await _safe_edit(
        callback,
        settings_menu_text(
            user.timezone,
            user.wake_time.strftime("%H:%M"),
            user.sleep_time.strftime("%H:%M"),
        ),
        reply_markup=settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "help"))
async def on_menu_help(callback: CallbackQuery) -> None:
    kb = await _menu_kb(callback.from_user.id)
    await _safe_edit(callback, help_text(), reply_markup=kb)
    await callback.answer()


# ── SOS Craving ──────────────────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "sos"))
async def on_menu_sos(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        tz = ZoneInfo(user.timezone)
        today = datetime.datetime.now(tz).date()
        day = get_course_day(course.start_date, today)
        days_smoke_free = max(0, day - QUIT_DAY) if day >= QUIT_DAY else 0

        await log_craving(session, callback.from_user.id)
        cravings = await get_craving_count(session, callback.from_user.id)
        newly_earned = await check_and_grant_achievements(
            session, callback.from_user.id, timezone=user.timezone
        )
        await session.commit()

    text = sos_craving_text(days_smoke_free, cravings)

    # Notify about new achievements
    for key in newly_earned:
        if key in ACHIEVEMENT_DEFS:
            title, desc = ACHIEVEMENT_DEFS[key]
            text += f"\n\n{new_achievement_text(title, desc)}"

    await _safe_edit(
        callback,
        text,
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


# ── Savings Calculator ───────────────────────────────────────────────────────


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


@router.callback_query(MenuCallback.filter(F.action == "savings"))
async def on_menu_savings(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)
        profile = await get_smoking_profile(session, callback.from_user.id)

    if not profile:
        await _safe_edit(
            callback,
            no_smoking_profile_text(),
            reply_markup=main_menu_keyboard(has_course=True),
        )
        await callback.answer()
        return

    tz = ZoneInfo(user.timezone)
    today = datetime.datetime.now(tz).date()
    day = get_course_day(course.start_date, today)
    days_smoke_free = max(0, day - QUIT_DAY) if day >= QUIT_DAY else 0

    cigarettes_avoided = days_smoke_free * profile.cigarettes_per_day
    price_per_cigarette = profile.pack_price / profile.cigarettes_in_pack
    money_saved = cigarettes_avoided * price_per_cigarette
    examples = _money_examples(money_saved)

    await _safe_edit(
        callback,
        savings_text(days_smoke_free, cigarettes_avoided, money_saved, examples),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


# ── Health Recovery Timeline ─────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "health"))
async def on_menu_health(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        user = await get_or_create_user(session, callback.from_user.id)

    tz = ZoneInfo(user.timezone)
    now = datetime.datetime.now(tz)
    day = get_course_day(course.start_date, now.date())

    if day < QUIT_DAY:
        hours_smoke_free = 0.0
    else:
        quit_date = course.start_date + datetime.timedelta(days=QUIT_DAY - 1)
        quit_dt = datetime.datetime.combine(quit_date, datetime.time(0, 0), tzinfo=tz)
        hours_smoke_free = (now - quit_dt).total_seconds() / 3600

    await _safe_edit(
        callback,
        health_timeline_text(hours_smoke_free),
        reply_markup=main_menu_keyboard(has_course=True),
    )
    await callback.answer()


# ── Achievements ─────────────────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "achievements"))
async def on_menu_achievements(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        earned = await get_user_achievements(session, callback.from_user.id)
        await check_and_grant_achievements(
            session, callback.from_user.id, timezone=user.timezone
        )
        earned = await get_user_achievements(session, callback.from_user.id)
        await session.commit()

    earned_list = []
    for a in earned:
        if a.key in ACHIEVEMENT_DEFS:
            title, desc = ACHIEVEMENT_DEFS[a.key]
            earned_list.append((a.key, title, desc))

    await _safe_edit(
        callback,
        achievements_text(earned_list, len(ACHIEVEMENT_DEFS)),
        reply_markup=await _menu_kb(callback.from_user.id),
    )
    await callback.answer()


# ── Relapse Diary ────────────────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "relapse"))
async def on_menu_relapse(callback: CallbackQuery, state: FSMContext) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

    await _safe_edit(callback, relapse_ask_count_text())
    await state.set_state(RelapseStates.waiting_cigarette_count)
    await callback.answer()


@router.message(RelapseStates.waiting_cigarette_count)
async def on_relapse_count(message: Message, state: FSMContext) -> None:
    try:
        count = int(message.text.strip())
        if count < 1 or count > 100:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Отправь число от 1 до 100.")
        return

    async with session_factory() as session:
        await log_relapse(session, message.from_user.id, count)
        stats = await get_relapse_stats(session, message.from_user.id)
        profile = await get_smoking_profile(session, message.from_user.id)
        await session.commit()

    cpd = profile.cigarettes_per_day if profile else None

    await state.clear()
    async with session_factory() as session:
        course = await get_active_course(session, message.from_user.id)

    await message.answer(
        relapse_logged_text(stats["count"], stats["total_cigarettes"], cpd),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(has_course=course is not None),
    )


# ── Complete Course ───────────────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "complete_course"))
async def on_menu_complete_course(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        course = await get_active_course(session, callback.from_user.id)
        if not course:
            await callback.answer("Нет активного курса", show_alert=True)
            return

        await complete_course(session, callback.from_user.id)
        await grant_achievement(session, callback.from_user.id, "course_completed")
        await session.commit()

    await _safe_edit(
        callback,
        course_completed_manual_text(),
        reply_markup=main_menu_keyboard(has_course=False),
    )
    await callback.answer()


# ── Course History ───────────────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "history"))
async def on_menu_history(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        courses = await get_course_history(session, callback.from_user.id)

    await _safe_edit(
        callback,
        course_history_text(courses),
        reply_markup=await _menu_kb(callback.from_user.id),
    )
    await callback.answer()


# ── Mood History ─────────────────────────────────────────────────────────────


@router.callback_query(MenuCallback.filter(F.action == "mood_history"))
async def on_menu_mood_history(callback: CallbackQuery) -> None:
    async with session_factory() as session:
        moods = await get_mood_history(session, callback.from_user.id)

    mood_list = [(m.created_at.strftime("%d.%m"), m.mood) for m in moods]

    await _safe_edit(
        callback,
        mood_history_text(mood_list),
        reply_markup=await _menu_kb(callback.from_user.id),
    )
    await callback.answer()
