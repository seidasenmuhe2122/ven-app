from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0018_systemsetting_ui_buttons'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='ad_network',
            field=models.CharField(choices=[('admob', 'Google AdMob'), ('adsense', 'Google AdSense'), ('custom', 'Custom network')], default='admob', max_length=20),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='admob_app_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='interstitial_ad_unit_id',
            field=models.CharField(blank=True, default='ca-app-pub-3940256099942544/1033173712', max_length=255),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='rewarded_ad_unit_id',
            field=models.CharField(blank=True, default='ca-app-pub-3940256099942544/5224354917', max_length=255),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='ad_placements',
            field=models.JSONField(blank=True, default=dict, help_text='Optional placement limits, for example {"feed": 3, "article": 2}.'),
        ),
    ]