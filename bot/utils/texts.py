"""All user-facing strings (Russian). Single source for future i18n."""

import random


def welcome_text() -> str:
    return (
        "👋 Привет! Я бот-помощник для отказа от курения с препаратом Табекс.\n\n"
        "Я помогу тебе пройти полный 25-дневный курс:\n"
        "• Напомню вовремя принять таблетку\n"
        "• Отслежу прогресс\n"
        "• Подскажу, когда нужно полностью бросить курить\n\n"
        "Для начала давай настроим время пробуждения и сна."
    )


def ask_timezone_text() -> str:
    return (
        "🌍 В каком часовом поясе ты находишься?\n\n"
        "Отправь название, например: <b>Europe/Moscow</b>, <b>Asia/Yekaterinburg</b>\n\n"
        "Или выбери из популярных ниже:"
    )


def ask_wake_time_text() -> str:
    return (
        "⏰ Во сколько ты обычно просыпаешься?\n\n"
        "Отправь время в формате <b>ЧЧ:ММ</b>, например: <b>07:00</b>"
    )


def ask_sleep_time_text() -> str:
    return (
        "🌙 Во сколько ты обычно ложишься спать?\n\n"
        "Отправь время в формате <b>ЧЧ:ММ</b>, например: <b>23:00</b>"
    )


def settings_saved_text() -> str:
    return "✅ Настройки сохранены!"


def course_started_text(start_date: str) -> str:
    return (
        f"🚀 Курс начат! Дата старта: <b>{start_date}</b>\n\n"
        "📋 Схема приёма Табекс:\n"
        "• Дни 1–3: каждые 2 часа (6 таблеток/день)\n"
        "• Дни 4–12: каждые 2.5 часа (5 таблеток/день)\n"
        "• Дни 13–16: каждые 3 часа (4 таблетки/день)\n"
        "• Дни 17–20: каждые 5 часов (3 таблетки/день)\n"
        "• Дни 21–25: каждые 5 часов (1–2 таблетки/день)\n\n"
        "⚠️ <b>На 5-й день ты должен полностью прекратить курить!</b>\n\n"
        "Я буду присылать напоминания о каждом приёме 💊"
    )


def already_has_course_text() -> str:
    return "⚠️ У тебя уже есть активный курс.\nХочешь отменить его и начать новый?"


def no_active_course_text() -> str:
    return "❌ У тебя нет активного курса. Начни его через меню 👇"


def dose_reminder_text(day: int, phase: int, target: int | str) -> str:
    return (
        f"💊 Время принять таблетку Табекс!\n\n"
        f"📅 День {day}/25 (фаза {phase})\n"
        f"📊 Цель на сегодня: {target} таблеток\n\n"
        "Нажми кнопку ниже, когда примешь таблетку."
    )


def dose_taken_text(taken_today: int, target: int | str) -> str:
    return f"✅ Отлично! Приём отмечен.\nСегодня принято: {taken_today}/{target} таблеток"


def quit_day_text() -> str:
    return (
        "🚭 <b>СЕГОДНЯ ДЕНЬ 5 — ПОЛНЫЙ ОТКАЗ ОТ КУРЕНИЯ!</b>\n\n"
        "С сегодняшнего дня ты должен полностью прекратить курить.\n"
        "Продолжай принимать Табекс по расписанию — "
        "он поможет справиться с тягой к никотину.\n\n"
        "💪 Ты справишься!"
    )


def progress_text(stats: dict) -> str:
    bar_filled = int(stats["percent_complete"] / 10)
    bar = "▓" * bar_filled + "░" * (10 - bar_filled)
    lines = [
        "📊 <b>Прогресс курса</b>\n",
        f"📅 День: {stats['day']}/{stats['total_days']}",
        f"🔬 Фаза: {stats['phase']}",
        f"💊 Принято сегодня: {stats['doses_taken']}/{stats['doses_target']}",
        f"📈 Общий прогресс: {bar} {stats['percent_complete']}%",
    ]
    if "smoke_free_days" in stats:
        lines.append(f"🚭 Дней без сигарет: {stats['smoke_free_days']}")
    return "\n".join(lines)


def course_completed_text() -> str:
    return (
        "🎉 <b>Поздравляю! 25-дневный курс Табекс завершён!</b>\n\n"
        "Ты прошёл полный курс лечения. Если чувствуешь, что тяга к курению "
        "ещё есть — обратись к врачу для консультации.\n\n"
        "Удачи! 🍀"
    )


def course_cancelled_text() -> str:
    return "🛑 Курс отменён. Ты можешь начать новый через меню 👇"


