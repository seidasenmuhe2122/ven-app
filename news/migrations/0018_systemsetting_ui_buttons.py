from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0017_article_summary_background_color_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='ui_buttons',
            field=models.JSONField(blank=True, default=dict, help_text='JSON button labels and URLs for the public UI. Leave empty to use defaults.'),
        ),
    ]