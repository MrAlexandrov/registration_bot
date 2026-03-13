import logging
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .constants import (
    ABOUT_TRIP,
    ADMIN_FORWARD_MESSAGE,
    ADMIN_SEND_MESSAGE,
    AMOUNT_OF_USERS,
    BUTTONS,
    CANCEL,
    CHANGE_DATA,
    EDIT,
    FORWARD_MESSAGE_TO_ALL,
    GET_ACTUAL_TABLE,
    OPTIONS,
    REGISTERED,
    SEND_MESSAGE_ALL_USERS,
    SEND_TRIP_POLL,
    STATE,
    WHAT_TO_BRING,
)
from .message_formatter import MessageFormatter
from .message_sender import message_sender
from .messages import (
    ADMIN_DOCUMENT_SENT_STATS,
    ADMIN_FILE_SENT_ERROR,
    ADMIN_FILE_SENT_SUCCESS,
    ADMIN_MESSAGE_SENT_STATS,
    ADMIN_PHOTO_SENT_STATS,
    ADMIN_VIDEO_SENT_STATS,
    ERROR_FIELD_NOT_EDITABLE,
    ERROR_SELECT_SOMETHING,
    ERROR_SOMETHING_WRONG,
    ERROR_UNKNOWN_FIELD,
    ERROR_USE_BUTTONS,
    ERROR_USER_NOT_FOUND,
    GREETING_MESSAGE,
    INFO_ABOUT_TRIP,
    INFO_WHAT_TO_BRING,
    OPTION_WILL_DRIVE_YES,
    TRIP_POLL_ACK_NO,
    TRIP_POLL_ACK_YES,
    TRIP_POLL_MESSAGE,
    TRIP_POLL_OPTIONS,
)
from .milestone_notifier import milestone_notifier
from .permissions import permission_manager
from .settings import ADMIN_IDS, SURVEY_CONFIG, TABLE_GETTERS
from .state_handler import StateHandler
from .survey.auto_collectors import auto_collect_counselor_status, auto_collect_staff_status
from .user_storage import UserStorage, user_storage
from .utils import get_actual_table

logger = logging.getLogger(__name__)


