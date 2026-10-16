from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0020_systemsetting_ad_networks_campaigns'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='logo',
            field=models.ImageField(blank=True, help_text='Optional application logo shown in the web header and mobile app.', null=True, upload_to='branding/'),
        ),
    ]