def invalid_time_format_text() -> str:
    return "❌ Неверный формат. Отправь время как <b>ЧЧ:ММ</b>, например: <b>08:00</b>"


def invalid_timezone_text() -> str:
    return "❌ Неизвестный часовой пояс. Попробуй, например: <b>Europe/Kyiv</b>"


def help_text() -> str:
    return (
        "📋 <b>Помощь</b>\n\n"
        "Все действия доступны через кнопки меню:\n\n"
        "💊 <b>Принять таблетку</b> — отметить приём\n"
        "🆘 <b>Хочу закурить</b> — SOS при тяге\n"
        "🚬 <b>Я закурил</b> — дневник срывов\n"
        "📊 <b>Прогресс</b> — статистика курса\n"
        "🕐 <b>Расписание</b> — приёмы на сегодня\n"
        "💰 <b>Экономия</b> — сколько сэкономил\n"
        "🏥 <b>Здоровье</b> — таймлайн восстановления\n"
        "🏆 <b>Достижения</b> — бейджи и награды\n"
        "📝 <b>Настроение</b> — история самочувствия\n\n"
        "Если меню пропало — отправь /start"
    )


def menu_text() -> str:
    return "📋 <b>Главное меню</b>\n\nВыбери действие:"


def today_schedule_text(day: int, phase: int, times: list[str], target: int | str) -> str:
    times_str = "\n".join(f"  • {t}" for t in times)
    return (
        f"📅 <b>Расписание на сегодня</b>\n\n"
        f"День {day}/25 (фаза {phase})\n"
        f"Цель: {target} таблеток\n\n"
        f"⏰ Время приёма:\n{times_str}"
    )


def settings_menu_text(timezone: str, wake: str, sleep: str) -> str:
    return (
        f"⚙️ <b>Текущие настройки</b>\n\n"
        f"🌍 Часовой пояс: {timezone}\n"
        f"⏰ Подъём: {wake}\n"
        f"🌙 Сон: {sleep}\n\n"
        "Что хочешь изменить?"
    )


# ── Smoking Profile (savings calculator) ─────────────────────────────────────


def ask_cigarettes_per_day_text() -> str:
    return "🚬 Сколько сигарет в день ты куришь (или курил)?\n\nОтправь число, например: <b>20</b>"


def ask_pack_price_text() -> str:
    return (
        "💰 Сколько стоит пачка сигарет (в твоей валюте)?\n\nОтправь число, например: <b>150</b>"
    )


def smoking_profile_saved_text() -> str:
    return "✅ Профиль курильщика сохранён! Теперь я буду считать твою экономию 💰"


def savings_text(
    days_smoke_free: int,
    cigarettes_avoided: int,
    money_saved: float,
    money_examples: list[str],
) -> str:
    examples_str = "\n".join(f"  • {e}" for e in money_examples)
    return (
        f"💰 <b>Калькулятор экономии</b>\n\n"
        f"🚭 Дней без сигарет: {days_smoke_free}\n"
        f"🚬 Сигарет не выкурено: {cigarettes_avoided}\n"
        f"💵 Сэкономлено: <b>{money_saved:.0f}</b>\n\n"
        f"На эти деньги можно:\n{examples_str}"
    )


def no_smoking_profile_text() -> str:
    return "📊 Сначала заполни профиль курильщика через настройки, чтобы видеть экономию."


# ── SOS Craving ──────────────────────────────────────────────────────────────

_BREATHING_EXERCISES = [
    (
        "🫁 <b>Дыхание 4-7-8</b>\n\n"
        "1. Вдох через нос — <b>4 секунды</b>\n"
        "2. Задержка — <b>7 секунд</b>\n"
        "3. Выдох через рот — <b>8 секунд</b>\n\n"
        "Повтори 3–4 раза. Тяга пройдёт через 5 минут!"
    ),
    (
        "🫁 <b>Квадратное дыхание</b>\n\n"
        "1. Вдох — <b>4 секунды</b>\n"
        "2. Задержка — <b>4 секунды</b>\n"
        "3. Выдох — <b>4 секунды</b>\n"
        "4. Пауза — <b>4 секунды</b>\n\n"
        "Повтори 5 раз. Ты справишься!"
    ),
    (
        "🫁 <b>Глубокое дыхание</b>\n\n"
        "1. Положи руку на живот\n"
        "2. Медленный вдох через нос — <b>5 секунд</b>\n"
        "3. Почувствуй, как поднимается живот\n"
        "4. Медленный выдох через рот — <b>5 секунд</b>\n\n"
        "Повтори 6 раз. Тяга — временная!"
    ),
]

