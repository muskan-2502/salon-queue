"""Shared queue calculations and transition rules for every screen."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Barber, QueueEntry, QueueSettings


ACTIVE_STATUSES = (QueueEntry.Status.WAITING, QueueEntry.Status.CALLED, QueueEntry.Status.IN_CHAIR)
NO_SHOW_GRACE_PERIOD = timedelta(minutes=10)


class QueueRuleError(Exception):
    """An action that would violate the queue's status or assignment rules."""


def service_totals(service_queryset):
    """Return the estimated duration and price for a set of active services."""
    totals = service_queryset.aggregate(
        minutes=Sum("duration_minutes"), price=Sum("price_rupees")
    )
    return totals["minutes"] or 0, totals["price"] or 0


def get_queue_settings():
    settings, _ = QueueSettings.objects.get_or_create(pk=1)
    return settings


def barber_wait_minutes(barber, before_entry=None):
    """Sum service estimates in this barber's eligible queue before a turn."""
    entries = QueueEntry.objects.filter(
        status__in=ACTIVE_STATUSES
    ).filter(Q(barber=barber) | Q(barber__isnull=True))
    if before_entry is not None:
        entries = entries.filter(
            Q(created_at__lt=before_entry.created_at)
            | Q(created_at=before_entry.created_at, pk__lt=before_entry.pk)
        )
    return entries.aggregate(total=Sum("services__duration_minutes"))["total"] or 0


def expected_wait_minutes(barbers, chosen_barber=None, before_entry=None):
    """Estimate wait for a chosen barber or the fastest active barber."""
    candidates = [chosen_barber] if chosen_barber else list(
        barber for barber in barbers if barber.is_on_duty and barber.availability != "break"
    )
    if not candidates:
        return 0
    return min(barber_wait_minutes(barber, before_entry) for barber in candidates)


def queue_position(entry, barbers):
    """Return the spot in the selected barber's eligible queue (or fastest queue)."""
    earlier = QueueEntry.objects.filter(
        status__in=(QueueEntry.Status.WAITING, QueueEntry.Status.CALLED)
    ).exclude(pk=entry.pk).filter(
        Q(created_at__lt=entry.created_at)
        | Q(created_at=entry.created_at, pk__lt=entry.pk)
    )
    if entry.barber_id:
        return earlier.filter(Q(barber_id=entry.barber_id) | Q(barber__isnull=True)).count() + 1

    eligible_barbers = [
        barber for barber in barbers
        if barber.is_on_duty and barber.availability != "break"
    ]
    if not eligible_barbers:
        return earlier.count() + 1
    options = [
        (
            barber_wait_minutes(barber, before_entry=entry),
            earlier.filter(Q(barber_id=barber.pk) | Q(barber__isnull=True)).count(),
        )
        for barber in eligible_barbers
    ]
    return min(options)[1] + 1


def create_queue_entry(customer_name, phone, services, barber=None, customer=None):
    """Append a remote or walk-in customer to the shared queue."""
    if QueueEntry.objects.filter(phone=phone, status__in=ACTIVE_STATUSES).exists():
        raise QueueRuleError("phone_active")
    try:
        with transaction.atomic():
            entry = QueueEntry.objects.create(
                customer_name=customer_name,
                phone=phone,
                customer=customer,
                barber=barber,
                status=QueueEntry.Status.WAITING,
            )
            entry.services.set(services)
    except IntegrityError as error:
        if QueueEntry.objects.filter(phone=phone, status__in=ACTIVE_STATUSES).exists():
            raise QueueRuleError("phone_active") from error
        raise
    return entry


def call_next_for_barber(barber):
    """Call the oldest waiting customer assigned to this barber or Any."""
    with transaction.atomic():
        barber = Barber.objects.select_for_update().get(pk=barber.pk)
        if not barber.is_on_duty or barber.availability == Barber.Availability.BREAK:
            raise QueueRuleError("barber_unavailable")
        if QueueEntry.objects.filter(status=QueueEntry.Status.CALLED, barber=barber).exists():
            raise QueueRuleError("called_pending")
        entry = QueueEntry.objects.select_for_update().filter(
            status=QueueEntry.Status.WAITING
        ).filter(
            Q(barber=barber) | Q(barber__isnull=True)
        ).order_by("created_at", "id").first()
        if entry is None:
            raise QueueRuleError("no_next_customer")
        updated = QueueEntry.objects.filter(
            pk=entry.pk, status=QueueEntry.Status.WAITING
        ).update(
            status=QueueEntry.Status.CALLED,
            barber=barber,
            called_at=timezone.now(),
        )
        if updated != 1:
            raise QueueRuleError("queue_changed")
        entry.refresh_from_db()
    return entry


