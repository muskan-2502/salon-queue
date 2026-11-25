from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def add_demo_current_customer(apps, schema_editor):
    Barber = apps.get_model("queue_app", "Barber")
    QueueEntry = apps.get_model("queue_app", "QueueEntry")
    Service = apps.get_model("queue_app", "Service")
    database = schema_editor.connection.alias
    barber = Barber.objects.using(database).get(name="Ravi")
    haircut = Service.objects.using(database).get(name="Haircut")
    entry, created = QueueEntry.objects.using(database).get_or_create(
        phone="9990000007",
        defaults={
            "customer_name": "Mohan Das",
            "barber_id": barber.pk,
            "status": "in_chair",
        },
    )
    if created:
        now = timezone.now()
        QueueEntry.objects.using(database).filter(pk=entry.pk).update(
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(minutes=12),
        )
        entry.services.add(haircut)


class Migration(migrations.Migration):
    dependencies = [("queue_app", "0003_queueentry_called_at_queueentry_started_at")]

    operations = [migrations.RunPython(add_demo_current_customer, migrations.RunPython.noop)]
