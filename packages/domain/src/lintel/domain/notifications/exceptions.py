"""Notification-related exceptions."""


class NotificationDeliveryError(Exception):
    """Raised when a notification fails to be delivered to a channel."""
