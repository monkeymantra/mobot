# Copyright (c) 2021 MobileCoin. All rights reserved.

# Generated by Django 3.0.4 on 2021-06-08 20:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0002_auto_20210608_1945'),
    ]

    operations = [
        migrations.AddField(
            model_name='dropsession',
            name='bonus_coin_claimed',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='mobot_client.BonusCoin'),
        ),
    ]
