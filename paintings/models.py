from django.db import models
from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
import secrets
from django.core.mail import send_mail

class Zakon_sbornik(models.Model):
    zakon_id = models.BigIntegerField(unique=True)  # уникальный идентификатор закона
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100, blank=True, null=True)
    original_link = models.URLField(blank=True, null=True)  # заглушка для ссылки
    date_added = models.DateField(auto_now_add=True)


class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=256)
    favorite_laws = models.ManyToManyField('Zakon_sbornik', blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_code = models.CharField(max_length=6, blank=True, null=True)
    code_created_at = models.DateTimeField(blank=True, null=True)
    is_authenticated=models.BooleanField(default=False)


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
class OTVET_REQUEST(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_question = models.TextField()
    answer = models.ForeignKey(OTVET, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accuracy = models.FloatField(default=0.0)  # <-- добавляем это поле

class ZakonView(models.Model):
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    zakon = models.ForeignKey('Zakon_sbornik', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
