# Generated by Django 3.0.4 on 2021-05-18 19:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DropSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(default=0)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Customer')),
                ('drop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Drop')),
            ],
        ),
    ]