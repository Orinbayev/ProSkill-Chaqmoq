from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_group_chat'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatPresence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('chat', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='presences',
                    to='core.groupchat',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_presences',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Chat Faollik',
                'verbose_name_plural': 'Chat Faolliklar',
            },
        ),
        migrations.AddConstraint(
            model_name='chatpresence',
            constraint=models.UniqueConstraint(
                fields=['chat', 'user'],
                name='core_chatpresence_unique_chat_user',
            ),
        ),
        migrations.AddIndex(
            model_name='chatpresence',
            index=models.Index(fields=['chat', 'last_seen'], name='core_chatp_chat_id_ls_idx'),
        ),
        migrations.CreateModel(
            name='ChatMessageRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reads',
                    to='core.chatmessage',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='message_reads',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': "Xabar O'qilishi",
                'verbose_name_plural': "Xabar O'qilishlari",
            },
        ),
        migrations.AddConstraint(
            model_name='chatmessageread',
            constraint=models.UniqueConstraint(
                fields=['message', 'user'],
                name='core_chatmsgread_unique_message_user',
            ),
        ),
        migrations.AddIndex(
            model_name='chatmessageread',
            index=models.Index(fields=['message', 'user'], name='core_chatmr_msg_id_usr_idx'),
        ),
    ]
