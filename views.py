import re

from django.contrib.auth import authenticate, get_user_model, login as auth_login, logout as auth_logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from .language import ENGLISH
from .models import Barber, QueueEntry, Service
from .queue_rules import (
    ACTIVE_STATUSES,
    barber_wait_minutes,
    call_next_for_barber,
    can_mark_no_show,
    cancel_waiting_entry,
    complete_service_for_barber,
    create_queue_entry,
    expected_wait_minutes,
    get_queue_settings,
    mark_no_show,
    QueueRuleError,
    queue_position,
    set_barber_break,
    set_barber_on_duty,
    service_totals,
    start_service_for_barber,
)


def _base_context(request, screen_id):
    labels = ENGLISH
    page_titles = {
        "home": "page_home", "join": "page_join", "login": "page_login",
        "register": "page_register", "status": "page_status",
        "reception": "page_reception", "barber": "page_barber",
        "display": "page_display", "settings": "page_settings",
    }
    return {
        "screen_id": screen_id,
        "page_title": labels[page_titles[screen_id]],
        "labels": labels,
    }


def _service_minutes(entry):
    return service_totals(entry.services.all())[0]


def _barber_display(barber, labels):
    if not barber.is_on_duty:
        return labels["off_duty"]
    return {
        Barber.Availability.AVAILABLE: labels["available"],
        Barber.Availability.BUSY: labels["busy"],
        Barber.Availability.BREAK: labels["break"],
    }[barber.availability]


def home(request):
    labels = ENGLISH
    queue_settings = get_queue_settings()
    barbers = list(Barber.objects.all())
    entries = QueueEntry.objects.filter(status__in=ACTIVE_STATUSES)
    personal_entry = None
    if request.user.is_authenticated:
        personal_entry = (
            entries.filter(
                Q(customer=request.user)
                | Q(customer__isnull=True, phone=request.user.get_username())
            )
            .select_related("barber")
            .prefetch_related("services")
            .order_by("created_at", "id")
            .first()
        )
    waiting_count = entries.filter(status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED]).count()
    barber_cards = [
        {
            "barber": barber,
            "availability_label": _barber_display(barber, labels),
            "wait_minutes": barber_wait_minutes(barber),
        }
        for barber in barbers
    ]
    wait_values = [card["wait_minutes"] for card in barber_cards if card["barber"].is_on_duty and card["barber"].availability != Barber.Availability.BREAK]
    context = _base_context(request, "home")
    context.update(
        {
            "waiting_count": waiting_count,
            "overall_wait": min(wait_values) if wait_values else 0,
            "barber_cards": barber_cards,
            "queue_open": queue_settings.online_joining_open,
            "personal_entry": personal_entry,
        }
    )
    return render(request, "home.html", context)


