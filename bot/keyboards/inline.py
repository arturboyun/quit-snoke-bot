from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class DoseCallback(CallbackData, prefix="dose"):
    action: str  # "taken"
    course_id: int
    day: int
    phase: int


class CourseCallback(CallbackData, prefix="course"):
    action: str  # "confirm_start", "cancel", "confirm_cancel"


class SettingsCallback(CallbackData, prefix="settings"):
    action: str  # "timezone", "wake_time", "sleep_time", "smoking_profile"


class MenuCallback(CallbackData, prefix="menu"):
    action: str  # "take_dose", "progress", "schedule", "settings", "help",
    #              "start_course", "cancel_course", "back",
    #              "sos", "savings", "health", "achievements", "relapse", "mood_history"


class MoodCallback(CallbackData, prefix="mood"):
    value: str  # "good", "neutral", "bad"


POPULAR_TIMEZONES = [
    "Europe/Kyiv",
    "Europe/Warsaw",
    "Europe/Berlin",
    "Europe/London",
    "America/New_York",
    "Asia/Istanbul",
]


def dose_taken_keyboard(course_id: int, day: int, phase: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принял таблетку",
                    callback_data=DoseCallback(
                        action="taken",
                        course_id=course_id,
                        day=day,
                        phase=phase,
                    ).pack(),
                ),
            ],
        ],
    )


def confirm_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Начать новый курс",
                    callback_data=CourseCallback(action="confirm_start").pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=CourseCallback(action="cancel").pack(),
                ),
            ],
        ],
    )


def confirm_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛑 Да, отменить",
                    callback_data=CourseCallback(action="confirm_cancel").pack(),
                ),
                InlineKeyboardButton(
                    text="Нет, продолжить",
                    callback_data=CourseCallback(action="cancel").pack(),
                ),
            ],
        ],
    )


def timezone_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=tz, callback_data=f"tz:{tz}")] for tz in POPULAR_TIMEZONES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Часовой пояс",
                    callback_data=SettingsCallback(action="timezone").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Время подъёма",
                    callback_data=SettingsCallback(action="wake_time").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌙 Время сна",
                    callback_data=SettingsCallback(action="sleep_time").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚬 Профиль курильщика",
                    callback_data=SettingsCallback(action="smoking_profile").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=MenuCallback(action="back").pack(),
                ),
            ],
        ],
    )


def mood_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="😊 Хорошо",
                    callback_data=MoodCallback(value="good").pack(),
                ),
                InlineKeyboardButton(
                    text="😐 Нормально",
                    callback_data=MoodCallback(value="neutral").pack(),
                ),
                InlineKeyboardButton(
                    text="😟 Плохо",
                    callback_data=MoodCallback(value="bad").pack(),
                ),
            ],
        ],
    )


def main_menu_keyboard(has_course: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if has_course:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💊 Принять таблетку",
                    callback_data=MenuCallback(action="take_dose").pack(),
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="🆘 Хочу закурить",
                    callback_data=MenuCallback(action="sos").pack(),
                ),
                InlineKeyboardButton(
                    text="🚬 Я закурил",
                    callback_data=MenuCallback(action="relapse").pack(),
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="📊 Прогресс",
                    callback_data=MenuCallback(action="progress").pack(),
                ),
                InlineKeyboardButton(
                    text="🕐 Расписание",
                    callback_data=MenuCallback(action="schedule").pack(),
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="💰 Экономия",
                    callback_data=MenuCallback(action="savings").pack(),
                ),
                InlineKeyboardButton(
                    text="🏥 Здоровье",
                    callback_data=MenuCallback(action="health").pack(),
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="🏆 Достижения",
                    callback_data=MenuCallback(action="achievements").pack(),
                ),
                InlineKeyboardButton(
                    text="📝 Настроение",
                    callback_data=MenuCallback(action="mood_history").pack(),
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Завершить курс",
                    callback_data=MenuCallback(action="complete_course").pack(),
                ),
                InlineKeyboardButton(
                    text="🛑 Отменить курс",
                    callback_data=MenuCallback(action="cancel_course").pack(),
                ),
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🚀 Начать курс",
                    callback_data=MenuCallback(action="start_course").pack(),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="📋 История",
                callback_data=MenuCallback(action="history").pack(),
            ),
            InlineKeyboardButton(
                text="⚙️ Настройки",
                callback_data=MenuCallback(action="settings").pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="❓ Помощь",
                callback_data=MenuCallback(action="help").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
