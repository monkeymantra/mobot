# Copyright (c) 2021 MobileCoin. All rights reserved.

# Generated by Django 3.0.4 on 2021-06-08 15:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('phone_number', models.TextField(primary_key=True, serialize=False)),
                ('received_sticker_pack', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Drop',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pre_drop_description', models.TextField()),
                ('advertisment_start_time', models.DateTimeField()),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('number_restriction', models.TextField()),
                ('timezone', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('phone_number', models.TextField()),
                ('description', models.TextField()),
                ('privacy_policy_url', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('direction', models.PositiveIntegerField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Customer')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Store')),
            ],
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('description', models.TextField(blank=True, default=None, null=True)),
                ('short_description', models.TextField(blank=True, default=None, null=True)),
                ('image_link', models.TextField(blank=True, default=None, null=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Store')),
            ],
        ),
        migrations.CreateModel(
            name='DropSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(default=0)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Customer')),
                ('drop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Drop')),
            ],
        ),
        migrations.AddField(
            model_name='drop',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Item'),
        ),
        migrations.AddField(
            model_name='drop',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Store'),
        ),
        migrations.CreateModel(
            name='CustomerStorePreferences',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allows_contact', models.BooleanField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Customer')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Store')),
            ],
        ),
    ]