def join(request):
    labels = ENGLISH
    queue_settings = get_queue_settings()
    queue_open = queue_settings.online_joining_open
    services = list(Service.objects.filter(is_active=True))
    barbers = list(Barber.objects.filter(is_on_duty=True))
    selected_ids = []
    errors = []
    saved_name = request.user.first_name if request.user.is_authenticated else ""
    saved_phone = request.user.get_username() if request.user.is_authenticated else ""
    values = {"customer_name": saved_name, "phone": saved_phone, "barber_id": ""}
    chosen_services = []
    barber_cards = []
    for barber_item in barbers:
        barber_cards.append(
            {
                "barber": barber_item,
                "availability_label": _barber_display(barber_item, labels),
                "wait_minutes": barber_wait_minutes(barber_item),
            }
        )
    eligible_waits = [
        item["wait_minutes"] for item in barber_cards
        if item["barber"].availability != Barber.Availability.BREAK
    ]
    fastest_wait = min(eligible_waits) if eligible_waits else 0
    service_minutes = 0
    total_price = 0
    wait_minutes = fastest_wait

    if request.method == "POST" and queue_open:
        values = {
            "customer_name": saved_name or request.POST.get("customer_name", "").strip(),
            "phone": saved_phone or request.POST.get("phone", "").strip(),
            "barber_id": request.POST.get("barber_id", ""),
        }
        selected_ids = list(dict.fromkeys(request.POST.getlist("service_ids")))
        if not values["customer_name"]:
            errors.append(labels["name_error"])
        if not re.fullmatch(r"[0-9]{10}", values["phone"]):
            errors.append(labels["phone_error"])
        if len(selected_ids) > 3:
            errors.append(labels["max_services_error"])
        chosen_services = [service for service in services if str(service.pk) in selected_ids]
        if not chosen_services:
            errors.append(labels["select_service_error"])
        if len(chosen_services) != len(selected_ids) and selected_ids:
            errors.append(labels["select_service_error"])

        selected_barber = None
        if values["barber_id"]:
            selected_barber = next((barber for barber in barbers if str(barber.pk) == values["barber_id"]), None)
            if selected_barber is None or selected_barber.availability == Barber.Availability.BREAK:
                errors.append(labels["select_barber"])

        if chosen_services:
            service_minutes, total_price = service_totals(Service.objects.filter(pk__in=[s.pk for s in chosen_services]))
        wait_minutes = expected_wait_minutes(barbers, selected_barber) if barbers else 0

        if not errors:
            existing = QueueEntry.objects.filter(phone=values["phone"], status__in=ACTIVE_STATUSES).first()
            if existing:
                return HttpResponseRedirect(f"{reverse('status', kwargs={'spot_id': existing.pk})}?existing=1")
            try:
                entry = create_queue_entry(
                    values["customer_name"],
                    values["phone"],
                    chosen_services,
                    selected_barber,
                    customer=request.user if request.user.is_authenticated else None,
                )
            except QueueRuleError:
                existing = QueueEntry.objects.filter(phone=values["phone"], status__in=ACTIVE_STATUSES).first()
                if existing:
                    return HttpResponseRedirect(f"{reverse('status', kwargs={'spot_id': existing.pk})}?existing=1")
                raise
            return redirect("status", spot_id=entry.pk)

    context = _base_context(request, "join")
    context.update(
        {
            "services": services,
            "barbers": barbers,
            "barber_cards": barber_cards,
            "fastest_wait": fastest_wait,
            "values": values,
            "selected_ids": selected_ids,
            "selected_barber": values["barber_id"],
            "errors": errors,
            "service_minutes": service_minutes,
            "total_price": total_price,
            "wait_minutes": wait_minutes,
            "queue_open": queue_open,
        }
    )
    return render(request, "join.html", context)


def register(request):
    labels = ENGLISH
    if request.user.is_authenticated:
        return redirect("home")

    values = {"customer_name": "", "phone": ""}
    errors = []
    if request.method == "POST":
        values = {
            "customer_name": request.POST.get("customer_name", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
        }
        password = request.POST.get("password", "")
        if not values["customer_name"]:
            errors.append(labels["name_error"])
        if not re.fullmatch(r"[0-9]{10}", values["phone"]):
            errors.append(labels["phone_error"])
        if not password:
            errors.append(labels["password_required"])

        User = get_user_model()
        user = User(username=values["phone"], first_name=values["customer_name"])
        if password and values["customer_name"] and re.fullmatch(r"[0-9]{10}", values["phone"]):
            try:
                validate_password(password, user=user)
            except ValidationError as error:
                errors.extend(error.messages)
        if User.objects.filter(username=values["phone"]).exists():
            errors.append(labels["account_phone_used"])

        if not errors:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=values["phone"],
                        first_name=values["customer_name"],
                        password=password,
                    )
            except IntegrityError:
                errors.append(labels["account_phone_used"])
            else:
                auth_login(request, user)
                return redirect("home")

    context = _base_context(request, "register")
    context.update({"values": values, "errors": errors})
    return render(request, "register.html", context)


