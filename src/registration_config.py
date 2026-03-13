"""
Конфигурация регистрационного опроса.
Единый файл для настройки всех вопросов регистрации.

Следует принципам SOLID:
- Single Responsibility: каждый класс отвечает за свою задачу
- Open/Closed: легко расширять новыми полями без изменения существующего кода
- Liskov Substitution: все валидаторы/форматтеры взаимозаменяемы
- Interface Segregation: отдельные интерфейсы для разных компонентов
- Dependency Inversion: зависимости от абстракций, а не от конкретных классов
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .constants import (
    ABOUT_TRIP,
    ADMIN_FORWARD_MESSAGE,
    ADMIN_SEND_MESSAGE,
    CANCEL,
    CHANGE_DATA,
    EDIT,
    REGISTERED,
    WHAT_TO_BRING,
)
from .messages import (
    ACK_EXPECTATIONS,
    ACK_NAME,
    ADMIN_SEND_MESSAGE_PROMPT,
    DEFAULT_NOT_SPECIFIED,
    EDIT_PROMPT,
    LABEL_BIRTH_DATE,
    LABEL_EXPECTATIONS,
    LABEL_GROUP,
    LABEL_NAME,
    LABEL_PHONE,
    LABEL_TELEGRAM_FULLNAME,
    LABEL_USERNAME,
    LABEL_WILL_DRIVE,
    QUESTION_BIRTH_DATE,
    QUESTION_EXPECTATIONS,
    QUESTION_GROUP,
    QUESTION_NAME,
    QUESTION_PHONE,
    QUESTION_WILL_DRIVE,
    REGISTERED_MESSAGE_HEADER,
    TRIP_POLL_ACKNOWLEDGMENTS,
    TRIP_POLL_MESSAGE,
    TRIP_POLL_OPTIONS,
    WILL_DRIVE_ACKNOWLEDGMENTS,
    WILL_DRIVE_OPTIONS,
)
from .survey.auto_collectors import (
    auto_collect_full_name,
    auto_collect_username,
)
from .survey.formatters import (
    format_date_db,
    format_default_display,
    format_group_db,
    format_phone_db,
    format_phone_display,
    format_text_db,
    format_username_db,
)
from .survey.validators import (
    validate_date,
    validate_group,
    validate_non_empty,
    validate_phone,
)

# Константы для вариантов ответов (оставляем здесь, так как они специфичны для конфигурации)
POSITIONS = ["Вожатый", "Подменка", "Физрук", "Кружковод", "Фотограф", "Радист", "Культорг"]
AGES = ["6-9", "10-12", "12-14", "14-16"]
PROBABILITIES = ["0-25", "25-50", "50-75", "75-100"]
EDUCATION_OPTIONS = ["МГТУ им. Баумана", "Другое учебное заведение", "Закончил(а)", "Не учусь"]
YES_NO = ["Да", "Нет"]


@dataclass
class SurveyField:
    """
    Конфигурация поля опроса.

    Содержит всю необходимую информацию для обработки одного вопроса:
    - Поле в базе данных
    - Что отправить пользователю
    - Какие могут быть варианты
    - Как валидировать введённые данные
    - Как их обработать перед сохранением в БД
    - Как их обрабатывать для вывода пользователю
    - Можно ли пропустить вопрос
    """

    # Основные параметры
    field_name: str  # Поле в базе данных
    label: str  # Что показать пользователю
    message: str | None = None  # Текст вопроса

    # Валидация
    validator: Callable[[str], tuple[bool, str | None]] | None = None  # Как валидировать

    # Форматирование
    db_formatter: Callable[[str], str | None] | None = None  # Как обработать для БД
    display_formatter: Callable[[str], str] | None = None  # Как обработать для вывода

    # Варианты ответов
    options: list[str] | None = None  # Варианты ответов
    multi_select: bool = False  # Можно ли выбрать несколько

    # Специальные возможности
    request_contact: bool = False  # Запросить контакт
    auto_collect: Callable[[Any], str | None] | None = None  # Автосбор данных
    skip_if: Callable[[dict[str, Any]], bool] | None = None  # Условие пропуска

    # Настройки редактирования
    editable: bool = True  # Можно ли редактировать

    # Настройки отображения
    hidden: bool = False  # Скрыть поле от отображения пользователю

    # Сообщения после ввода
    acknowledgment_message: str | None = None  # Сообщение после успешного ввода данных
    option_acknowledgments: dict[str, str] | None = None  # Сообщения для каждого варианта ответа

    # Тип поля в БД
    db_type: str = "TEXT"  # Тип поля в БД


class RegistrationSurveyConfig:
    """Конфигурация регистрационного опроса."""

    def __init__(self) -> None:
        self._fields = self._create_fields()
        self._post_registration_states = self._create_post_registration_states()
        self._admin_states = self._create_admin_states()

    def _create_fields(self) -> list[SurveyField]:
        """Создает список полей опроса."""
        return [
            SurveyField(
                field_name="username",
                label=LABEL_USERNAME,
                db_formatter=format_username_db,
                auto_collect=auto_collect_username,
                hidden=True,
            ),
            SurveyField(
                field_name="telegram_sername",
                label=LABEL_TELEGRAM_FULLNAME,
                auto_collect=auto_collect_full_name,
                hidden=True,
            ),
            SurveyField(
                field_name="name",
                label=LABEL_NAME,
                message=QUESTION_NAME,
                validator=validate_non_empty,
                db_formatter=format_text_db,
                display_formatter=format_default_display,
                acknowledgment_message=ACK_NAME,
                editable=True,
            ),
            SurveyField(
                field_name="birth_date",
                label=LABEL_BIRTH_DATE,
                message=QUESTION_BIRTH_DATE,
                validator=validate_date,
                db_formatter=format_date_db,
                display_formatter=format_default_display,
                editable=True,
            ),
            SurveyField(
                field_name="group",
                label=LABEL_GROUP,
                message=QUESTION_GROUP,
                validator=validate_group,
                db_formatter=format_group_db,
                display_formatter=format_default_display,
                editable=True,
            ),
            SurveyField(
                field_name="phone",
                label=LABEL_PHONE,
                message=QUESTION_PHONE,
                validator=validate_phone,
                db_formatter=format_phone_db,
                display_formatter=format_phone_display,
                request_contact=True,
                editable=True,
            ),
            SurveyField(
                field_name="expectations",
                label=LABEL_EXPECTATIONS,
                message=QUESTION_EXPECTATIONS,
                validator=validate_non_empty,
                acknowledgment_message=ACK_EXPECTATIONS,
                editable=True,
            ),
            SurveyField(
                field_name="will_drive",
                label=LABEL_WILL_DRIVE,
                message=QUESTION_WILL_DRIVE,
                options=WILL_DRIVE_OPTIONS,
                multi_select=False,
                db_formatter=format_text_db,
                display_formatter=format_default_display,
                option_acknowledgments=WILL_DRIVE_ACKNOWLEDGMENTS,
                editable=True,
            ),
            SurveyField(
                field_name="trip_attendance",
                label="Участие в выезде",
                message=TRIP_POLL_MESSAGE,
                options=TRIP_POLL_OPTIONS,
                multi_select=False,
                db_formatter=format_text_db,
                display_formatter=format_default_display,
                option_acknowledgments=TRIP_POLL_ACKNOWLEDGMENTS,
                editable=True,
            ),
        ]

    def _create_post_registration_states(self) -> list[dict[str, Any]]:
        """Создает состояния после регистрации."""
        return [
            {
                "state": REGISTERED,
                "message": self._generate_registered_message,
                "buttons": [ABOUT_TRIP, WHAT_TO_BRING, CHANGE_DATA],
            },
            {
                "state": EDIT,
                "message": EDIT_PROMPT,
                "buttons": lambda: [field.label for field in self.get_editable_fields()] + [CANCEL],
            },
        ]

    def _create_admin_states(self) -> list[dict[str, Any]]:
        """Создает админские состояния."""
        return [
            {
                "state": ADMIN_SEND_MESSAGE,
                "message": ADMIN_SEND_MESSAGE_PROMPT,
                "buttons": [CANCEL],
            },
            {
                "state": ADMIN_FORWARD_MESSAGE,
                "message": "Отправьте мне сообщение, которое нужно переслать всем пользователям.\n\nЯ сохраню все его свойства (премиум стикеры, эмодзи, фото, видео и т.д.) при пересылке.",
                "buttons": [CANCEL],
            },
        ]

    def _generate_registered_message(self, user_data: dict[str, Any]) -> str:
        """Генерирует сообщение с данными пользователя после регистрации."""
        message = REGISTERED_MESSAGE_HEADER

        for field in self._fields:
            # Пропускаем скрытые поля
            if field.hidden:
                continue

            value = user_data.get(field.field_name, DEFAULT_NOT_SPECIFIED)
            if field.display_formatter:
                value = field.display_formatter(value)
            message += f"{field.label}: `{value}`\n"

        return message

    # Публичные методы для доступа к конфигурации

    @property
    def fields(self) -> list[SurveyField]:
        """Возвращает список всех полей."""
        return self._fields.copy()

    @property
    def post_registration_states(self) -> list[dict[str, Any]]:
        """Возвращает состояния после регистрации."""
        return self._post_registration_states.copy()

    @property
    def admin_states(self) -> list[dict[str, Any]]:
        """Возвращает админские состояния."""
        return self._admin_states.copy()

    def get_field_by_name(self, field_name: str) -> SurveyField | None:
        """Получает поле по имени."""
        return next((field for field in self._fields if field.field_name == field_name), None)

    def get_field_by_label(self, label: str) -> SurveyField | None:
        """Получает поле по метке."""
        return next((field for field in self._fields if field.label == label), None)

    def get_editable_fields(self) -> list[SurveyField]:
        """Возвращает список редактируемых полей."""
        return [field for field in self._fields if field.editable and not field.hidden]

    def get_field_names(self) -> list[str]:
        """Возвращает список имен полей."""
        return [field.field_name for field in self._fields]

    def add_field(self, field: SurveyField) -> None:
        """Добавляет новое поле в конфигурацию."""
        self._fields.append(field)

    def remove_field(self, field_name: str) -> bool:
        """Удаляет поле из конфигурации."""
        original_length = len(self._fields)
        self._fields = [field for field in self._fields if field.field_name != field_name]
        return len(self._fields) < original_length


# Глобальный экземпляр конфигурации
registration_survey = RegistrationSurveyConfig()
