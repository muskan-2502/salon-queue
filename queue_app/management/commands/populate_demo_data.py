from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from queue_app.models import Barber, QueueEntry, Service


BARBER_QUEUE_TARGETS = {"Ravi": 2, "Amit": 3, "Neel": 4, "Kabir": 5}
SERVICE_DATA = [
    ("Haircut", 30, 150, 1),
    ("Beard trim", 15, 80, 2),
    ("Hair spa", 45, 400, 3),
    ("Color touch-up", 60, 700, 4),
    ("Head massage", 20, 120, 5),
]
BARBER_DATA = [
    ("Ravi", Barber.Availability.BUSY, 1),
    ("Amit", Barber.Availability.BUSY, 2),
    ("Imran", Barber.Availability.BREAK, 3),
    ("Neel", Barber.Availability.BUSY, 4),
    ("Kabir", Barber.Availability.BUSY, 5),
]
WAITING_CUSTOMERS = {
    "Ravi": [
        ("9990000101", "Priya Nair", "Haircut"),
        ("9990000102", "Vikram Joshi", "Beard trim"),
    ],
    "Amit": [
        ("9990000103", "Anaya Shah", "Hair spa"),
        ("9990000104", "Rahul Desai", "Haircut"),
        ("9990000105", "Meera Iyer", "Head massage"),
    ],
    "Neel": [
        ("9990000106", "Ishaan Mehta", "Haircut"),
        ("9990000107", "Tara Patel", "Beard trim"),
        ("9990000108", "Rohan Shah", "Hair spa"),
        ("9990000109", "Diya Rao", "Color touch-up"),
    ],
    "Kabir": [
        ("9990000110", "Aarav Kulkarni", "Haircut"),
        ("9990000111", "Sana Khan", "Beard trim"),
        ("9990000112", "Kabir Shah", "Hair spa"),
        ("9990000113", "Pooja Menon", "Head massage"),
        ("9990000114", "Aditya Rao", "Color touch-up"),
    ],
}