def login_view(request):
    labels = ENGLISH
    if request.user.is_authenticated:
        return redirect("home")

    phone = ""
    errors = []
    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=phone, password=password)
        if user is None:
            errors.append(labels["login_error"])
        else:
            auth_login(request, user)
            next_url = request.POST.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("home")

    context = _base_context(request, "login")
    context.update({"phone": phone, "errors": errors, "next": request.GET.get("next", "")})
    return render(request, "login.html", context)


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("home")


def status(request, spot_id):
    entry = get_object_or_404(QueueEntry.objects.prefetch_related("services", "barber"), pk=spot_id)
    barbers = list(Barber.objects.filter(is_on_duty=True))
    is_waiting = entry.status == QueueEntry.Status.WAITING
    position = queue_position(entry, barbers) if is_waiting else 0
    wait_minutes = (
        barber_wait_minutes(entry.barber, before_entry=entry)
        if entry.barber_id and is_waiting
        else expected_wait_minutes(barbers, before_entry=entry) if is_waiting else 0
    )
    called_barber = entry.barber.name if entry.barber_id else ""
    barber_on_break = bool(
        entry.barber_id and entry.barber.availability == Barber.Availability.BREAK
    )
    barber_off_duty = bool(entry.barber_id and not entry.barber.is_on_duty)
    context = _base_context(request, "status")
    context.update({
        "entry": entry,
        "position": position,
        "service_minutes": _service_minutes(entry),
        "wait_minutes": wait_minutes,
        "called_barber": called_barber,
        "barber_on_break": barber_on_break,
        "barber_off_duty": barber_off_duty,
        "existing_spot": request.GET.get("existing") == "1",
    })
    return render(request, "status.html", context)


def status_summary(request, spot_id):
    entry = get_object_or_404(QueueEntry.objects.select_related("barber"), pk=spot_id)
    barbers = list(Barber.objects.filter(is_on_duty=True))
    is_waiting = entry.status == QueueEntry.Status.WAITING
    position = queue_position(entry, barbers) if is_waiting else 0
    wait_minutes = (
        barber_wait_minutes(entry.barber, before_entry=entry)
        if entry.barber_id and is_waiting
        else expected_wait_minutes(barbers, before_entry=entry) if is_waiting else 0
    )
    return JsonResponse({
        "token": entry.token,
        "status": entry.status,
        "position": position,
        "wait_minutes": wait_minutes,
        "barber_name": entry.barber.name if entry.barber_id else "",
        "barber_on_break": bool(
            entry.barber_id and entry.barber.availability == Barber.Availability.BREAK
        ),
        "barber_off_duty": bool(entry.barber_id and not entry.barber.is_on_duty),
    })


