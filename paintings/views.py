from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import date
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from collections import defaultdict
from django.utils import timezone
from .models import Zakon_sbornik
from .models import User
from .forms import RegistrationForm, LoginForm, PasswordResetForm
from .forms import VerifyEmailForm
from .email_utils import send_verification_email
from django import forms
import random
from datetime import datetime, timedelta
import calendar
from .models import ZakonView
from django.db.models import Count
from .forms import DeleteAccountForm
from .forms import ForgotUsernameForm
from django.http import HttpResponse
from .models import OTVET_REQUEST
from .services import find_best_answer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from collections import defaultdict

def remove_from_favorites_profile(request, pk):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    zakon = get_object_or_404(Zakon_sbornik, pk=pk)

    user.favorite_laws.remove(zakon)

    # остаёмся на профиле
    return redirect('profile')

def add_to_favorites(request, pk, redirect_to='zakon_detail'):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    user = User.objects.get(id=user_id)
    zakon = get_object_or_404(Zakon_sbornik, pk=pk)

    user.favorite_laws.add(zakon)

    if redirect_to == 'profile':
        return redirect('profile', user.id)
    return redirect('zakon_detail', pk=pk)


def remove_from_favorites(request, pk, redirect_to='zakon_detail'):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    user = User.objects.get(id=user_id)
    zakon = get_object_or_404(Zakon_sbornik, pk=pk)

    user.favorite_laws.remove(zakon)

    if redirect_to == 'profile':
        return redirect('profile', user.id)
    return redirect('zakon_detail', pk=pk)

def logout_view(request):
    # Очищаем сессию
    request.session.flush()
    messages.success(request, "Вы успешно вышли из аккаунта!")
    return redirect('login')

def ui_views(request):
    return render(request, 'paintings/ui.html')

def index(request):
    latest_laws = Zakon_sbornik.objects.order_by('-date_added')[:3]
    return render(request, 'paintings/index.html', {'latest_laws': latest_laws})

def aiadvocat(request):
    return render(request, 'paintings/aiadvocat.html')


def proverka(request):
    return render(request, 'paintings/proverka.html')


