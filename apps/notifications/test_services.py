from django.test import TestCase

from apps.accounts.models import User, UserProfile
from apps.companies.models import Company
from apps.notifications.constants import NotificationCode
from apps.notifications.models import Notification, NotificationDelivery
from apps.notifications.services import NotificationService


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="notifications-acme")
        self.actor = User.objects.create_user(email="actor@example.com")
        self.recipient = User.objects.create_user(email="recipient@example.com")
        UserProfile.objects.create(user=self.actor, company=self.company)
        UserProfile.objects.create(user=self.recipient, company=self.company)

    def test_create_notification_adds_default_delivery(self):
        notification = NotificationService.create(
            company=self.company,
            recipient=self.recipient,
            code=NotificationCode.LEAD_ASSIGNED,
            title="Lead assigned",
        )

        self.assertIsNotNone(notification)
        self.assertEqual(NotificationDelivery.objects.filter(notification=notification).count(), 1)

    def test_create_for_users_excludes_actor_and_deduplicates_recipients(self):
        NotificationService.create_for_users(
            company=self.company,
            recipients=[self.actor, self.recipient, self.recipient],
            exclude_user=self.actor,
            code=NotificationCode.CAMPAIGN_APPROVED,
            title="Campaign approved",
        )

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().recipient, self.recipient)

    def test_mark_read_and_mark_all_read(self):
        first = NotificationService.create(
            company=self.company,
            recipient=self.recipient,
            code=NotificationCode.LEAD_ASSIGNED,
        )
        NotificationService.create(
            company=self.company,
            recipient=self.recipient,
            code=NotificationCode.MEETING_DUE,
        )

        NotificationService.mark_read(notification=first)
        self.assertTrue(Notification.objects.get(id=first.id).is_read)

        updated = NotificationService.mark_all_read(recipient=self.recipient)
        self.assertEqual(updated, 1)
        self.assertFalse(Notification.objects.filter(recipient=self.recipient, is_read=False).exists())
