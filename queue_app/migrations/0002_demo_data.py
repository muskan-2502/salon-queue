from django.db import migrations


def seed_demo_data(apps, schema_editor):
    Service = apps.get_model("queue_app", "Service")
    Barber = apps.get_model("queue_app", "Barber")
    QueueEntry = apps.get_model("queue_app", "QueueEntry")
    database = schema_editor.connection.alias

    services = {}
    for name, minutes, price, order in [
        ("Haircut", 30, 150, 1),
        ("Beard trim", 15, 80, 2),
        ("Hair spa", 45, 400, 3),
        ("Color touch-up", 60, 700, 4),
        ("Head massage", 20, 120, 5),
    ]:
        service, _ = Service.objects.using(database).get_or_create(
            name=name,
            defaults={"duration_minutes": minutes, "price_rupees": price, "display_order": order},
        )
        services[name] = service

    barbers = {}
    for name, availability, order in [
        ("Ravi", "busy", 1),
        ("Amit", "available", 2),
        ("Imran", "break", 3),
    ]:
        barber, _ = Barber.objects.using(database).get_or_create(
            name=name, defaults={"availability": availability, "display_order": order}
        )
        barbers[name] = barber

    examples = [
        ("Kunal Shah", "9990000001", "Ravi", ["Haircut"]),
        ("Rhea Mehta", "9990000002", None, ["Beard trim"]),
        ("Arjun Patel", "9990000003", "Amit", ["Hair spa"]),
        ("Dev Shah", "9990000004", None, ["Haircut"]),
        ("Nisha Rao", "9990000005", "Ravi", ["Beard trim"]),
        ("Sam Kapoor", "9990000006", "Amit", ["Haircut"]),
    ]
    for customer_name, phone, barber_name, selected_services in examples:
        entry, created = QueueEntry.objects.using(database).get_or_create(
            phone=phone,
            defaults={
                "customer_name": customer_name,
                "barber_id": barbers[barber_name].pk if barber_name else None,
                "status": "waiting",
            },
        )
        if created:
            entry.services.set([services[name].pk for name in selected_services])


class Migration(migrations.Migration):
    dependencies = [("queue_app", "0001_initial")]

    operations = [migrations.RunPython(seed_demo_data, migrations.RunPython.noop)]
