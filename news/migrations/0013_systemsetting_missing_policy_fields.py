from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0012_dashboardwidgetconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='about_url',
            field=models.URLField(blank=True, default='https://example.com/about'),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='contact_url',
            field=models.URLField(blank=True, default='https://example.com/contact'),
        ),
    ]
