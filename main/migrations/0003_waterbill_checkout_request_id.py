# Generated by Django 4.1.3 on 2025-07-06 17:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_remove_client_first_name_remove_client_last_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='waterbill',
            name='checkout_request_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