class RegistrationFlow:
    def __init__(self, user_storage: UserStorage):
        self.user_storage = user_storage
        self.state_handler = StateHandler(user_storage)
        self.steps = [field.field_name for field in SURVEY_CONFIG.fields]

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команды, такие как /start."""
        user_id = update.message.from_user.id
        user = self.user_storage.get_user(user_id)

        if not user:
            logger.info(f"Creating new user for user_id: {user_id}")
            self.user_storage.create_user(user_id)

            # Автоматически собираем is_staff и is_counselor при создании пользователя
            try:
                is_staff = await auto_collect_staff_status(update, permission_manager, context)
                is_counselor = await auto_collect_counselor_status(update, permission_manager, context)

                if is_staff:
                    self.user_storage.update_user(user_id, "is_staff", is_staff)
                    logger.info(f"Auto-collected is_staff={is_staff} for new user {user_id}")

                if is_counselor:
                    self.user_storage.update_user(user_id, "is_counselor", is_counselor)
                    logger.info(f"Auto-collected is_counselor={is_counselor} for new user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to auto-collect staff/counselor status for user {user_id}: {e}")

            # Send greeting message for new users
            await message_sender.send_message(
                context.bot,
                user_id,
                GREETING_MESSAGE,
            )
            await self.state_handler.transition_state(update, context, self.steps[0])
        else:
            logger.info(f"User {user_id} already exists in state '{user[STATE]}'")

            # Если пользователь был заблокирован, но теперь пишет боту - разблокируем
            if user.get("is_blocked"):
                logger.info(f"User {user_id} was blocked but now interacting - unblocking")
                self.user_storage.update_user(user_id, "is_blocked", 0)

            await self.state_handler.transition_state(update, context, user[STATE])

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает пользовательский ввод для всех состояний."""
        user_id = update.message.from_user.id
        user = self.user_storage.get_user(user_id)
        if user is None:
            await message_sender.send_message(
                context.bot,
                user_id,
                ERROR_USER_NOT_FOUND,
            )
            await self.handle_command(update, context)
            return
        state = user[STATE]
        logger.info(f"User {user_id} is in state '{state}'")

        if user_id in ADMIN_IDS:
            if await self.handle_admin_input(update, context, state):
                return

        config = self.state_handler.get_config_by_state(state)
        if not config:
            logger.error(f"Invalid state '{state}' for user {user_id}")
            await message_sender.send_message(
                context.bot,
                user_id,
                ERROR_SOMETHING_WRONG,
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Проверяем наличие options для SurveyField или словаря
        has_options = (hasattr(config, "options") and config.options) or (
            isinstance(config, dict) and OPTIONS in config
        )
        if has_options:
            logger.debug("User sent message while inline keyboard is active")
            await message_sender.send_message(context.bot, user_id, ERROR_USE_BUTTONS)
            return

        user_input = update.message.contact.phone_number if update.message.contact else update.message.text

        # Проверяем наличие buttons (только для словарей, SurveyField не имеет buttons)
        if isinstance(config, dict) and BUTTONS in config:
            await self.process_action_input(update, context, state, user_input)
            return

        await self.process_data_input(update, context, state, user_input)

    async def handle_admin_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str) -> bool:
        user_id = update.effective_user.id
        if state == ADMIN_FORWARD_MESSAGE:
            # Handle cancel through callback query or text
            if (update.message and update.message.text and update.message.text == CANCEL) or (
                update.callback_query and update.callback_query.data == "cancel"
            ):
                if update.callback_query:
                    await update.callback_query.answer()
                await self.state_handler.transition_state(update, context, REGISTERED)
                return True

            # Get message to forward
            message = update.message
            all_users_id = self.user_storage.get_all_users()
            logger.info(f"Forwarding message to {len(all_users_id)} users")

            # Use copy_message_to_multiple to preserve all message properties
            stats = await message_sender.copy_message_to_multiple(
                bot=context.bot,
                user_ids=all_users_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                delay_between=0.05,
            )

            # Send stats back to admin
            await message_sender.send_message(
                context.bot,
                user_id,
                f"✅ Пересылка завершена!\n\n"
                f"📊 Статистика:\n"
                f"• Всего пользователей: {len(all_users_id)}\n"
                f"• Успешно: {stats['success']}\n"
                f"• Неудачно: {stats['failed']}",
            )

            logger.info(f"Message forwarded to users: success={stats['success']}, failed={stats['failed']}")
            await self.state_handler.transition_state(update, context, REGISTERED)
            return True
        elif state == ADMIN_SEND_MESSAGE:
            # Handle cancel through callback query or text
            if (update.message and update.message.text and update.message.text == CANCEL) or (
                update.callback_query and update.callback_query.data == CANCEL
            ):
                if update.callback_query:
                    await update.callback_query.answer()
                await self.state_handler.transition_state(update, context, REGISTERED)
                return True

            # Detect content type and send accordingly
            all_users_id = self.user_storage.get_all_users()
            logger.info(f"Sending message to {len(all_users_id)} users")

            stats = None
            user_input = MessageFormatter.get_escaped_text(update.message)
            if update.message.photo:
                # Send photo
                photo = update.message.photo[-1].file_id
                caption = user_input
                stats = await message_sender.send_message_to_multiple(
                    context.bot,
                    all_users_id,
                    caption,
                    message_type="photo",
                    photo=photo,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    ADMIN_PHOTO_SENT_STATS.format(success=stats["success"], failed=stats["failed"]),
                )
            elif update.message.video:
                # Send video
                video = update.message.video.file_id
                caption = user_input
                stats = await message_sender.send_message_to_multiple(
                    context.bot,
                    all_users_id,
                    caption,
                    message_type="video",
                    video=video,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    ADMIN_VIDEO_SENT_STATS.format(success=stats["success"], failed=stats["failed"]),
                )
            elif update.message.document:
                # Send document
                document = update.message.document.file_id
                caption = user_input
                stats = await message_sender.send_message_to_multiple(
                    context.bot,
                    all_users_id,
                    caption,
                    message_type="document",
                    document=document,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    ADMIN_DOCUMENT_SENT_STATS.format(success=stats["success"], failed=stats["failed"]),
                )
            else:
                # Send text message
                stats = await message_sender.send_message_to_multiple(
                    context.bot,
                    all_users_id,
                    user_input,
                    message_type="text",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    ADMIN_MESSAGE_SENT_STATS.format(success=stats["success"], failed=stats["failed"]),
                )

            if stats:
                logger.info(f"Message sent to users: success={stats['success']}, failed={stats['failed']}")
            await self.state_handler.transition_state(update, context, REGISTERED)
            return True
        return False

    async def process_action_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, user_input: str
    ) -> None:
        """Обрабатывает кнопки в состояниях registered и edit."""
        user_id = update.message.from_user.id

        if state == REGISTERED:
            if user_input == CHANGE_DATA:
                logger.info(f"User {user_id} chose 'Change data'")
                await self.state_handler.transition_state(update, context, EDIT)
            elif user_input == ABOUT_TRIP:
                logger.info(f"User {user_id} requested info about trip")
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    INFO_ABOUT_TRIP,
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif user_input == WHAT_TO_BRING:
                logger.info(f"User {user_id} requested info about what to bring")
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    INFO_WHAT_TO_BRING,
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif user_id in ADMIN_IDS and user_input == SEND_MESSAGE_ALL_USERS:
                await self.state_handler.transition_state(update, context, ADMIN_SEND_MESSAGE)
            elif user_id in ADMIN_IDS and user_input == FORWARD_MESSAGE_TO_ALL:
                await self.state_handler.transition_state(update, context, ADMIN_FORWARD_MESSAGE)
            elif user_id in ADMIN_IDS and user_input == SEND_TRIP_POLL:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                # Create inline keyboard with Yes/No buttons
                keyboard = [
                    [
                        InlineKeyboardButton(TRIP_POLL_OPTIONS[0], callback_data=f"trip_poll|{TRIP_POLL_OPTIONS[0]}"),
                        InlineKeyboardButton(TRIP_POLL_OPTIONS[1], callback_data=f"trip_poll|{TRIP_POLL_OPTIONS[1]}"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                all_users_id = self.user_storage.get_all_users()
                stats = await message_sender.send_message_to_multiple(
                    context.bot,
                    all_users_id,
                    TRIP_POLL_MESSAGE,
                    message_type="text",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup,
                )
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    ADMIN_MESSAGE_SENT_STATS.format(success=stats["success"], failed=stats["failed"]),
                )
                if stats:
                    logger.info(f"Trip poll sent to users: success={stats['success']}, failed={stats['failed']}")
            elif user_id in ADMIN_IDS and user_input == AMOUNT_OF_USERS:
                amount_of_users = self.user_storage.get_amount_of_users()
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    str(amount_of_users),
                )
            elif user_id in TABLE_GETTERS and user_input == GET_ACTUAL_TABLE:
                file_path = get_actual_table()
                try:
                    await context.bot.send_document(chat_id=user_id, document=open(file_path, "rb"))
                    await update.message.reply_text(ADMIN_FILE_SENT_SUCCESS)
                except Exception as e:
                    logger.error(f"Failed to send file to user {user_id}: {e}")
                    await update.message.reply_text(ADMIN_FILE_SENT_ERROR.format(error=e))
        elif state == ADMIN_SEND_MESSAGE and user_input == CANCEL:
            await self.state_handler.transition_state(update, context, REGISTERED)
        elif state == EDIT:
            if user_input == CANCEL:
                logger.info(f"User {user_id} canceled editing")
                await self.state_handler.transition_state(update, context, REGISTERED)
                return

            field_config = self.get_config_by_label(user_input)
            if not field_config:
                logger.error(f"Field '{user_input}' not found for user {user_id}")
                await message_sender.send_message(
                    context.bot,
                    user_id,
                    ERROR_UNKNOWN_FIELD,
                )
                return

            if not field_config.editable:
                await message_sender.send_message(context.bot, user_id, ERROR_FIELD_NOT_EDITABLE)
                return

            await self.state_handler.transition_state(update, context, f"edit_{field_config.field_name}")

    def apply_db_formatter(self, field_name: str, value: str) -> str:
        """Применяет форматтер для базы данных, если он указан в конфиге."""
        field_config = SURVEY_CONFIG.get_field_by_name(field_name)
        if field_config and field_config.db_formatter:
            return field_config.db_formatter(value)
        return value

    async def process_data_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, user_input: str
    ) -> None:
        """Обрабатывает пользовательский ввод, проверяет и форматирует перед сохранением."""
        user_id = update.effective_user.id
        actual_state = state.replace("edit_", "")
        field_config = SURVEY_CONFIG.get_field_by_name(actual_state)

        if not field_config:
            logger.error(f"Field '{actual_state}' not found for user {user_id}")
            await message_sender.send_message(
                context.bot,
                user_id,
                ERROR_SOMETHING_WRONG,
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if field_config.request_contact and update.message.contact:
            user_input = update.message.contact.phone_number

        if field_config.validator:
            is_valid, error_message = field_config.validator(user_input)
            if not is_valid:
                await message_sender.send_message(context.bot, user_id, error_message)
                return

        formatted_db_value = self.apply_db_formatter(actual_state, user_input)
        self.user_storage.update_user(user_id, actual_state, formatted_db_value)

        # Отправляем сообщение-подтверждение
        await self._send_acknowledgment(context.bot, user_id, field_config, user_input)

        next_state = self.state_handler.get_next_state(state)
        await self.state_handler.transition_state(update, context, next_state)

    async def _send_acknowledgment(self, bot, user_id: int, field_config, user_input: str) -> None:
        """Отправляет сообщение-подтверждение в зависимости от конфигурации поля."""
        # Приоритет 1: Специфичное сообщение для выбранного варианта (для полей с options)
        if field_config.option_acknowledgments and user_input in field_config.option_acknowledgments:
            await message_sender.send_message(bot, user_id, field_config.option_acknowledgments[user_input])
        # Приоритет 2: Общее сообщение-подтверждение
        elif field_config.acknowledgment_message:
            await message_sender.send_message(bot, user_id, field_config.acknowledgment_message)

    def get_config_by_label(self, label: str) -> Any:
        """Возвращает конфигурацию поля по его label (используется в редактировании)."""
        return SURVEY_CONFIG.get_field_by_label(label)

    async def clear_inline_keyboard(self, update: Update) -> None:
        """Удаляет только инлайн-клавиатуру, оставляя текст сообщения."""
        if update.callback_query:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)

    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает нажатия на инлайн-кнопки."""
        query = update.callback_query
        await query.answer()

        callback_data = query.data.split("|")
        action = callback_data[0]
        option = callback_data[1] if len(callback_data) > 1 else None

        user_id = query.from_user.id
        user = self.user_storage.get_user(user_id)
        state = user[STATE] if user else None

        # Handle cancel actions first, as they don't need field config
        if action == "cancel" or action == "cancel_edit":
            await self.clear_inline_keyboard(update)
            await self.state_handler.transition_state(update, context, REGISTERED)
            return

        # Special handling for trip poll (no state change)
        if action == "trip_poll" and option:
            await self.clear_inline_keyboard(update)

            # Save the response to trip_attendance field
            self.user_storage.update_user(user_id, "trip_attendance", option)
            logger.info(f"User {user_id} responded to trip poll: {option}")

            # Send acknowledgment based on the option
            if option == TRIP_POLL_OPTIONS[0]:  # Yes option
                await message_sender.send_message(context.bot, user_id, TRIP_POLL_ACK_YES)
            elif option == TRIP_POLL_OPTIONS[1]:  # No option
                await message_sender.send_message(context.bot, user_id, TRIP_POLL_ACK_NO)

            # No state change - user stays in their current state
            await self.state_handler.transition_state(update, context, REGISTERED)
            return

        # For other actions, we need field config
        if not state:
            logger.warning("No state found for user %s", user_id)
            return

        actual_field_name = state.replace("edit_", "")
        field_config = self.state_handler.get_config_by_state(actual_field_name)

        # If no field config, we can't handle select or done actions
        if not field_config:
            logger.warning("No field config found for state %s", state)
            return

        is_multi_select = field_config.multi_select if hasattr(field_config, "multi_select") else False
        selected_options = user.get(actual_field_name, "").split(", ") if user.get(actual_field_name) else []

        if action == "select":
            if is_multi_select:
                if option in selected_options:
                    selected_options.remove(option)
                else:
                    selected_options.append(option)
            else:
                selected_options = [option]

            self.user_storage.update_user(user_id, actual_field_name, ", ".join(selected_options))
            reply_markup = self.state_handler.create_inline_keyboard(
                field_config.options, selected_options=selected_options
            )
            if query.message.reply_markup != reply_markup:
                await query.edit_message_reply_markup(reply_markup=reply_markup)
            else:
                logger.debug("Reply markup is not modified, skipping edit_message_reply_markup call")

        elif action == "done":
            if not selected_options:
                await message_sender.send_message(context.bot, user_id, ERROR_SELECT_SOMETHING)
                return
            await self.clear_inline_keyboard(update)

            # Отправляем сообщение-подтверждение для выбранных опций
            user_input = ", ".join(selected_options)
            await self._send_acknowledgment(context.bot, user_id, field_config, user_input)

            # Проверяем, не достигнута ли веха регистрации (только для поля will_drive)
            if actual_field_name == "will_drive" and user_input == OPTION_WILL_DRIVE_YES:
                try:
                    await milestone_notifier.check_and_notify(context.bot)
                except Exception as e:
                    logger.error(f"Ошибка при проверке вехи регистрации: {e}", exc_info=True)

            next_state = self.state_handler.get_next_state(state)
            await self.state_handler.transition_state(update, context, next_state)


# Инициализируем регистрацию
registration_flow = RegistrationFlow(user_storage)
