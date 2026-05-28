from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_game_questions'),
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='balls_earned',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='GameBallsConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min_balls_to_convert', models.PositiveSmallIntegerField(default=100, help_text='Minimal ball miqdori')),
                ('chaqmoq_per_conversion', models.PositiveSmallIntegerField(default=5, help_text='Bir konvertatsiyada beriladi')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('center', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='game_balls_config', to='accounts.center')),
            ],
            options={'verbose_name': "O'yin Balli Sozlamasi", 'verbose_name_plural': "O'yin Balli Sozlamalari"},
        ),
        migrations.CreateModel(
            name='StudentBallsWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_balls', models.PositiveIntegerField(default=0)),
                ('lifetime_balls', models.PositiveIntegerField(default=0)),
                ('last_ball_at', models.DateTimeField(blank=True, null=True)),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_balls_wallets', to='accounts.center')),
                ('student', models.ForeignKey(limit_choices_to={'role': 'student'}, on_delete=django.db.models.deletion.CASCADE, related_name='balls_wallet', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': "O'quvchi Ball Hisobchasi", 'verbose_name_plural': "O'quvchi Ball Hisobchalari"},
        ),
        migrations.AddConstraint(
            model_name='studentballswallet',
            constraint=models.UniqueConstraint(fields=['center', 'student'], name='unique_student_balls_wallet'),
        ),
        migrations.AddIndex(
            model_name='studentballswallet',
            index=models.Index(fields=['center', 'student'], name='core_studen_center__balls_idx'),
        ),
        migrations.CreateModel(
            name='GameBallsConversionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balls_spent', models.PositiveSmallIntegerField()),
                ('chaqmoq_earned', models.PositiveSmallIntegerField()),
                ('converted_at', models.DateTimeField(auto_now_add=True)),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balls_conversions', to='accounts.center')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balls_conversions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-converted_at'], 'verbose_name': 'Ball Konvertatsiyasi', 'verbose_name_plural': 'Ball Konvertatsiyalari'},
        ),
    ]
