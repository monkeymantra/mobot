# Generated by Django 3.0.4 on 2021-08-03 16:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0008_auto_20210729_2100'),
    ]

    operations = [
        migrations.AddField(
            model_name='sku',
            name='sort_order',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
