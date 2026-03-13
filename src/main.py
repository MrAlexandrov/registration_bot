import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .admin_commands import admin_commands
from .chat_tracker import chat_tracker
from .error_notifier import error_notifier
from .message_logger import message_logger
from .registration_handler import RegistrationFlow
from .settings import BOT_TOKEN
from .user_storage import user_storage

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

registration_flow = RegistrationFlow(user_storage)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates and notify superuser chat."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

    # Send error notification to superuser chat
    if context.error:
        await error_notifier.notify_error(context, context.error, update if isinstance(update, Update) else None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    await registration_flow.handle_command(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает сообщения пользователя."""
    # Log incoming message
    message_logger.log_incoming_message(update)

    await registration_flow.handle_input(update, context)


async def track_chat_member_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отслеживает изменения статуса бота в чате с пользователем.
    Срабатывает когда пользователь блокирует или разблокирует бота.
    Работает только для приватных чатов (не групп).
    """
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    user_id = result.from_user.id
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    logger.info(
        f"Chat member update in chat {chat.id} (type: {chat.type}) for user {user_id}: {old_status} -> {new_status}"
    )

    # Обрабатываем только приватные чаты (блокировка/разблокировка бота)
    if chat.type != "private":
        logger.debug(f"Ignoring chat member update in non-private chat {chat.id}")
        return

    # Проверяем, существует ли пользователь в БД
    user = user_storage.get_user(user_id)
    if not user:
        logger.info(f"User {user_id} not found in database, skipping status update")
        return

    # Пользователь заблокировал бота
    if new_status in ["kicked", "left"] and old_status in ["member", "administrator"]:
        logger.warning(f"User {user_id} blocked the bot")
        user_storage.update_user(user_id, "is_blocked", 1)

    # Пользователь разблокировал бота
    elif new_status in ["member", "administrator"] and old_status in ["kicked", "left"]:
        logger.info(f"User {user_id} unblocked the bot")
        user_storage.update_user(user_id, "is_blocked", 0)


async def handle_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin commands in both private and group chats."""
    await admin_commands.handle_admin_command(update, context)


async def post_init(application: Application) -> None:  # type: ignore[type-arg]
    """Initialize bot after startup - grant ROOT user admin permissions."""
    from .config import config
    from .permissions import Permission, permission_manager

    logger.info("Initializing ROOT user permissions...")

    # Grant all permissions to ROOT user
    root_id = config.root_id
    permissions_to_grant = [Permission.ADMIN, Permission.TABLE_VIEWER, Permission.MESSAGE_SENDER, Permission.STAFF]

    for perm in permissions_to_grant:
        try:
            permission_manager.grant_permission(root_id, perm, 0)
            logger.info(f"Granted {perm.value} to ROOT user {root_id}")
        except Exception as e:
            logger.debug(f"Permission {perm.value} already exists for ROOT or error: {e}")

    logger.info("ROOT user initialization complete")


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set")

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Admin commands - work in both private and group chats
    admin_command_list = [
        "grant_permission",
        "revoke_permission",
        "list_permissions",
        "list_users",
        "register_staff_chat",
        "register_counselor_chat",
        "register_superuser_chat",
        "sync_staff_chat",
        "sync_counselor_chat",
        "my_permissions",
        "help",
    ]
    for cmd in admin_command_list:
        application.add_handler(CommandHandler(cmd, handle_admin_command))

    # Registration commands - only in private chats
    application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))

    # Message handlers - only in private chats for registration
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.CONTACT & filters.ChatType.PRIVATE, handle_message))

    # Media message handlers - log all media types
    application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.AUDIO & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.Sticker.ALL & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.LOCATION & filters.ChatType.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.POLL & filters.ChatType.PRIVATE, handle_message))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(registration_flow.handle_inline_query))

    # Track when users block/unblock the bot
    application.add_handler(ChatMemberHandler(track_chat_member_updates, ChatMemberHandler.MY_CHAT_MEMBER))

    # Track chat member updates for staff chat
    application.add_handler(ChatMemberHandler(chat_tracker.handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"])


if __name__ == "__main__":
    main()
