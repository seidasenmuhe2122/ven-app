from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0019_systemsetting_ad_network_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='ad_networks',
            field=models.JSONField(blank=True, default=list, help_text='Unlimited list of enabled ad networks and their placement IDs.'),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='ad_campaigns',
            field=models.JSONField(blank=True, default=list, help_text='Unlimited list of campaigns with network, placement, and targeting metadata.'),
        ),
    ]