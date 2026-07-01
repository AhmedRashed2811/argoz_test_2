from django.test import TestCase

from apps.accounts.models import User, UserProfile
from apps.companies.models import Company
from apps.notebook.services import NotebookService


class NotebookServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="notebook-acme")
        self.owner = User.objects.create_user(email="owner@example.com")
        self.other = User.objects.create_user(email="other@example.com")
        UserProfile.objects.create(user=self.owner, company=self.company)
        UserProfile.objects.create(user=self.other, company=self.company)

    def test_empty_note_is_not_created(self):
        self.assertIsNone(NotebookService.create(company=self.company, owner=self.owner, title="", body=""))

    def test_note_access_is_owner_scoped(self):
        note = NotebookService.create(
            company=self.company,
            owner=self.owner,
            title="Private",
            body="Only mine",
        )

        self.assertEqual(NotebookService.get_note(owner=self.owner, note_id=note.id), note)
        self.assertIsNone(NotebookService.get_note(owner=self.other, note_id=note.id))

    def test_title_is_trimmed_to_model_limit(self):
        note = NotebookService.create(
            company=self.company,
            owner=self.owner,
            title="x" * 250,
            body="Body",
        )

        self.assertEqual(len(note.title), 200)