def _reception_context(request):
    labels = ENGLISH
    now = timezone.now()
    barbers = list(Barber.objects.all())
    barber_cards = []
    for barber_item in barbers:
        current = QueueEntry.objects.filter(
            barber=barber_item, status=QueueEntry.Status.IN_CHAIR
        ).prefetch_related("services").order_by("created_at", "id").first()
        called = QueueEntry.objects.filter(
            barber=barber_item, status=QueueEntry.Status.CALLED
        ).prefetch_related("services").order_by("created_at", "id").first()
        next_candidates = QueueEntry.objects.filter(status=QueueEntry.Status.WAITING)
        if barber_item.is_on_duty and barber_item.availability != Barber.Availability.BREAK:
            next_candidates = next_candidates.filter(Q(barber=barber_item) | Q(barber__isnull=True))
        else:
            next_candidates = next_candidates.filter(barber=barber_item)
        next_customer = next_candidates.prefetch_related("services").order_by("created_at", "id").first()
        service_minutes = service_totals(current.services.all())[0] if current else 0
        elapsed = int((now - current.started_at).total_seconds() // 60) if current and current.started_at else 0
        barber_cards.append({
            "barber": barber_item,
            "availability_label": _barber_display(barber_item, labels),
            "current": current,
            "current_elapsed": elapsed,
            "current_remaining": max(0, service_minutes - elapsed),
            "called": called,
            "next_customer": next_customer,
            "can_call": (
                barber_item.is_on_duty
                and barber_item.availability != Barber.Availability.BREAK
                and called is None
            ),
        })

    services = list(Service.objects.filter(is_active=True))
    entries = QueueEntry.objects.filter(
        status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED]
    ).select_related("barber").prefetch_related("services")
    waiting_entries = []
    for entry in entries:
        waited_minutes = max(0, int((now - entry.created_at).total_seconds() // 60))
        if entry.status == QueueEntry.Status.WAITING:
            entry.estimated_wait = (
                barber_wait_minutes(entry.barber, before_entry=entry)
                if entry.barber_id
                else expected_wait_minutes(barbers, before_entry=entry)
            )
        else:
            entry.estimated_wait = 0
        entry.waited_minutes = waited_minutes
        entry.waited_over_hour = waited_minutes > 60
        entry.no_show_ready = can_mark_no_show(entry, now)
        waiting_entries.append(entry)

    return {
        **_base_context(request, "reception"),
        "barber_cards": barber_cards,
        "waiting_entries": waiting_entries,
        "services": services,
        "walkin_values": {"customer_name": "", "phone": ""},
        "walkin_selected_ids": [],
        "walkin_errors": [],
        "walkin_dialog_open": False,
        "notice": labels.get(f"reception_notice_{request.GET.get('notice', '')}", ""),
        "action_error": labels.get(f"reception_error_{request.GET.get('error', '')}", ""),
        "last_updated": now,
    }


def reception(request):
    labels = ENGLISH
    context = _reception_context(request)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "add-walkin":
            values = {
                "customer_name": request.POST.get("customer_name", "").strip(),
                "phone": request.POST.get("phone", "").strip(),
            }
            selected_ids = list(dict.fromkeys(request.POST.getlist("service_ids")))
            selected_services = list(Service.objects.filter(is_active=True, pk__in=selected_ids))
            errors = []
            if not values["customer_name"]:
                errors.append(labels["name_error"])
            if not re.fullmatch(r"[0-9]{10}", values["phone"]):
                errors.append(labels["phone_error"])
            if len(selected_ids) > 3:
                errors.append(labels["max_services_error"])
            if not selected_services or len(selected_services) != len(selected_ids):
                errors.append(labels["select_service_error"])
            if not errors:
                try:
                    create_queue_entry(values["customer_name"], values["phone"], selected_services)
                except QueueRuleError:
                    errors.append(labels["walkin_duplicate_phone"])
                else:
                    return redirect(f"{reverse('reception')}?notice=walkin_added")
            context.update({
                "walkin_values": values,
                "walkin_selected_ids": selected_ids,
                "walkin_errors": errors,
                "walkin_dialog_open": True,
            })
            return render(request, "reception.html", context)

        try:
            if action == "call-next":
                barber_item = get_object_or_404(Barber, pk=request.POST.get("barber_id"))
                call_next_for_barber(barber_item)
                notice = "called"
            elif action == "no-show":
                entry = get_object_or_404(QueueEntry, pk=request.POST.get("entry_id"))
                mark_no_show(entry)
                notice = "no_show"
            elif action == "cancel":
                entry = get_object_or_404(QueueEntry, pk=request.POST.get("entry_id"))
                cancel_waiting_entry(entry)
                notice = "cancelled"
            else:
                return redirect(f"{reverse('reception')}?error=invalid_action")
        except QueueRuleError as error:
            return redirect(f"{reverse('reception')}?error={error.args[0]}")
        return redirect(f"{reverse('reception')}?notice={notice}")

    return render(request, "reception.html", context)


def reception_fragment(request):
    return render(request, "reception_content.html", _reception_context(request))


def _barber_view_context(request, barber_item):
    labels = ENGLISH
    now = timezone.now()
    current = QueueEntry.objects.filter(
        barber=barber_item, status=QueueEntry.Status.IN_CHAIR
    ).prefetch_related("services").order_by("started_at", "id").first()
    called = QueueEntry.objects.filter(
        barber=barber_item, status=QueueEntry.Status.CALLED
    ).prefetch_related("services").order_by("called_at", "id").first()
    next_candidates = QueueEntry.objects.filter(status=QueueEntry.Status.WAITING)
    if barber_item.is_on_duty and barber_item.availability != Barber.Availability.BREAK:
        next_candidates = next_candidates.filter(Q(barber=barber_item) | Q(barber__isnull=True))
    else:
        next_candidates = next_candidates.filter(barber=barber_item)
    next_customer = next_candidates.prefetch_related("services").order_by("created_at", "id").first()
    service_minutes = service_totals(current.services.all())[0] if current else 0
    elapsed_seconds = max(0, int((now - current.started_at).total_seconds())) if current and current.started_at else 0
    next_customer_wait = barber_wait_minutes(barber_item, before_entry=next_customer) if next_customer else 0
    return {
        **_base_context(request, "barber"),
        "barber": barber_item,
        "availability_label": _barber_display(barber_item, labels),
        "on_break": barber_item.availability == Barber.Availability.BREAK,
        "break_toggle_disabled": bool(current or called or not barber_item.is_on_duty),
        "current": current,
        "current_elapsed_seconds": elapsed_seconds,
        "current_service_minutes": service_minutes,
        "called": called,
        "next_customer": next_customer,
        "next_customer_wait": next_customer_wait,
        "last_updated": now,
        "notice": labels.get(f"barber_notice_{request.GET.get('notice', '')}", ""),
        "action_error": labels.get(f"barber_error_{request.GET.get('error', '')}", ""),
    }


def barber(request, name):
    barber_item = get_object_or_404(Barber, name=name)
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "start":
                start_service_for_barber(barber_item)
                notice = "started"
            elif action == "done":
                complete_service_for_barber(barber_item)
                notice = "done"
            elif action == "toggle-break":
                set_barber_break(barber_item, barber_item.availability != Barber.Availability.BREAK)
                notice = "on_break" if barber_item.availability != Barber.Availability.BREAK else "available"
            else:
                return redirect(f"{reverse('barber', kwargs={'name': name})}?error=invalid_action")
        except QueueRuleError as error:
            return redirect(f"{reverse('barber', kwargs={'name': name})}?error={error.args[0]}")
        return redirect(f"{reverse('barber', kwargs={'name': name})}?notice={notice}")
    return render(request, "barber.html", _barber_view_context(request, barber_item))


def barber_fragment(request, name):
    barber_item = get_object_or_404(Barber, name=name)
    return render(request, "barber_content.html", _barber_view_context(request, barber_item))


def _display_context(request):
    labels = ENGLISH
    now = timezone.now()
    barbers = list(Barber.objects.all())
    barber_lanes = []
    for barber_item in barbers:
        current = QueueEntry.objects.filter(
            barber=barber_item, status=QueueEntry.Status.IN_CHAIR
        ).prefetch_related("services").order_by("started_at", "id").first()
        called = QueueEntry.objects.filter(
            barber=barber_item, status=QueueEntry.Status.CALLED
        ).prefetch_related("services").order_by("called_at", "id").first()
        candidates = QueueEntry.objects.filter(status=QueueEntry.Status.WAITING)
        if barber_item.is_on_duty and barber_item.availability != Barber.Availability.BREAK:
            candidates = candidates.filter(Q(barber=barber_item) | Q(barber__isnull=True))
        else:
            candidates = candidates.filter(barber=barber_item)
        candidates = candidates.prefetch_related("services").order_by("created_at", "id")[:5]
        next_entries = list(candidates)
        for entry in next_entries:
            entry.estimated_wait = (
                barber_wait_minutes(barber_item, before_entry=entry)
                if barber_item.is_on_duty and barber_item.availability != Barber.Availability.BREAK
                else None
            )
        current_minutes = service_totals(current.services.all())[0] if current else 0
        current_elapsed = max(0, int((now - current.started_at).total_seconds() // 60)) if current and current.started_at else 0
        barber_lanes.append({
            "barber": barber_item,
            "availability_label": _barber_display(barber_item, labels),
            "on_break": barber_item.availability == Barber.Availability.BREAK,
            "current": current,
            "current_elapsed": current_elapsed,
            "current_remaining": max(0, current_minutes - current_elapsed),
            "called": called,
            "next_entries": next_entries,
        })
    waiting_count = QueueEntry.objects.filter(status=QueueEntry.Status.WAITING).count()
    return {
        **_base_context(request, "display"),
        "barber_lanes": barber_lanes,
        "waiting_count": waiting_count,
        "last_updated": now,
    }


def display(request):
    return render(request, "display.html", _display_context(request))


def display_fragment(request):
    return render(request, "display_content.html", _display_context(request))


def owner_settings(request):
    labels = ENGLISH
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "toggle-queue":
                settings = get_queue_settings()
                settings.online_joining_open = not settings.online_joining_open
                settings.save()
                notice = "queue_open" if settings.online_joining_open else "queue_closed"
            elif action == "toggle-service":
                service = get_object_or_404(Service, pk=request.POST.get("service_id"))
                service.is_active = not service.is_active
                service.save(update_fields=["is_active"])
                notice = "service_on" if service.is_active else "service_off"
            elif action == "toggle-barber-duty":
                barber_item = get_object_or_404(Barber, pk=request.POST.get("barber_id"))
                set_barber_on_duty(barber_item, not barber_item.is_on_duty)
                notice = "barber_on_duty" if not barber_item.is_on_duty else "barber_off_duty"
            else:
                return redirect(f"{reverse('owner-settings')}?error=invalid_action")
        except QueueRuleError as error:
            return redirect(f"{reverse('owner-settings')}?error={error.args[0]}")
        return redirect(f"{reverse('owner-settings')}?notice={notice}")

    today = timezone.localdate()
    completed_today = QueueEntry.objects.filter(
        status=QueueEntry.Status.DONE, completed_at__date=today
    )
    served_count = completed_today.count()
    wait_samples = list(
        completed_today.filter(started_at__isnull=False).values_list("created_at", "started_at")
    )
    average_wait = round(
        sum((started - created).total_seconds() / 60 for created, started in wait_samples)
        / len(wait_samples)
    ) if wait_samples else 0
    no_show_count = QueueEntry.objects.filter(
        status=QueueEntry.Status.NO_SHOW, called_at__date=today
    ).count()
    services = list(Service.objects.all())
    barber_cards = []
    for barber_item in Barber.objects.all():
        has_active_customer = QueueEntry.objects.filter(
            barber=barber_item,
            status__in=[QueueEntry.Status.CALLED, QueueEntry.Status.IN_CHAIR],
        ).exists()
        barber_cards.append({
            "barber": barber_item,
            "availability_label": _barber_display(barber_item, labels),
            "has_active_customer": has_active_customer,
        })
    queue_settings = get_queue_settings()
    context = _base_context(request, "settings")
    context.update({
        "services": services,
        "barber_cards": barber_cards,
        "queue_settings": queue_settings,
        "served_count": served_count,
        "average_wait": average_wait,
        "no_show_count": no_show_count,
        "today_date": today,
        "notice": labels.get(f"settings_notice_{request.GET.get('notice', '')}", ""),
        "action_error": labels.get(f"settings_error_{request.GET.get('error', '')}", ""),
    })
    return render(request, "owner_settings.html", context)


def home_summary(request):
    cards = []
    for barber_item in Barber.objects.all():
        cards.append({
            "id": barber_item.pk,
            "wait": barber_wait_minutes(barber_item),
            "available": barber_item.is_on_duty and barber_item.availability != Barber.Availability.BREAK,
        })
    waits = [item["wait"] for item in cards if item["available"]]
    waiting_count = QueueEntry.objects.filter(
        status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED]
    ).count()
    queue_settings = get_queue_settings()
    return JsonResponse({
        "waiting_count": waiting_count,
        "overall_wait": min(waits) if waits else None,
        "barbers": cards,
        "queue_open": queue_settings.online_joining_open,
        "active_service_ids": list(Service.objects.filter(is_active=True).values_list("pk", flat=True)),
    })