def can_mark_no_show(entry, now=None):
    now = now or timezone.now()
    return (
        entry.status == QueueEntry.Status.CALLED
        and entry.called_at is not None
        and entry.called_at <= now - NO_SHOW_GRACE_PERIOD
    )


def mark_no_show(entry):
    if entry.status != QueueEntry.Status.CALLED:
        raise QueueRuleError("no_show_called_only")
    if not can_mark_no_show(entry):
        raise QueueRuleError("no_show_too_early")
    updated = QueueEntry.objects.filter(
        pk=entry.pk, status=QueueEntry.Status.CALLED
    ).update(status=QueueEntry.Status.NO_SHOW)
    if updated != 1:
        raise QueueRuleError("queue_changed")


def cancel_waiting_entry(entry):
    if entry.status != QueueEntry.Status.WAITING:
        raise QueueRuleError("cancel_waiting_only")
    updated = QueueEntry.objects.filter(
        pk=entry.pk, status=QueueEntry.Status.WAITING
    ).update(status=QueueEntry.Status.CANCELLED)
    if updated != 1:
        raise QueueRuleError("queue_changed")


def start_service_for_barber(barber):
    """Move this barber's called customer into the chair."""
    with transaction.atomic():
        barber = Barber.objects.select_for_update().get(pk=barber.pk)
        if not barber.is_on_duty or barber.availability == Barber.Availability.BREAK:
            raise QueueRuleError("barber_unavailable")
        if QueueEntry.objects.filter(
            barber=barber, status=QueueEntry.Status.IN_CHAIR
        ).exists():
            raise QueueRuleError("chair_occupied")
        entry = QueueEntry.objects.select_for_update().filter(
            barber=barber, status=QueueEntry.Status.CALLED
        ).order_by("called_at", "id").first()
        if entry is None:
            raise QueueRuleError("no_called_customer")
        updated = QueueEntry.objects.filter(
            pk=entry.pk, status=QueueEntry.Status.CALLED, barber=barber
        ).update(
            status=QueueEntry.Status.IN_CHAIR,
            started_at=timezone.now(),
        )
        if updated != 1:
            raise QueueRuleError("queue_changed")
        Barber.objects.filter(pk=barber.pk).update(availability=Barber.Availability.BUSY)
        entry.refresh_from_db()
    return entry


def complete_service_for_barber(barber):
    """Finish the active service and free the barber's chair."""
    with transaction.atomic():
        barber = Barber.objects.select_for_update().get(pk=barber.pk)
        entry = QueueEntry.objects.select_for_update().filter(
            barber=barber, status=QueueEntry.Status.IN_CHAIR
        ).order_by("started_at", "id").first()
        if entry is None:
            raise QueueRuleError("no_current_customer")
        updated = QueueEntry.objects.filter(
            pk=entry.pk, barber=barber, status=QueueEntry.Status.IN_CHAIR
        ).update(status=QueueEntry.Status.DONE, completed_at=timezone.now())
        if updated != 1:
            raise QueueRuleError("queue_changed")
        Barber.objects.filter(pk=barber.pk).update(availability=Barber.Availability.AVAILABLE)
        entry.refresh_from_db()
    return entry


def set_barber_break(barber, on_break):
    """Change availability without stranding a called or in-chair customer."""
    with transaction.atomic():
        barber = Barber.objects.select_for_update().get(pk=barber.pk)
        if not barber.is_on_duty:
            raise QueueRuleError("barber_off_duty")
        if on_break and QueueEntry.objects.filter(
            barber=barber,
            status__in=(QueueEntry.Status.CALLED, QueueEntry.Status.IN_CHAIR),
        ).exists():
            raise QueueRuleError("barber_has_active_customer")
        availability = Barber.Availability.BREAK if on_break else Barber.Availability.AVAILABLE
        Barber.objects.filter(pk=barber.pk).update(availability=availability)


def set_barber_on_duty(barber, on_duty):
    """Prevent taking a barber off duty while they have an active customer."""
    with transaction.atomic():
        barber = Barber.objects.select_for_update().get(pk=barber.pk)
        if not on_duty and QueueEntry.objects.filter(
            barber=barber,
            status__in=(QueueEntry.Status.CALLED, QueueEntry.Status.IN_CHAIR),
        ).exists():
            raise QueueRuleError("barber_has_active_customer")
        Barber.objects.filter(pk=barber.pk).update(is_on_duty=on_duty)
