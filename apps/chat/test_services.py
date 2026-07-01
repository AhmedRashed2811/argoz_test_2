from django.test import TestCase

from apps.accounts.models import User, UserProfile
from apps.chat.services import ChatService
from apps.companies.models import Company


class ChatServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="chat-acme")
        self.user = User.objects.create_user(email="one@example.com")
        self.other = User.objects.create_user(email="two@example.com")
        self.outsider = User.objects.create_user(email="outsider@example.com")
        for user in (self.user, self.other, self.outsider):
            UserProfile.objects.create(user=user, company=self.company)

    def test_direct_conversation_cannot_be_created_with_self(self):
        self.assertIsNone(
            ChatService.get_or_create_direct(
                company=self.company,
                user=self.user,
                other_id=self.user.id,
            )
        )

    def test_conversation_access_is_participant_scoped(self):
        conversation = ChatService.get_or_create_direct(
            company=self.company,
            user=self.user,
            other_id=self.other.id,
        )

        self.assertEqual(
            ChatService.get_conversation(user=self.user, conversation_id=conversation.id),
            conversation,
        )
        self.assertIsNone(
            ChatService.get_conversation(user=self.outsider, conversation_id=conversation.id)
        )

    def test_mark_read_only_marks_messages_from_other_participant(self):
        conversation = ChatService.get_or_create_direct(
            company=self.company,
            user=self.user,
            other_id=self.other.id,
        )
        ChatService.send_message(conversation=conversation, sender=self.user, body="from me")
        ChatService.send_message(conversation=conversation, sender=self.other, body="from them")

        updated = ChatService.mark_read(conversation=conversation, reader=self.user)

        self.assertEqual(updated, 1)
        self.assertEqual(ChatService.unread_total(self.user), 0)
