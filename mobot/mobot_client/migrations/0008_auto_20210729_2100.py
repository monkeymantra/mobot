# Generated by Django 3.0.4 on 2021-07-29 21:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0007_auto_20210611_1955'),
    ]

    operations = [
        migrations.AddField(
            model_name='drop',
            name='drop_type',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='dropsession',
            name='manual_override',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='item',
            name='price_in_pmob',
            field=models.PositiveIntegerField(blank=True, default=None, null=True),
        ),
        migrations.CreateModel(
            name='Sku',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.TextField()),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Item')),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('shipping_address', models.TextField(blank=True, default=None, null=True)),
                ('shipping_name', models.TextField(blank=True, default=None, null=True)),
                ('status', models.IntegerField(default=0)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Customer')),
                ('drop_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.DropSession')),
                ('sku', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Sku')),
            ],
        ),
    ]