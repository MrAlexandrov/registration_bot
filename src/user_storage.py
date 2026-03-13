"""
User storage using SQLAlchemy ORM.
Provides backward-compatible interface with the previous SQLite implementation.
"""

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError

from src.messages import TRIP_POLL_YES

from .database import db
from .models import get_user_model

logger = logging.getLogger(__name__)


class UserStorage:
    """
    User storage class using SQLAlchemy ORM.

    Provides methods to create, read, update, and delete users in the database.
    All methods maintain backward compatibility with the previous implementation.
    """

    def __init__(self, db_path: str = "data/database.sqlite") -> None:
        """
        Initialize user storage.

        Args:
            db_path: Path to SQLite database file (for backward compatibility)
        """
        # Initialize database with the provided path
        from .database import Database

        global db
        db = Database(db_path)

        # Get the User model
        self.User = get_user_model()

        # Create tables
        self._create_table()

    def _create_table(self) -> None:
        """Create database tables based on the User model."""
        try:
            db.create_tables()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def create_user(self, user_id: int, initial_state: str = "name") -> None:
        """
        Create a new user with empty fields.

        Args:
            user_id: Telegram user ID
            initial_state: Initial registration state (default: "name")

        Raises:
            ValueError: If user already exists
        """
        try:
            with db.get_session() as session:
                # Create new user instance
                user = self.User(telegram_id=user_id, state=initial_state)
                session.add(user)
                session.commit()
                logger.info(f"Created new user with ID: {user_id}")
        except IntegrityError as e:
            logger.warning(f"User {user_id} already exists")
            raise ValueError(f"User {user_id} already exists") from e

    def update_user(self, user_id: int, field: str, value: Any) -> None:
        """
        Update a single field for a user.

        Args:
            user_id: Telegram user ID
            field: Field name to update
            value: New value for the field

        Raises:
            ValueError: If user not found
        """
        with db.get_session() as session:
            user = session.query(self.User).filter_by(telegram_id=user_id).first()

            if not user:
                logger.warning(f"No user found with ID: {user_id}")
                raise ValueError(f"User {user_id} not found")

            # Update the field
            setattr(user, field, value)
            session.commit()
            logger.debug(f"Updated user {user_id}: {field} = {value}")

    def update_state(self, user_id: int, state: str) -> None:
        """
        Update user's state.

        Args:
            user_id: Telegram user ID
            state: New state value
        """
        self.update_user(user_id, "state", state)

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        """
        Get user data by Telegram ID.

        Args:
            user_id: Telegram user ID

        Returns:
            Dictionary with user data or None if not found
        """
        with db.get_session() as session:
            user = session.query(self.User).filter_by(telegram_id=user_id).first()

            if not user:
                logger.debug(f"User {user_id} not found")
                return None

            # Convert to dictionary for backward compatibility
            return user.to_dict()

    def get_all_users(self) -> list[int]:
        """
        Get list of all user telegram_ids.

        Returns:
            List of telegram_id values
        """
        with db.get_session() as session:
            users = session.query(self.User.telegram_id).order_by(self.User.created_at).all()
            return [user[0] for user in users]

    def get_users_count(self) -> int:
        """
        Get count of registered users.

        Returns:
            Number of users in database
        """
        with db.get_session() as session:
            count = session.query(self.User).count()
            return count

    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user from the database.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user was deleted, False if not found
        """
        with db.get_session() as session:
            user = session.query(self.User).filter_by(telegram_id=user_id).first()

            if not user:
                logger.warning(f"User {user_id} not found for deletion")
                return False

            session.delete(user)
            session.commit()
            logger.info(f"Deleted user {user_id}")
            return True

    def get_users_by_state(self, state: str) -> list[dict[str, Any]]:
        """
        Get all users in a specific state.

        Args:
            state: State to filter by

        Returns:
            List of user dictionaries
        """
        with db.get_session() as session:
            users = session.query(self.User).filter_by(state=state).order_by(self.User.created_at).all()
            return [user.to_dict() for user in users]

    def get_amount_of_users(self) -> int:
        with db.get_session() as session:
            users = (
                session.query(self.User.telegram_id)
                .filter_by(trip_attendance=TRIP_POLL_YES)
                .filter_by(is_staff=0)
                .filter_by(is_blocked=0)
                .all()
            )
            return len(users)

    def get_will_drive(self) -> list[int]:
        with db.get_session() as session:
            users = session.query(self.User.telegram_id).filter_by(will_drive="Обязательно! 🤩").all()
            return [user[0] for user in users]

    def get_previous_year(self) -> list[int]:
        with db.get_session() as session:
            users = session.query(self.User.telegram_id).filter_by(will_drive="Жду ответа по этому году ❗").all()
            return [user[0] for user in users]

    def get_did_not_finished(self) -> list[int]:
        with db.get_session() as session:
            users = session.query(self.User.telegram_id).filter_by(will_drive=None).all()
            return [user[0] for user in users]

    def get_dont_know(self) -> list[int]:
        with db.get_session() as session:
            users = session.query(self.User.telegram_id).filter_by(will_drive="Пока думаю 🤔")
            return [user[0] for user in users]


# Create global instance for backward compatibility
user_storage = UserStorage()