_MOTIVATION_FACTS = [
    "Через 20 минут без сигареты пульс и давление приходят в норму.",
    "Через 8 часов уровень кислорода в крови нормализуется.",
    "Через 24 часа риск сердечного приступа начинает снижаться.",
    "Через 48 часов восстанавливаются вкус и обоняние.",
    "Через 72 часа бронхи расслабляются — дышать становится легче.",
    "Через 2 недели улучшается кровообращение и функция лёгких.",
    "Через 1 месяц уменьшается кашель и одышка.",
    "Через 1 год риск ишемической болезни сердца снижается вдвое.",
    "Через 5 лет риск инсульта сравняется с некурящим.",
    "Через 10 лет риск рака лёгких снижается вдвое.",
    "Каждая невыкуренная сигарета — это 11 минут жизни, которые ты вернул себе.",
    "Средний курильщик тратит более 50 000 в год на сигареты.",
    "Уже через 3 дня никотин полностью выводится из организма.",
    "Бросившие курить отмечают улучшение сна уже через неделю.",
]


def sos_craving_text(
    days_smoke_free: int,
    cravings_resisted: int,
) -> str:
    exercise = random.choice(_BREATHING_EXERCISES)
    fact = random.choice(_MOTIVATION_FACTS)
    parts = [
        "🆘 <b>Тяга к сигарете? Держись!</b>\n",
        exercise,
        f"\n💡 <b>Факт:</b> {fact}\n",
    ]
    if days_smoke_free > 0:
        parts.append(f"\n🚭 Ты уже <b>{days_smoke_free}</b> дн. без сигарет — не сдавайся!")
    if cravings_resisted > 0:
        parts.append(f"🛡️ Ты уже справился с тягой <b>{cravings_resisted}</b> раз!")
    parts.append("\n⏰ <b>Тяга длится 3–5 минут. Просто подожди — она пройдёт!</b>")
    return "\n".join(parts)


# ── Health Recovery Timeline ─────────────────────────────────────────────────

_HEALTH_MILESTONES = [
    (20, "min", "💓 Пульс и давление приходят в норму"),
    (8, "hours", "🫁 Уровень кислорода в крови нормализуется"),
    (24, "hours", "❤️ Риск сердечного приступа начинает снижаться"),
    (48, "hours", "👅 Восстанавливаются вкус и обоняние"),
    (72, "hours", "🌬️ Бронхи расслабляются, дышать легче"),
    (14, "days", "🏃 Улучшается кровообращение и функция лёгких"),
    (30, "days", "😮‍💨 Уменьшается кашель и одышка"),
    (90, "days", "💪 Функция лёгких улучшается на 30%"),
    (365, "days", "❤️‍🩹 Риск ишемической болезни снижается вдвое"),
    (1825, "days", "🧠 Риск инсульта = как у некурящего"),
    (3650, "days", "🎗️ Риск рака лёгких снижается вдвое"),
]


def health_timeline_text(hours_smoke_free: float) -> str:
    lines = ["🏥 <b>Восстановление здоровья</b>\n"]

    for value, unit, description in _HEALTH_MILESTONES:
        if unit == "min":
            milestone_hours = value / 60
        elif unit == "hours":
            milestone_hours = value
        else:  # days
            milestone_hours = value * 24

        if hours_smoke_free >= milestone_hours:
            lines.append(f"  ✅ {description}")
        else:
            # Calculate how much time left
            remaining_hours = milestone_hours - hours_smoke_free
            if remaining_hours < 1:
                time_left = f"{int(remaining_hours * 60)} мин"
            elif remaining_hours < 24:
                time_left = f"{int(remaining_hours)} ч"
            elif remaining_hours < 730:
                time_left = f"{int(remaining_hours / 24)} дн"
            elif remaining_hours < 8760:
                time_left = f"{int(remaining_hours / 730)} мес"
            else:
                time_left = f"{remaining_hours / 8760:.1f} лет"
            lines.append(f"  ⏳ {description} (через {time_left})")

    return "\n".join(lines)


# ── Achievements ─────────────────────────────────────────────────────────────


def achievements_text(
    earned: list[tuple[str, str, str]],
    total: int,
) -> str:
    """earned is list of (key, title, description)."""
    lines = [f"🏆 <b>Достижения</b> ({len(earned)}/{total})\n"]
    if not earned:
        lines.append("Пока нет достижений. Продолжай — они скоро появятся! 💪")
    else:
        for _key, title, desc in earned:
            lines.append(f"  {title} — <i>{desc}</i>")
    return "\n".join(lines)