def profile_view(request):

    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Сначала войдите в систему")
        return redirect('login')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Пользователь не найден")
        return redirect('login')

    # --- Сводная аналитика ---
    total_ai_requests = OTVET_REQUEST.objects.filter(user=user).count()
    total_zakon_views = ZakonView.objects.filter(user=user).count()

    last_ai = OTVET_REQUEST.objects.filter(user=user).order_by('-created_at').first()
    last_view = ZakonView.objects.filter(user=user).order_by('-viewed_at').first()

    last_ai_request = last_ai.created_at if last_ai else None
    last_zakon_view = last_view.viewed_at if last_view else None
    # --- после получения last_ai и last_view ---
    if last_ai:
        last_ai_request = {
            "datetime": last_ai.created_at,
            "question": last_ai.user_question,
            "answer": last_ai.answer
            }
    else:
        last_ai_request = None
    if last_view:
        last_zakon_view = {
            "datetime": last_view.viewed_at,
            "zakon_title": last_view.zakon.title,
            "zakon_id": last_view.zakon.id
            }
    else:
        last_zakon_view = None

    # любимая категория
    favorite_category = (
        ZakonView.objects.filter(user=user)
        .values('zakon__category')
        .annotate(count=Count('id'))
        .order_by('-count')
        .first()
    )
    favorite_category = favorite_category['zakon__category'] if favorite_category else None

    # --- структура по месяцам/неделям/дням ---
    # Русские названия дней недели
    weekdays_rus = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    monthly_stats = {}
    for month in range(1, 13):
        month_name = calendar.month_name[month]
        monthly_stats[month_name] = {
            "top_category": None,
            "ai_count": 0,
            "view_count": 0,
            "weeks": {}
        }

        days_in_month = calendar.monthrange(2026, month)[1]
        for day_num in range(1, days_in_month + 1):
            current_day = date(2026, month, day_num)
            week_num = current_day.isocalendar()[1]  # ISO неделя
            weekday_num = current_day.weekday()      # 0=понедельник
            weekday_name = weekdays_rus[weekday_num] # название дня недели

            # создаем неделю, если еще нет
            if week_num not in monthly_stats[month_name]["weeks"]:
                monthly_stats[month_name]["weeks"][week_num] = {
                    "top_category": None,
                    "ai_count": 0,
                    "view_count": 0,
                    "days": {}
                }

            # создаем день в неделе
            
            monthly_stats[month_name]["weeks"][week_num]["days"][current_day] = {
                "weekday_num": weekday_num,
                "weekday_name": weekday_name,
                "top_category": None,
                "ai_count": 0,
                "view_count": 0,
                "zakon_views": [],
                "ai_requests": []
            }

    views = ZakonView.objects.filter(user=user)
    ai_requests = OTVET_REQUEST.objects.filter(user=user)

    # --- просмотры ---
    for view in views:
        dt = view.viewed_at
        month_name = calendar.month_name[dt.month]
        week_num = dt.isocalendar()[1]
        day = dt.date()

        # создаем неделю и день, если нет
        if week_num not in monthly_stats[month_name]["weeks"]:
            monthly_stats[month_name]["weeks"][week_num] = {
                "top_category": None,
                "ai_count": 0,
                "view_count": 0,
                "days": {},
                
            }
        if day not in monthly_stats[month_name]["weeks"][week_num]["days"]:
            weekday_num = day.weekday()
            weekday_name = weekdays_rus[weekday_num]
            monthly_stats[month_name]["weeks"][week_num]["days"][day] = {
                "weekday_num": weekday_num,
                "weekday_name": weekday_name,
                "top_category": None,
                "ai_count": 0,
                "view_count": 0
            }

        monthly_stats[month_name]["view_count"] += 1
        monthly_stats[month_name]["weeks"][week_num]["view_count"] += 1
        monthly_stats[month_name]["weeks"][week_num]["days"][day]["view_count"]+= 1
        monthly_stats[month_name]["weeks"][week_num]["days"][day]["zakon_views"].append({
            "time": dt.strftime("%H:%M"),
            "zakon_title": view.zakon.title,
            "zakon_id": view.zakon.id
})

    # --- AI-запросы ---
    for req in ai_requests:
        dt = req.created_at
        month_name = calendar.month_name[dt.month]
        week_num = dt.isocalendar()[1]
        day = dt.date()

        if week_num not in monthly_stats[month_name]["weeks"]:
            monthly_stats[month_name]["weeks"][week_num] = {
                "top_category": None,
                "ai_count": 0,
                "view_count": 0,
                "days": {}
            }
        if day not in monthly_stats[month_name]["weeks"][week_num]["days"]:
            weekday_num = day.weekday()
            weekday_name = weekdays_rus[weekday_num]
            monthly_stats[month_name]["weeks"][week_num]["days"][day] = {
                "weekday_num": weekday_num,
                "weekday_name": weekday_name,
                "top_category": None,
                "ai_count": 0,
                "view_count": 0
            }

        monthly_stats[month_name]["ai_count"] += 1
        monthly_stats[month_name]["weeks"][week_num]["ai_count"] += 1
        monthly_stats[month_name]["weeks"][week_num]["days"][day]["ai_count"] += 1
        monthly_stats[month_name]["weeks"][week_num]["days"][day]["ai_requests"].append({
            "time": dt.strftime("%H:%M"),
            "question": req.user_question,
            "answer": req.answer.answer if req.answer else None,
})

    # --- функция для топ-категории ---
    def get_top_category(qs):
        data = (
            qs.values('zakon__category')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        return data['zakon__category'] if data else None

    # --- подсчет топ-категорий ---
    for month_name in monthly_stats:
        month_index = list(calendar.month_name).index(month_name)
        monthly_views = views.filter(viewed_at__month=month_index)
        monthly_stats[month_name]["top_category"] = get_top_category(monthly_views)

        for week_num in monthly_stats[month_name]["weeks"]:
            weekly_views = views.filter(viewed_at__week=week_num)
            monthly_stats[month_name]["weeks"][week_num]["top_category"] = get_top_category(weekly_views)

            for day in monthly_stats[month_name]["weeks"][week_num]["days"]:
                day_views = views.filter(viewed_at__date=day)
                monthly_stats[month_name]["weeks"][week_num]["days"][day]["top_category"] = get_top_category(day_views)

    # --- convert defaultdict -> dict ---
    for month_name in monthly_stats:
        monthly_stats[month_name]["weeks"] = dict(monthly_stats[month_name]["weeks"])
        for week_num in monthly_stats[month_name]["weeks"]:
            monthly_stats[month_name]["weeks"][week_num]["days"] = dict(
                monthly_stats[month_name]["weeks"][week_num]["days"]
            )

    monthly_stats = dict(monthly_stats)
    weekdays = [0,1,2,3,4,5,6] 

    context = {
        "user": user,
        "monthly_stats": monthly_stats,
        "total_ai_requests": total_ai_requests,
        "total_zakon_views": total_zakon_views,
        "last_ai_request": last_ai_request,
        "last_zakon_view": last_zakon_view,
        "favorite_category": favorite_category,
        "weekdays": weekdays
    }
    for month in monthly_stats.values():
        for week in month["weeks"].values():
            for day in week["days"].values():
                day["ai_requests"] = json.dumps(day["ai_requests"])
                day["zakon_views"] = json.dumps(day["zakon_views"])

    return render(request, "paintings/profile.html", context)

# Вход
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(username=form.cleaned_data['username'])
                if user.check_password(form.cleaned_data['password']):
                    request.session['user_id'] = user.id
                    messages.success(request, f"Добро пожаловать, {user.username}!")
                    return redirect('profile')
                else:
                    messages.error(request, "Неверный пароль")
            except User.DoesNotExist:
                messages.error(request, "Пользователь не найден")
    else:
        form = LoginForm()
    return render(request, 'paintings/login.html', {'form': form})



def password_reset_view(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(email=form.cleaned_data['email'])
                email=form.cleaned_data['email']
                code = user.generate_code()
                send_verification_email(
                    email,
                    "Сброс пароля",
                    f"Ваш код для сброса пароля: {code}"
                )
                messages.success(request, "Код для сброса пароля отправлен на email!")
                return redirect('password_reset_confirm', user_id=user.id)
            except User.DoesNotExist:
                messages.error(request, "Пользователь с таким email не найден")
    else:
        form = PasswordResetForm()
    return render(request, 'paintings/password_reset.html', {'form': form})



class SetNewPasswordForm(forms.Form):
    code = forms.CharField(max_length=6)
    new_password = forms.CharField(widget=forms.PasswordInput)

def password_reset_confirm_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            new_password = form.cleaned_data['new_password']
            if user.email_verification_code == code and user.code_is_valid():
                user.set_password(new_password)
                user.email_verification_code = None
                user.code_created_at = None
                user.save()
                messages.success(request, "Пароль успешно изменен!")
                return redirect('login')
            else:
                messages.error(request, "Неверный или просроченный код")
    else:
        form = SetNewPasswordForm()
    return render(request, 'paintings/password_reset_confirm.html', {'form': form})


def zakons(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    zakon_id_raw = request.GET.get('zakon_id', '').strip()

    zakons_list = Zakon_sbornik.objects.all()

    # Получаем все уникальные категории для подсказок
    all_categories = Zakon_sbornik.objects.values_list('category', flat=True).distinct()

    # ✅ Проверка zakon_id: только цифры
    if zakon_id_raw:
        if zakon_id_raw.isdigit():
            # ищем частично совпадающие ID
            zakons_list = zakons_list.filter(zakon_id__icontains=zakon_id_raw)
        else:
            messages.error(request, "ZAKONID должен содержать только цифры!")
            zakon_id_raw = ''  # сброс для корректной работы
        
    
    # ✅ Фильтр по категории — просто icontains
    if category:
        zakons_list = zakons_list.filter(category__icontains=category)
        
    # ✅ Поиск по q в title и description
    if query:
        zakons_list = zakons_list.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )
     # Получаем избранные законы пользователя (если авторизован)
    user_id = request.session.get('user_id')
    favorite_laws = []
    if user_id:
        user = User.objects.get(id=user_id)
        favorite_laws = user.favorite_laws.all()
    favorite_ids = []
    if user_id:
        user = User.objects.get(id=user_id)
        favorite_ids = list(user.favorite_laws.values_list('id', flat=True))

    return render(request, 'paintings/zakons.html', {
        'zakons_list': zakons_list,
        'query': query,
        'category': category,
        'zakon_id': zakon_id_raw,
        'favorite_laws': favorite_laws,
        'all_categories': all_categories,
        'favorite_ids': favorite_ids,
    })


def zakon_detail(request, pk):
    zakon = get_object_or_404(Zakon_sbornik, pk=pk)

    user_id = request.session.get('user_id')
    is_favorite = False

    if user_id:
        user = User.objects.get(id=user_id)
        is_favorite = user.favorite_laws.filter(pk=zakon.pk).exists()
        # Создаем запись о просмотре только для авторизованных
        ZakonView.objects.create(user=user, zakon=zakon)

    return render(request, 'paintings/zakon_detail.html', {
        'zakon': zakon,
        'is_favorite': is_favorite
    })

def registration_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # Проверка уникальности
            if User.objects.filter(username=username).exists():
                messages.error(request, "Пользователь с таким username уже существует!")
                return render(request, 'paintings/registration.html', {'form': form})

            if User.objects.filter(email=email).exists():
                messages.error(request, "Пользователь с таким email уже существует!")
                return render(request, 'paintings/registration.html', {'form': form})

            # Генерация кода
            code = str(random.randint(100000, 999999))

            request.session['registration_data'] = {
                'username': username,
                'email': email,
                'password': password
            }
            request.session['email_verification_code'] = code
            request.session['code_created_at'] = timezone.now().isoformat()

            # Отправка письма (строка email!)
            send_verification_email(
                email,
                "Подтверждение email",
                f"Ваш код подтверждения: {code}"
            )

            messages.success(request, "Код подтверждения отправлен на email!")
            return redirect('verify_email')
    else:
        form = RegistrationForm()

    return render(request, 'paintings/registration.html', {'form': form})
def verify_email_view(request):
    if request.method == 'POST':
        form = VerifyEmailForm(request.POST)

        if form.is_valid():
            code_entered = form.cleaned_data['code']
            session_code = request.session.get('email_verification_code')

            if session_code and code_entered == session_code:
                data = request.session.get('registration_data')

                if data:
                    user = User.objects.create(
                        username=data['username'],
                        email=data['email'],
                        is_email_verified=True
                    )
                    user.set_password(data['password'])
                    user.save()

                    # Очистка сессии
                    request.session.flush()

                    messages.success(request, "Email подтверждён! Теперь можете войти.")
                    return redirect('login')

            messages.error(request, "Неверный код подтверждения.")
    else:
        form = VerifyEmailForm()

    return render(request, 'paintings/verify_email.html', {'form': form})

def delete_account_view(request, user_id):
    user = get_object_or_404(User, id=user_id)


    show_code_form = False
    form = None

    if request.method == "POST":
        if "send_code" in request.POST:
            code = user.generate_code()
            try:
                send_verification_email(
                    user.email,
                    "Удаление аккаунта",
                    f"Ваш код для удаления аккаунта: {code}\n\nДействует 10 минут."
                )
                messages.info(request, "Код отправлен на вашу почту.")
                show_code_form = True
                form = DeleteAccountForm()  # показываем форму для ввода кода
            except Exception as e:
                messages.error(request, "Не удалось отправить письмо. Попробуйте позже.")
                print("Ошибка отправки email:", e)

        elif "confirm_delete" in request.POST:
            form = DeleteAccountForm(request.POST)
            show_code_form = True
            if form.is_valid():
                code_entered = form.cleaned_data["code"].strip()
                if code_entered == user.email_verification_code and user.code_is_valid():
                    try:
                        user.delete()
                        messages.success(request, "Аккаунт успешно удалён.")
                        return redirect("index")
                    except Exception as e:
                        messages.error(request, "Ошибка при удалении аккаунта.")
                        print("Ошибка удаления:", e)
                else:
                    messages.error(request, "Неверный или просроченный код.")
            else:
                messages.error(request, "Введите корректный код.")

    return render(request, 'paintings/delete_account.html', {
        "user": user,
        "show_code_form": show_code_form,
        "form": form,
    })

def forgot_username_view(request):
    if request.method == "POST":
        form = ForgotUsernameForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]

            try:
                user = User.objects.get(email=email)

                send_verification_email(
                    email,
                    "Ваш логин",
                    f"Ваш логин для входа: {user.username}"
                )

                messages.success(request, "Логин отправлен на ваш email!")

            except User.DoesNotExist:
                messages.error(request, "Пользователь с таким email не найден")

    else:
        form = ForgotUsernameForm()

    return render(request, "paintings/forgot_username.html", {"form": form})


#AIADVOCAT
@csrf_exempt
def ai_advocate(request):
    if request.method == "POST":
         
        try:
            data = json.loads(request.body)
        except:
            data = {}
        question = data.get("question", "")

        answer_obj, accuracy = find_best_answer(question)  # <-- получаем точность

        # сохраняем историю
        user_id = request.session.get('user_id')
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user = None

# сохраняем историю запроса
            OTVET_REQUEST.objects.create(
                user=user,                  # обязательно ключевое слово
                user_question=question,
                answer=answer_obj,           # может быть None
                accuracy=accuracy
)
        # формируем ответ
        if answer_obj:
            laws = [{"title": law.title, "link": law.original_link, "internal_link": reverse('zakon_detail', args=[law.pk])} for law in answer_obj.laws.all()]
            answer_text = answer_obj.answer
        else:
            laws = []
            answer_text = "Ответ не найден."

        return JsonResponse({"answer": answer_text, "laws": laws, "accuracy": accuracy})
    
     
    # GET-запрос — рендер страницы с историей
    history = []
    user_id = request.session.get('user_id')
    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    if user:
        requests = OTVET_REQUEST.objects.filter(user=user).order_by('created_at')
        for r in requests:
            # Формируем законы с внутренними и внешними ссылками
            laws = []
            if r.answer:  # если есть ответ
                for law in r.answer.laws.all():
                    laws.append({
                        "title": law.title,
                        "external_link": law.original_link,
                        "internal_link": reverse('zakon_detail', args=[law.pk])
                   })
            history.append({
                "question": r.user_question,
                "answer": r.answer.answer if r.answer else "Ответ не найден",
                "accuracy": r.accuracy,
                "time": r.created_at,
                "laws": laws
            })

    return render(request, "paintings/aiadvocat.html", {"history": history, "user_authenticated": bool(user)})










# 🔹 Получение топ-3 категорий просмотров
def get_top_viewed_categories():
    qs = ZakonView.objects.values('zakon__category') \
        .annotate(count=Count('id')).order_by('-count')[:3]
    return [(x['zakon__category'] or 'Без категории', x['count']) for x in qs]

# 🔹 Получение топ-3 категорий AI-запросов
def get_top_ai_categories():
    qs = OTVET_REQUEST.objects.filter(answer__isnull=False) \
        .values('answer__laws__category') \
        .annotate(count=Count('id')).order_by('-count')[:3]
    return [(x['answer__laws__category'] or 'Без категории', x['count']) for x in qs]

# 🔹 AI-запросы по календарным месяцам
def get_monthly_ai_stats(year):
    stats = {}
    tz = timezone.get_current_timezone()
    for month in range(1, 13):
        start_date = datetime(year, month, 1, tzinfo=tz)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=tz)
        count = OTVET_REQUEST.objects.filter(created_at__gte=start_date, created_at__lte=end_date).count()
        stats[calendar.month_name[month]] = count
    return stats

# 🔹 AI-запросы по календарным неделям (понедельник-воскресенье)
def get_weekly_ai_stats(year):
    tz = timezone.get_current_timezone()
    stats = {}
    date = datetime(year, 1, 1, tzinfo=tz)
    date -= timedelta(days=date.weekday())  # сдвигаем к понедельнику

    while date.year <= year:
        week_start = date
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        count = OTVET_REQUEST.objects.filter(created_at__gte=week_start, created_at__lte=week_end).count()
        stats[f"{week_start.date()} - {week_end.date()}"] = count
        date = week_start + timedelta(days=7)
    return stats

# 🔹 Главная аналитика view
def analytics_view(request):
    current_year = timezone.now().year
    monthly_stats = get_monthly_ai_stats(current_year)
    weekly_stats = get_weekly_ai_stats(current_year)
    top_viewed_categories = get_top_viewed_categories()
    top_ai_categories = get_top_ai_categories()

    return render(request, "paintings/analytics.html", {
        "monthly_stats": monthly_stats,
        "weekly_stats": weekly_stats,
        "top_viewed_categories": top_viewed_categories,
        "top_ai_categories": top_ai_categories,
    })
