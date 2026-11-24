from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.conf import settings


class Service(models.Model):
    name = models.CharField(max_length=80, unique=True)
    duration_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(240)]
    )
    price_rupees = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Barber(models.Model):
    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        BUSY = "busy", "Busy"
        BREAK = "break", "On break"

    name = models.CharField(max_length=80, unique=True)
    availability = models.CharField(
        max_length=12, choices=Availability.choices, default=Availability.AVAILABLE
    )
    is_on_duty = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class QueueSettings(models.Model):
    online_joining_open = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Online queue open" if self.online_joining_open else "Online queue closed"


class QueueEntry(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        IN_CHAIR = "in_chair", "In chair"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No-show"

    customer_name = models.CharField(max_length=100)
    phone = models.CharField(
        max_length=10,
        validators=[RegexValidator(r"^\d{10}$", "Enter a 10-digit phone number.")],
        db_index=True,
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="queue_entries",
    )
    barber = models.ForeignKey(
        Barber, null=True, blank=True, on_delete=models.PROTECT, related_name="queue_entries"
    )
    services = models.ManyToManyField(Service, related_name="queue_entries")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.WAITING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    called_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["phone"],
                condition=models.Q(status__in=["waiting", "called", "in_chair"]),
                name="unique_active_spot_phone",
            )
        ]

    def __str__(self):
        return f"{self.token} — {self.customer_name}"

    @property
    def token(self):
        return f"S-{self.pk}" if self.pk else "S-NEW"
