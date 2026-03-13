"""
Модуль для безопасной отправки сообщений с обработкой блокировок и ретраями.
"""

import asyncio
import logging
from typing import Any

from telegram import Bot
from telegram.error import Forbidden, NetworkError, RetryAfter, TelegramError

from .message_logger import message_logger
from .user_storage import user_storage

logger = logging.getLogger(__name__)


class MessageSender:
    """
    Класс для безопасной отправки сообщений через Telegram Bot API.

    Особенности:
    - Автоматическая обработка блокировок пользователями
    - Retry механизм при сетевых ошибках
    - Обработка rate limiting (RetryAfter)
    - Логирование всех операций
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Инициализация отправителя сообщений.

        Args:
            max_retries: Максимальное количество попыток отправки
            retry_delay: Базовая задержка между попытками в секундах
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def send_message(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        **kwargs: Any,
    ) -> bool:
        """
        Безопасная отправка сообщения с обработкой ошибок и ретраями.

        Args:
            bot: Экземпляр Telegram Bot
            chat_id: ID чата/пользователя
            text: Текст сообщения
            **kwargs: Дополнительные параметры для send_message (parse_mode, reply_markup и т.д.)

        Returns:
            bool: True если сообщение отправлено успешно, False в противном случае
        """
        # Проверяем, не заблокирован ли бот пользователем
        user = user_storage.get_user(chat_id)
        if user and user.get("is_blocked"):
            logger.info(f"Пользователь {chat_id} заблокировал бота, пропускаем отправку")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                sent_message = await bot.send_message(chat_id=chat_id, text=text, **kwargs)
                logger.debug(f"Сообщение успешно отправлено пользователю {chat_id}")

                # Log outgoing message
                message_logger.log_outgoing_message(
                    telegram_id=chat_id,
                    chat_id=chat_id,
                    sent_message=sent_message,
                    message_type="text",
                    reply_to_message_id=kwargs.get("reply_to_message_id"),
                )

                return True

            except Forbidden as e:
                # Пользователь заблокировал бота
                logger.warning(f"Пользователь {chat_id} заблокировал бота: {e}")
                self._mark_user_as_blocked(chat_id)
                return False

            except RetryAfter as e:
                # Rate limiting от Telegram
                retry_after = e.retry_after
                logger.warning(f"Rate limit для {chat_id}, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after)
                # Не считаем это попыткой, просто ждём и пробуем снова
                continue

            except NetworkError as e:
                # Сетевая ошибка - пробуем ещё раз
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Сетевая ошибка при отправке сообщения {chat_id} "
                        f"(попытка {attempt}/{self.max_retries}): {e}. "
                        f"Повтор через {delay} сек."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Не удалось отправить сообщение {chat_id} после {self.max_retries} попыток: {e}")
                    return False

            except TelegramError as e:
                # Другие ошибки Telegram API
                logger.error(f"Ошибка Telegram API при отправке сообщения {chat_id}: {e}")
                return False

            except Exception as e:
                # Неожиданная ошибка
                logger.error(f"Неожиданная ошибка при отправке сообщения {chat_id}: {e}", exc_info=True)
                return False

        return False

    async def send_photo(
        self,
        bot: Bot,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        Безопасная отправка фото с обработкой ошибок и ретраями.

        Args:
            bot: Экземпляр Telegram Bot
            chat_id: ID чата/пользователя
            photo: File ID, URL или путь к фото
            caption: Подпись к фото (опционально)
            **kwargs: Дополнительные параметры для send_photo

        Returns:
            bool: True если фото отправлено успешно, False в противном случае
        """
        # Проверяем, не заблокирован ли бот пользователем
        user = user_storage.get_user(chat_id)
        if user and user.get("is_blocked"):
            logger.info(f"Пользователь {chat_id} заблокировал бота, пропускаем отправку")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                sent_message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, **kwargs)
                logger.debug(f"Фото успешно отправлено пользователю {chat_id}")

                # Log outgoing message
                message_logger.log_outgoing_message(
                    telegram_id=chat_id,
                    chat_id=chat_id,
                    sent_message=sent_message,
                    message_type="photo",
                    reply_to_message_id=kwargs.get("reply_to_message_id"),
                )

                return True

            except Forbidden as e:
                # Пользователь заблокировал бота
                logger.warning(f"Пользователь {chat_id} заблокировал бота: {e}")
                self._mark_user_as_blocked(chat_id)
                return False

            except RetryAfter as e:
                # Rate limiting от Telegram
                retry_after = e.retry_after
                logger.warning(f"Rate limit для {chat_id}, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after)
                # Не считаем это попыткой, просто ждём и пробуем снова
                continue

            except NetworkError as e:
                # Сетевая ошибка - пробуем ещё раз
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Сетевая ошибка при отправке фото {chat_id} "
                        f"(попытка {attempt}/{self.max_retries}): {e}. "
                        f"Повтор через {delay} сек."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Не удалось отправить фото {chat_id} после {self.max_retries} попыток: {e}")
                    return False

            except TelegramError as e:
                # Другие ошибки Telegram API
                logger.error(f"Ошибка Telegram API при отправке фото {chat_id}: {e}")
                return False

            except Exception as e:
                # Неожиданная ошибка
                logger.error(f"Неожиданная ошибка при отправке фото {chat_id}: {e}", exc_info=True)
                return False

        return False

    async def send_video(
        self,
        bot: Bot,
        chat_id: int,
        video: str,
        caption: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        Безопасная отправка видео с обработкой ошибок и ретраями.

        Args:
            bot: Экземпляр Telegram Bot
            chat_id: ID чата/пользователя
            video: File ID, URL или путь к видео
            caption: Подпись к видео (опционально)
            **kwargs: Дополнительные параметры для send_video

        Returns:
            bool: True если видео отправлено успешно, False в противном случае
        """
        # Проверяем, не заблокирован ли бот пользователем
        user = user_storage.get_user(chat_id)
        if user and user.get("is_blocked"):
            logger.info(f"Пользователь {chat_id} заблокировал бота, пропускаем отправку")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                sent_message = await bot.send_video(chat_id=chat_id, video=video, caption=caption, **kwargs)
                logger.debug(f"Видео успешно отправлено пользователю {chat_id}")

                # Log outgoing message
                message_logger.log_outgoing_message(
                    telegram_id=chat_id,
                    chat_id=chat_id,
                    sent_message=sent_message,
                    message_type="video",
                    reply_to_message_id=kwargs.get("reply_to_message_id"),
                )

                return True

            except Forbidden as e:
                # Пользователь заблокировал бота
                logger.warning(f"Пользователь {chat_id} заблокировал бота: {e}")
                self._mark_user_as_blocked(chat_id)
                return False

            except RetryAfter as e:
                # Rate limiting от Telegram
                retry_after = e.retry_after
                logger.warning(f"Rate limit для {chat_id}, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after)
                # Не считаем это попыткой, просто ждём и пробуем снова
                continue

            except NetworkError as e:
                # Сетевая ошибка - пробуем ещё раз
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Сетевая ошибка при отправке видео {chat_id} "
                        f"(попытка {attempt}/{self.max_retries}): {e}. "
                        f"Повтор через {delay} сек."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Не удалось отправить видео {chat_id} после {self.max_retries} попыток: {e}")
                    return False

            except TelegramError as e:
                # Другие ошибки Telegram API
                logger.error(f"Ошибка Telegram API при отправке видео {chat_id}: {e}")
                return False

            except Exception as e:
                # Неожиданная ошибка
                logger.error(f"Неожиданная ошибка при отправке видео {chat_id}: {e}", exc_info=True)
                return False

        return False

    async def send_document(
        self,
        bot: Bot,
        chat_id: int,
        document: str,
        caption: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        Безопасная отправка документа с обработкой ошибок и ретраями.

        Args:
            bot: Экземпляр Telegram Bot
            chat_id: ID чата/пользователя
            document: File ID, URL или путь к документу
            caption: Подпись к документу (опционально)
            **kwargs: Дополнительные параметры для send_document

        Returns:
            bool: True если документ отправлен успешно, False в противном случае
        """
        # Проверяем, не заблокирован ли бот пользователем
        user = user_storage.get_user(chat_id)
        if user and user.get("is_blocked"):
            logger.info(f"Пользователь {chat_id} заблокировал бота, пропускаем отправку")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                sent_message = await bot.send_document(chat_id=chat_id, document=document, caption=caption, **kwargs)
                logger.debug(f"Документ успешно отправлен пользователю {chat_id}")

                # Log outgoing message
                message_logger.log_outgoing_message(
                    telegram_id=chat_id,
                    chat_id=chat_id,
                    sent_message=sent_message,
                    message_type="document",
                    reply_to_message_id=kwargs.get("reply_to_message_id"),
                )

                return True

            except Forbidden as e:
                # Пользователь заблокировал бота
                logger.warning(f"Пользователь {chat_id} заблокировал бота: {e}")
                self._mark_user_as_blocked(chat_id)
                return False

            except RetryAfter as e:
                # Rate limiting от Telegram
                retry_after = e.retry_after
                logger.warning(f"Rate limit для {chat_id}, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after)
                # Не считаем это попыткой, просто ждём и пробуем снова
                continue

            except NetworkError as e:
                # Сетевая ошибка - пробуем ещё раз
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Сетевая ошибка при отправке документа {chat_id} "
                        f"(попытка {attempt}/{self.max_retries}): {e}. "
                        f"Повтор через {delay} сек."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Не удалось отправить документ {chat_id} после {self.max_retries} попыток: {e}")
                    return False

            except TelegramError as e:
                # Другие ошибки Telegram API
                logger.error(f"Ошибка Telegram API при отправке документа {chat_id}: {e}")
                return False

            except Exception as e:
                # Неожиданная ошибка
                logger.error(f"Неожиданная ошибка при отправке документа {chat_id}: {e}", exc_info=True)
                return False

        return False

    def _mark_user_as_blocked(self, user_id: int) -> None:
        """
        Помечает пользователя как заблокировавшего бота.

        Args:
            user_id: ID пользователя
        """
        try:
            user_storage.update_user(user_id, "is_blocked", 1)
            logger.info(f"Пользователь {user_id} помечен как заблокировавший бота")
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса блокировки для {user_id}: {e}")

    async def copy_message(
        self,
        bot: Bot,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
        **kwargs: Any,
    ) -> bool:
        """
        Копирование сообщения с сохранением всех свойств (стикеры, эмодзи и т.д.).

        Args:
            bot: Экземпляр Telegram Bot
            chat_id: ID чата получателя
            from_chat_id: ID чата источника
            message_id: ID сообщения для копирования
            **kwargs: Дополнительные параметры для copy_message

        Returns:
            bool: True если сообщение скопировано успешно, False в противном случае
        """
        # Проверяем, не заблокирован ли бот пользователем
        user = user_storage.get_user(chat_id)
        if user and user.get("is_blocked"):
            logger.info(f"Пользователь {chat_id} заблокировал бота, пропускаем копирование")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                    **kwargs,
                )
                logger.debug(f"Сообщение успешно скопировано пользователю {chat_id}")
                return True

            except Forbidden as e:
                # Пользователь заблокировал бота
                logger.warning(f"Пользователь {chat_id} заблокировал бота: {e}")
                self._mark_user_as_blocked(chat_id)
                return False

            except RetryAfter as e:
                # Rate limiting от Telegram
                retry_after = e.retry_after
                logger.warning(f"Rate limit для {chat_id}, ожидание {retry_after} секунд")
                await asyncio.sleep(retry_after)
                # Не считаем это попыткой, просто ждём и пробуем снова
                continue

            except NetworkError as e:
                # Сетевая ошибка - пробуем ещё раз
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Сетевая ошибка при копировании сообщения для {chat_id} "
                        f"(попытка {attempt}/{self.max_retries}): {e}. "
                        f"Повтор через {delay} сек."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Не удалось скопировать сообщение для {chat_id} после {self.max_retries} попыток: {e}"
                    )
                    return False

            except TelegramError as e:
                # Другие ошибки Telegram API
                logger.error(f"Ошибка Telegram API при копировании сообщения для {chat_id}: {e}")
                return False

            except Exception as e:
                # Неожиданная ошибка
                logger.error(f"Неожиданная ошибка при копировании сообщения для {chat_id}: {e}", exc_info=True)
                return False

        return False

    async def copy_message_to_multiple(
        self,
        bot: Bot,
        user_ids: list[int],
        from_chat_id: int,
        message_id: int,
        delay_between: float = 0.05,
        **kwargs: Any,
    ) -> dict[str, int]:
        """
        Копирование сообщения нескольким пользователям с задержкой между отправками.
        Используется для пересылки сообщений со всеми свойствами (премиум стикеры, эмодзи и т.д.).

        Args:
            bot: Экземпляр Telegram Bot
            user_ids: Список ID пользователей
            from_chat_id: ID чата источника
            message_id: ID сообщения для копирования
            delay_between: Задержка между отправками в секундах (для избежания rate limit)
            **kwargs: Дополнительные параметры для copy_message

        Returns:
            dict: Статистика отправки {"success": количество успешных, "failed": количество неудачных}
        """
        stats = {"success": 0, "failed": 0}

        for user_id in user_ids:
            success = await self.copy_message(bot, user_id, from_chat_id, message_id, **kwargs)

            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # Задержка между отправками для избежания rate limit
            if delay_between > 0:
                await asyncio.sleep(delay_between)

        logger.info(f"Массовая пересылка завершена: успешно={stats['success']}, неудачно={stats['failed']}")
        return stats

    async def send_message_to_multiple(
        self,
        bot: Bot,
        user_ids: list[int],
        text: str,
        delay_between: float = 0.05,
        message_type: str = "text",
        **kwargs: Any,
    ) -> dict[str, int]:
        """
        Отправка сообщения нескольким пользователям с задержкой между отправками.

        Args:
            bot: Экземпляр Telegram Bot
            user_ids: Список ID пользователей
            text: Текст сообщения (или caption для медиа)
            delay_between: Задержка между отправками в секундах (для избежания rate limit)
            message_type: Тип сообщения ("text", "photo", "video", "document")
            **kwargs: Дополнительные параметры для соответствующего метода отправки

        Returns:
            dict: Статистика отправки {"success": количество успешных, "failed": количество неудачных}
        """
        stats = {"success": 0, "failed": 0}

        for user_id in user_ids:
            success = False
            caption = text  # Для медиафайлов text становится caption

            # Удаляем медиа-параметры из kwargs чтобы не передавать их в методы отправки
            media_kwargs = kwargs.copy()
            photo = media_kwargs.pop("photo", None)
            video = media_kwargs.pop("video", None)
            document = media_kwargs.pop("document", None)

            if message_type == "text":
                success = await self.send_message(bot, user_id, text, **kwargs)
            elif message_type == "photo":
                if photo is None:
                    logger.error("Photo is required for sending photos")
                    stats["failed"] += 1
                    continue
                success = await self.send_photo(bot, user_id, photo, caption, **media_kwargs)
            elif message_type == "video":
                if video is None:
                    logger.error("Video is required for sending videos")
                    stats["failed"] += 1
                    continue
                success = await self.send_video(bot, user_id, video, caption, **media_kwargs)
            elif message_type == "document":
                if document is None:
                    logger.error("Document is required for sending documents")
                    stats["failed"] += 1
                    continue
                success = await self.send_document(bot, user_id, document, caption, **media_kwargs)
            else:
                logger.error(f"Unsupported message type: {message_type}")
                stats["failed"] += 1
                continue

            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # Задержка между отправками для избежания rate limit
            if delay_between > 0:
                await asyncio.sleep(delay_between)

        logger.info(f"Массовая рассылка завершена: успешно={stats['success']}, неудачно={stats['failed']}")
        return stats


# Глобальный экземпляр для использования в проекте
message_sender = MessageSender(max_retries=3, retry_delay=1.0)