class Command(BaseCommand):
    help = "Populate the salon with a repeatable 22-customer queue demo."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        services = self._ensure_services()
        barbers = self._ensure_barbers()

        self._ensure_entry(
            phone="9990000007",
            name="Mohan Das",
            status=QueueEntry.Status.IN_CHAIR,
            barber=barbers["Ravi"],
            services=[services["Haircut"]],
            started_at=now - timedelta(minutes=14),
        )
        self._ensure_entry(
            phone="9990000002",
            name="Rhea Mehta",
            status=QueueEntry.Status.IN_CHAIR,
            barber=barbers["Amit"],
            services=[services["Hair spa"]],
            started_at=now - timedelta(minutes=9),
        )
        self._ensure_entry(
            phone="9990000001",
            name="Kunal Shah",
            status=QueueEntry.Status.CALLED,
            barber=barbers["Ravi"],
            services=[services["Haircut"]],
            called_at=now - timedelta(minutes=3),
        )
        self._ensure_entry(
            phone="9990000115",
            name="Siddharth Rao",
            status=QueueEntry.Status.IN_CHAIR,
            barber=barbers["Neel"],
            services=[services["Beard trim"]],
            started_at=now - timedelta(minutes=11),
        )
        self._ensure_entry(
            phone="9990000116",
            name="Maya Joshi",
            status=QueueEntry.Status.IN_CHAIR,
            barber=barbers["Kabir"],
            services=[services["Haircut"], services["Beard trim"]],
            started_at=now - timedelta(minutes=6),
        )

        self._ensure_waiting_customers(services, barbers)
        self._ensure_completed_customers(now, services)
        self._verify_result(barbers)

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded 22 queue customers: 15 waiting, 4 in chairs, "
                "1 called, and 2 completed. Imran is on break."
            )
        )

    def _ensure_services(self):
        services = {}
        for name, minutes, price, order in SERVICE_DATA:
            service, _ = Service.objects.update_or_create(
                name=name,
                defaults={
                    "duration_minutes": minutes,
                    "price_rupees": price,
                    "display_order": order,
                    "is_active": True,
                },
            )
            services[name] = service
        return services

    def _ensure_barbers(self):
        barbers = {}
        for name, availability, order in BARBER_DATA:
            barber, _ = Barber.objects.update_or_create(
                name=name,
                defaults={
                    "availability": availability,
                    "is_on_duty": True,
                    "display_order": order,
                },
            )
            barbers[name] = barber

        if Barber.objects.count() != len(BARBER_DATA):
            raise CommandError(
                "Expected exactly five barbers. No existing barbers were deleted."
            )
        return barbers

    def _ensure_entry(
        self,
        *,
        phone,
        name,
        status,
        barber,
        services,
        called_at=None,
        started_at=None,
        completed_at=None,
        created_at=None,
    ):
        if get_user_model().objects.filter(username=phone).exists():
            raise CommandError(
                f"Demo phone {phone} belongs to an account; refusing to use it."
            )

        matches = QueueEntry.objects.filter(phone=phone)
        if matches.count() > 1:
            raise CommandError(f"Multiple queue records already use demo phone {phone}.")
        entry = matches.first()
        if entry and entry.customer_id is not None:
            raise CommandError(
                f"Demo phone {phone} belongs to a customer account; refusing to change it."
            )

        values = {
            "customer_name": name,
            "phone": phone,
            "status": status,
            "barber": barber,
            "called_at": called_at,
            "started_at": started_at,
            "completed_at": completed_at,
        }
        if entry is None:
            entry = QueueEntry.objects.create(**values)
        else:
            QueueEntry.objects.filter(pk=entry.pk).update(**values)
            entry.refresh_from_db()
        if created_at is not None:
            QueueEntry.objects.filter(pk=entry.pk).update(created_at=created_at)
        entry.services.set(services)
        return entry

    def _ensure_waiting_customers(self, services, barbers):
        for barber_name, target_count in BARBER_QUEUE_TARGETS.items():
            barber = barbers[barber_name]
            current_count = QueueEntry.objects.filter(
                barber=barber, status=QueueEntry.Status.WAITING
            ).count()
            if current_count > target_count:
                raise CommandError(
                    f"{barber_name} already has {current_count} waiting customers; "
                    f"the demo target is {target_count}. No queue records were removed."
                )

            customers = WAITING_CUSTOMERS[barber_name]
            missing = target_count - current_count
            for phone, name, service_name in customers[:missing]:
                self._ensure_entry(
                    phone=phone,
                    name=name,
                    status=QueueEntry.Status.WAITING,
                    barber=barber,
                    services=[services[service_name]],
                )

        unassigned_waiting = QueueEntry.objects.filter(
            status=QueueEntry.Status.WAITING, barber__isnull=True
        ).count()
        if unassigned_waiting != 1:
            raise CommandError(
                "Expected exactly one existing Any-barber waiting spot; "
                "no existing queue records were reassigned."
            )

    def _ensure_completed_customers(self, now, services):
        completed_at = now - timedelta(days=1)
        for phone, name, service_name in [
            ("9990000117", "Nikita Shah", "Haircut"),
            ("9990000118", "Yash Mehta", "Beard trim"),
        ]:
            self._ensure_entry(
                phone=phone,
                name=name,
                status=QueueEntry.Status.DONE,
                barber=None,
                services=[services[service_name]],
                started_at=completed_at - timedelta(minutes=20),
                completed_at=completed_at,
                created_at=completed_at - timedelta(minutes=35),
            )

    def _verify_result(self, barbers):
        waiting_count = QueueEntry.objects.filter(
            status=QueueEntry.Status.WAITING
        ).count()
        chair_count = QueueEntry.objects.filter(
            status=QueueEntry.Status.IN_CHAIR
        ).count()
        total_count = QueueEntry.objects.count()

        if (total_count, waiting_count, chair_count) != (22, 15, 4):
            raise CommandError(
                "Seeded data does not match the requested totals "
                f"(customers={total_count}, waiting={waiting_count}, in_chair={chair_count})."
            )

        for barber_name, target_count in BARBER_QUEUE_TARGETS.items():
            barber = barbers[barber_name]
            if QueueEntry.objects.filter(
                barber=barber, status=QueueEntry.Status.IN_CHAIR
            ).count() != 1:
                raise CommandError(f"{barber_name} must have exactly one customer in the chair.")
            if QueueEntry.objects.filter(
                barber=barber, status=QueueEntry.Status.WAITING
            ).count() != target_count:
                raise CommandError(
                    f"{barber_name} does not have the requested {target_count}-person queue."
                )

        if barbers["Imran"].availability != Barber.Availability.BREAK:
            raise CommandError("Imran must be the one barber on break.")
