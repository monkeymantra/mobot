# Copyright (c) 2021 MobileCoin. All rights reserved.

# Generated by Django 3.0.4 on 2021-06-11 19:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0006_auto_20210611_1954'),
    ]

    operations = [
        migrations.RenameField(
            model_name='drop',
            old_name='conversion_rate',
            new_name='conversion_rate_mob_to_currency',
        ),
    ]