def new_achievement_text(title: str, description: str) -> str:
    return f"🏆 <b>Новое достижение!</b>\n\n{title}\n<i>{description}</i>"


# ── Relapse Diary ────────────────────────────────────────────────────────────


def relapse_ask_count_text() -> str:
    return (
        "Ничего страшного — срыв не означает провал. 💙\n\n"
        "Сколько сигарет ты выкурил? Отправь число:"
    )


def relapse_logged_text(
    total_relapses: int,
    total_cigarettes: int,
    cigarettes_per_day_before: int | None,
) -> str:
    lines = [
        "📝 <b>Записано</b>\n",
        "Срыв — это часть процесса, не конец пути.",
        "Важно, что ты продолжаешь курс!\n",
        f"📊 Всего срывов: {total_relapses}",
        f"🚬 Всего сигарет: {total_cigarettes}",
    ]
    if cigarettes_per_day_before and total_relapses > 0:
        avg = total_cigarettes / max(total_relapses, 1)
        lines.append(
            f"\n💡 Раньше: {cigarettes_per_day_before} сигарет/день. "
            f"Сейчас в среднем: {avg:.1f} за срыв — прогресс!"
        )
    lines.append("\n💪 Продолжай принимать Табекс по расписанию.")
    return "\n".join(lines)


# ── Morning Check-in ─────────────────────────────────────────────────────────


def morning_checkin_text(day: int) -> str:
    return f"☀️ Доброе утро! День {day}/25\n\nКак ты себя чувствуешь сегодня?"


def mood_logged_text(mood_emoji: str) -> str:
    responses = {
        "good": "Отлично! Хорошее настроение — отличный помощник в борьбе с курением! 🎉",
        "neutral": "Нормально — это тоже хорошо. Продолжай двигаться вперёд! 👍",
        "bad": (
            "Понимаю, бывают тяжёлые дни. Помни: это временно, "
            "и с каждым днём будет легче. Если тяжело — нажми кнопку SOS 🆘"
        ),
    }
    return responses.get(mood_emoji, "Записано! 👍")


def mood_history_text(moods: list[tuple[str, str]]) -> str:
    """moods is list of (date_str, mood)."""
    emoji_map = {"good": "😊", "neutral": "😐", "bad": "😟"}
    lines = ["📊 <b>Настроение за последние дни</b>\n"]
    if not moods:
        lines.append("Пока нет записей.")
    else:
        for date_str, mood in moods:
            lines.append(f"  {date_str}: {emoji_map.get(mood, '❓')}")
    return "\n".join(lines)


def phase_change_text(new_phase: int, interval_minutes: int, target_tablets: int | str) -> str:
    hours = interval_minutes / 60
    if hours == int(hours):
        interval_str = f"{int(hours)} ч"
    else:
        interval_str = f"{hours:.1f} ч"
    return (
        f"🔄 <b>Переход на фазу {new_phase}!</b>\n\n"
        f"Новый режим приёма:\n"
        f"• Интервал: каждые {interval_str}\n"
        f"• Таблеток в день: {target_tablets}\n\n"
        "Продолжай следовать расписанию 💪"
    )


def missed_doses_text(missed: int, day: int) -> str:
    return (
        f"⚠️ Вчера (день {day}) пропущено таблеток: <b>{missed}</b>\n\n"
        "Помни: пропущенные дозы <b>нельзя</b> удваивать. "
        "Просто продолжай по расписанию."
    )


def course_completed_manual_text() -> str:
    return (
        "✅ Курс завершён досрочно.\n\n"
        "Если чувствуешь тягу к курению — обратись к врачу. Удачи! 🍀"
    )


def course_history_text(courses: list) -> str:
    if not courses:
        return "📋 История курсов пуста."
    lines = ["📋 <b>История курсов</b>\n"]
    for i, c in enumerate(courses, 1):
        status_emoji = {"active": "🟢", "completed": "✅", "cancelled": "🛑"}.get(
            c.status.value,
            "⚪",
        )
        lines.append(f"{i}. {status_emoji} Начат: {c.start_date.isoformat()} — {c.status.value}")
    return "\n".join(lines)


def dose_too_soon_text(minutes_left: int) -> str:
    return f"⏳ Слишком рано для следующей таблетки.\nПодожди ещё {minutes_left} мин."


def dose_followup_text(day: int, phase: int, target: int | str) -> str:
    return (
        f"⏰ Напоминание: ты ещё не отметил приём таблетки!\n\n"
        f"📅 День {day}/25 (фаза {phase})\n"
        f"📊 Цель на сегодня: {target} таблеток\n\n"
        "Если ты уже принял — нажми кнопку ниже 👇"
    )
