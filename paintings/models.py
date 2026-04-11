from django.db import models
from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
import secrets
from django.core.mail import send_mail
from django.core.validators import MinValueValidator, MaxValueValidator

class Zakon_sbornik(models.Model):
    zakon_id = models.BigIntegerField(unique=True, null=True, blank=True)  # уникальный идентификатор закона
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100, blank=True, null=True)
    original_link = models.URLField(blank=True, null=True)  # заглушка для ссылки
    date_added = models.DateField(auto_now_add=True)
    def __str__(self):
        return f"{self.title} (ID: {self.zakon_id})"

class User(models.Model):
    SUBSCRIPTION_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("pro", "Pro"),
    ]
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=256)
    favorite_laws = models.ManyToManyField('Zakon_sbornik', blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_code = models.CharField(max_length=6, blank=True, null=True)
    code_created_at = models.DateTimeField(blank=True, null=True)
    is_authenticated=models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
        # UI настройки
    theme = models.CharField(max_length=10, default="dark")   # dark / light
    font_size = models.IntegerField(default=100)              # проценты
    tutorial_done = models.BooleanField(default=False)  # 👈 вот это
    # 👇 подписка пользователя
    subscription_level = models.CharField(
        max_length=10,
        choices=SUBSCRIPTION_CHOICES,
        default="free"
    )

    # 👇 является ли адвокатом
    is_lawyer = models.BooleanField(default=False)

    def get_lawyer_limit(self):
        limits = {
            "free": 1,
            "basic": 2,
            "pro": 5,
        }
        return limits.get(self.subscription_level, 1)


    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    def generate_code(self):
        import secrets
        code = str(secrets.randbelow(900000) + 100000)
        self.email_verification_code = code
        self.code_created_at = timezone.now()
        self.save()
        return code
    @staticmethod
    def generate_code_static():
        code = str(secrets.randbelow(900000) + 100000)
        return code
    def code_is_valid(self):
        if self.code_created_at is None:
            return False
        return timezone.now() < self.code_created_at + timedelta(minutes=10)  # срок действия 10 минут
    def delete_account_request(self):
        """
        Генерирует код удаления аккаунта и отправляет его на email.
        Код не хранится в базе, а используется для подтверждения пользователем.
        Возвращает сгенерированный код для тестов или логики отправки.
        """
        # Генерация 6-значного кода
        codef = str(secrets.randbelow(900000) + 100000)
        created_at = timezone.now()  # Время генерации кода

        # Отправка кода на email
        send_mail(
            subject='Подтверждение удаления аккаунта',
            message=f'Ваш код для удаления аккаунта: {codef}\nОн действителен 10 минут.',
            from_email='no-reply@example.com',
            recipient_list=[self.email],
            fail_silently=False
        )

        # Возвращаем код и время создания для проверки во view (не сохраняем в модели)
        return {"code": codef, "created_at": created_at}

    @staticmethod
    def confirm_delete_account(user, code_entered, code_generated, code_created_at):
        """
        Проверяет введенный код и удаляет аккаунт, если всё верно.
        """
        # Проверка срока действия кода (10 минут)
        if timezone.now() > code_created_at + timedelta(minutes=10):
            return False, "Срок действия кода истёк."

        # Проверка совпадения кода
        if code_entered != code_generated:
            return False, "Неверный код."

        # Удаление аккаунта
        user.favorite_laws.clear()  # Очистка M2M связей
        user.delete()
        return True, "Аккаунт успешно удалён."
    



#АДВОКАТ
class OTVET(models.Model):
    keywords = models.TextField()  # ключевые слова через запятую
    answer = models.TextField()  # текст ответа
    laws = models.ManyToManyField(Zakon_sbornik, blank=True)  # связанные законы
    def __str__(self):
        return f"{self.keywords[:30]}"
class OTVET_REQUEST(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_question = models.TextField()
    answer = models.ForeignKey(OTVET, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accuracy = models.FloatField(default=0.0)  # <-- добавляем это поле
    rating = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Оценка ответа от 0 до 5"
    )

class ZakonView(models.Model):
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    zakon = models.ForeignKey('Zakon_sbornik', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)



class Advokat(models.Model):
    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
    ]

    # Основные данные
    first_name = models.CharField("Имя", max_length=50)
    last_name = models.CharField("Фамилия", max_length=50)
    age = models.PositiveIntegerField("Возраст")
    gender = models.CharField("Пол", max_length=1, choices=GENDER_CHOICES)
    experience = models.PositiveIntegerField("Стаж работы (лет)")
    specialty = models.CharField("Специальность", max_length=100)  # юрист по недвижимости и т.д.

    # Связь с текущим клиентом (one-to-one)
    current_client = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Кем занят (клиент)"
    )

    is_busy = models.BooleanField("Занят", default=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.specialty})"
    




class LawyerProfile(models.Model):

    LEVEL_CHOICES = [
        ("junior", "Junior"),
        ("middle", "Middle"),
        ("senior", "Senior"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="lawyer_profile"
    )

    experience = models.PositiveIntegerField(
        verbose_name="Стаж работы"
    )

    specialty = models.CharField(
        max_length=100,
        verbose_name="Специализация"
    )

    level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
        default="junior"
    )

    def get_client_limit(self):
        limits = {
            "junior": 2,
            "middle": 5,
            "senior": 10,
        }
        return limits.get(self.level, 2)

    def __str__(self):
        return f"Адвокат: {self.user}"
    



class UserLawyer(models.Model):

    STATUS_CHOICES = [
        ("active", "Активный"),
        ("expired", "Истёк"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="client_lawyers"
    )

    lawyer = models.ForeignKey(
        LawyerProfile,
        on_delete=models.CASCADE,
        related_name="lawyer_clients"
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active"
    )

    def save(self, *args, **kwargs):

        # при создании ставим срок 30 дней
        if not self.expires_at:
            self.expires_at = (
                timezone.now() + timedelta(days=30)
            )

        super().save(*args, **kwargs)

    def is_expired(self):

        if timezone.now() > self.expires_at:
            self.status = "expired"
            self.save()

            return True

        return False
    

class Message(models.Model):
    sender = models.ForeignKey('User', on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey('User', on_delete=models.CASCADE, related_name='received_messages')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    law = models.ForeignKey('Zakon_sbornik', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f'{self.sender} → {self.receiver}: {self.text[:20]}'