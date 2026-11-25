from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count
from django.test import TestCase

from .models import Barber, QueueEntry, Service


class CustomerAccountTests(TestCase):
    def test_registration_hashes_password_and_logs_customer_in(self):
        response = self.client.post(
            "/account/register/",
            {
                "customer_name": "Asha Patel",
                "phone": "9876543210",
                "password": "QueuePassword#2026",
            },
        )

        user = get_user_model().objects.get(username="9876543210")
        self.assertRedirects(response, "/")
        self.assertTrue(user.check_password("QueuePassword#2026"))
        self.assertNotEqual(user.password, "QueuePassword#2026")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_login_rejects_incorrect_password(self):
        get_user_model().objects.create_user(
            username="9876543210", first_name="Asha Patel", password="QueuePassword#2026"
        )

        response = self.client.post(
            "/account/login/", {"phone": "9876543210", "password": "incorrect"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "We couldn't log you in with that mobile number and password.",
            response.context["errors"],
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_accepts_correct_password_and_logout_clears_session(self):
        user = get_user_model().objects.create_user(
            username="9876543210", first_name="Asha Patel", password="QueuePassword#2026"
        )

        response = self.client.post(
            "/account/login/", {"phone": "9876543210", "password": "QueuePassword#2026"}
        )

        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        response = self.client.post("/account/logout/")

        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_queue_join_uses_saved_identity_and_home_shows_spot(self):
        user = get_user_model().objects.create_user(
            username="9876543210", first_name="Asha Patel", password="QueuePassword#2026"
        )
        service = Service.objects.create(
            name="Account Test Haircut", duration_minutes=30, price_rupees=150
        )
        barber = Barber.objects.create(name="Account Test Barber")
        self.client.force_login(user)

        response = self.client.post(
            "/join/",
            {
                "customer_name": "Not Asha",
                "phone": "1111111111",
                "service_ids": [str(service.pk)],
                "barber_id": str(barber.pk),
            },
        )

        entry = QueueEntry.objects.get(customer=user)
        self.assertRedirects(response, f"/status/{entry.pk}/")
        self.assertEqual(entry.customer, user)
        self.assertEqual(entry.customer_name, "Asha Patel")
        self.assertEqual(entry.phone, "9876543210")

        home_response = self.client.get("/")
        self.assertEqual(home_response.context["personal_entry"], entry)
        self.assertContains(home_response, "Account Test Haircut")
        self.assertContains(home_response, "Account Test Barber")
        self.assertContains(home_response, entry.token)


class PopulateDemoDataTests(TestCase):
    def test_command_is_repeatable_and_creates_requested_queue_distribution(self):
        call_command("populate_demo_data")
        call_command("populate_demo_data")

        self.assertEqual(Barber.objects.count(), 5)
        self.assertEqual(QueueEntry.objects.count(), 22)
        self.assertEqual(
            QueueEntry.objects.filter(status=QueueEntry.Status.WAITING).count(), 15
        )
        self.assertEqual(
            QueueEntry.objects.filter(status=QueueEntry.Status.IN_CHAIR).count(), 4
        )
        self.assertEqual(
            QueueEntry.objects.filter(status=QueueEntry.Status.CALLED).count(), 1
        )
        self.assertEqual(
            QueueEntry.objects.filter(status=QueueEntry.Status.DONE).count(), 2
        )
        self.assertEqual(
            dict(
                QueueEntry.objects.filter(status=QueueEntry.Status.WAITING)
                .values("barber__name")
                .order_by("barber__name")
                .annotate(total=Count("id"))
                .values_list("barber__name", "total")
            ),
            {"Amit": 3, "Kabir": 5, "Neel": 4, "Ravi": 2, None: 1},
        )
        self.assertEqual(
            Barber.objects.get(name="Imran").availability, Barber.Availability.BREAK
        )

    def test_command_refuses_to_delete_extra_barbers(self):
        Barber.objects.create(name="Extra Barber")

        with self.assertRaises(CommandError):
            call_command("populate_demo_data")

        self.assertEqual(Barber.objects.count(), 4)
