# Copyright (c) 2021 MobileCoin. All rights reserved.

# Generated by Django 3.0.4 on 2021-06-08 20:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0003_dropsession_bonus_coin_claimed'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bonuscoin',
            name='number_claimed',
        ),
    ]
