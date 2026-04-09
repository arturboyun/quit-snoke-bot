"""All user-facing strings (Russian). Single source for future i18n."""


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
    return (
        "⚠️ У тебя уже есть активный курс.\n"
        "Хочешь отменить его и начать новый?"
    )


def no_active_course_text() -> str:
    return "❌ У тебя нет активного курса. Начни его через меню 👇"


def dose_reminder_text(day: int, phase: int, target: int) -> str:
    return (
        f"💊 Время принять таблетку Табекс!\n\n"
        f"📅 День {day}/25 (фаза {phase})\n"
        f"📊 Цель на сегодня: {target} таблеток\n\n"
        "Нажми кнопку ниже, когда примешь таблетку."
    )


def dose_taken_text(taken_today: int, target: int) -> str:
    return (
        f"✅ Отлично! Приём отмечен.\n"
        f"Сегодня принято: {taken_today}/{target} таблеток"
    )


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
    return (
        f"📊 <b>Прогресс курса</b>\n\n"
        f"📅 День: {stats['day']}/{stats['total_days']}\n"
        f"🔬 Фаза: {stats['phase']}\n"
        f"💊 Принято сегодня: {stats['doses_taken']}/{stats['doses_target']}\n"
        f"📈 Общий прогресс: {bar} {stats['percent_complete']}%"
    )


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
        "Все действия доступны через кнопки меню.\n\n"
        "Если меню пропало — отправь /start"
    )


def menu_text() -> str:
    return "📋 <b>Главное меню</b>\n\nВыбери действие:"


def today_schedule_text(day: int, phase: int, times: list[str], target: int) -> str:
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
