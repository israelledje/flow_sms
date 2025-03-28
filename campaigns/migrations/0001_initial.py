# Generated by Django 5.1.7 on 2025-03-24 14:17

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(max_length=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('message_content', models.TextField()),
                ('status', models.CharField(choices=[('draft', 'Brouillon'), ('scheduled', 'Programmé'), ('sending', "En cours d'envoi"), ('sent', 'Envoyé'), ('failed', 'Échoué')], default='draft', max_length=20)),
                ('scheduled_date', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_rich_sms', models.BooleanField(default=False)),
                ('rich_content', models.JSONField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('sent', 'Envoyé'), ('delivered', 'Livré'), ('failed', 'Échoué')], default='pending', max_length=20)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('is_rich_sms', models.BooleanField(default=False)),
                ('rich_content', models.JSONField(blank=True, null=True)),
                ('message_id', models.CharField(blank=True, max_length=100, null=True)),
                ('error_description', models.TextField(blank=True, null=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='campaigns.campaign')),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='campaigns.contact')),
            ],
        ),
        migrations.AddField(
            model_name='campaign',
            name='contacts',
            field=models.ManyToManyField(through='campaigns.Message', to='campaigns.contact'),
        ),
        migrations.CreateModel(
            name='SenderId',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=11)),
                ('status', models.CharField(choices=[('pending', 'En attente de validation'), ('approved', 'Approuvé'), ('rejected', 'Rejeté')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='message',
            name='sender',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='campaigns.senderid'),
        ),
        migrations.AddField(
            model_name='campaign',
            name='sender',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='campaigns.senderid'),
        ),
    ]
