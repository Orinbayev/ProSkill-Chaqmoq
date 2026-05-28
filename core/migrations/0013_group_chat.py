from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_game_balls_system'),
        ('education', '0056_enrollment_credit_balance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GroupChat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_chats', to='accounts.center')),
                ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='chat', to='education.group')),
            ],
            options={'verbose_name': 'Guruh Chat', 'verbose_name_plural': 'Guruh Chatlar'},
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('body', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='core.groupchat')),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages', to='accounts.center')),
                ('reply_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='core.chatmessage')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at'], 'verbose_name': 'Chat Xabar', 'verbose_name_plural': 'Chat Xabarlar'},
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['chat', 'created_at'], name='core_chatme_chat_id_idx'),
        ),
        migrations.CreateModel(
            name='ChatAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('file', models.FileField(blank=True, null=True, upload_to='chat/%Y/%m/')),
                ('link_url', models.URLField(blank=True)),
                ('att_type', models.CharField(choices=[('image', 'Rasm'), ('pdf', 'PDF'), ('file', 'Fayl'), ('link', 'Havola')], default='file', max_length=10)),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('file_size', models.PositiveIntegerField(default=0)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='core.chatmessage')),
            ],
            options={'verbose_name': 'Chat Fayl', 'verbose_name_plural': 'Chat Fayllar'},
        ),
    ]
