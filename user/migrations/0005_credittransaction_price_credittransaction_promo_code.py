# Generated by Django 5.1.7 on 2025-04-01 16:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0004_promocode'),
    ]

    operations = [
        migrations.AddField(
            model_name='credittransaction',
            name='price',
            field=models.DecimalField(decimal_places=2, default=2, help_text='Prix total de la transaction', max_digits=10, verbose_name='Prix'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='credittransaction',
            name='promo_code',
            field=models.ForeignKey(blank=True, help_text='Code promo appliqué à la transaction', null=True, on_delete=django.db.models.deletion.SET_NULL, to='user.promocode', verbose_name='Code promo'),
        ),
    ]
