from django.shortcuts import render, redirect
from django.db.models import Count, Q, OuterRef, Subquery
from django.utils import timezone
from datetime import timedelta
from .models import OTVET, OTVET_REQUEST
from django.contrib import messages
from datetime import date
from django.urls import reverse

from django.db import transaction

from django.shortcuts import get_object_or_404
from django.db.models import Q
from collections import defaultdict
from django.utils import timezone
from .models import Zakon_sbornik
from .models import LawyerProfile
from .models import UserLawyer
from .models import User
from .forms import RegistrationForm, LoginForm, PasswordResetForm
from .forms import VerifyEmailForm
from .email_utils import send_verification_email
from django import forms
import random
from datetime import datetime, timedelta
import calendar
from datetime import date
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
from .models import Zakon_sbornik, OTVET
from .forms import ZakonForm, OtvetForm
from .models import Advokat
from django.shortcuts import redirect
















from .models import User, LawyerProfile, UserLawyer





def lawyers_and_users(request):
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "Сначала войдите в систему, что бы получить доступ к адвокатам")
        return redirect('login')

    user = User.objects.get(id=user_id)


    lawyers = LawyerProfile.objects.select_related("user")


    # общие параметры
    query = request.GET.get("q", "")
    specialty = request.GET.get("specialty", "")
    availability = request.GET.get("availability", "")
    subscription = request.GET.get("subscription", "")
    sort = request.GET.get("sort", "")
    
    context = {
        "query": query,
        "sort": sort,
    }

    # =========================
    # 👤 ЕСЛИ ЭТО ОБЫЧНЫЙ ПОЛЬЗОВАТЕЛЬ
    # =========================
    if not user.is_lawyer:

        lawyers = LawyerProfile.objects.select_related("user")

        # 🔍 поиск по ФИО
        if query:
            words = query.split()
            q_objects = Q()

            for word in words:
                q_objects &= Q(user__username__icontains=word)

            lawyers = lawyers.filter(q_objects)

        # 🔍 фильтр по специализации
        if specialty:
            lawyers = lawyers.filter(
                specialty__icontains=specialty
            )

        lawyers_data = []

        for lawyer in lawyers:

            active_clients = UserLawyer.objects.filter(
                lawyer=lawyer,
                status="active"
            ).count()

            limit = lawyer.get_client_limit()
            is_full = active_clients >= limit

            # 🔍 фильтр по занятости
            if availability == "free" and is_full:
                continue
            if availability == "busy" and not is_full:
                continue

            is_my_lawyer = UserLawyer.objects.filter(
                user=user,
                lawyer=lawyer,
                status="active"
            ).exists()

            lawyers_data.append({
                "lawyer": lawyer,
                "active_clients": active_clients,
                "limit": limit,
                "is_full": is_full,
                "is_my_lawyer": is_my_lawyer,
            })

        context["lawyers"] = lawyers_data
        context["mode"] = "lawyers"

    # =========================
    # ⚖️ ЕСЛИ ЭТО АДВОКАТ
    # =========================
    else:

        users = User.objects.filter(
        client_lawyers__lawyer__user=user,
        client_lawyers__status="active"
        ).distinct()

        # 🔍 поиск по ФИО
        if query:
            words = query.split()
            q_objects = Q()

            for word in words:
                q_objects &= Q(username__icontains=word)

            users = users.filter(q_objects)

        # 🔍 фильтр по подписке
        if subscription:
            users = users.filter(
                subscription_level=subscription
            )

        # 🔽 сортировка (если нужна)
        if sort == "subscription":
            users = users.order_by("-subscription_level")

        context["users"] = users
        context["mode"] = "users"
        context["user"] = user

    return render(request, "paintings/lawyers_and_users.html", context)

def profile_lawyer(request, username):
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "Сначала войдите в систему")
        return redirect('login')

    current_user = User.objects.get(id=user_id)

    # только для обычных пользователей
    if current_user.is_lawyer:
        return redirect('lawyers_and_users')

    lawyer_user = get_object_or_404(User, username=username, is_lawyer=True)
    lawyer = lawyer_user.lawyer_profile

    # считаем клиентов
    active_clients = UserLawyer.objects.filter(
        lawyer=lawyer,
        status="active"
    ).count()
# сколько у пользователя уже адвокатов
    my_lawyers_count = UserLawyer.objects.filter(
        user=current_user,
        status="active"
    ).count()

    user_limit = current_user.get_lawyer_limit()

    is_limit_reached = my_lawyers_count >= user_limit
    limit = lawyer.get_client_limit()
    is_full = active_clients >= limit

    # уже есть связь?
    relation = UserLawyer.objects.filter(
        user=current_user,
        lawyer=lawyer,
        status="active"
    ).first()

    # 🔥 если нажали "связаться"
    if request.method == "POST":

            # уже есть → чат
        if relation:
            return redirect('chat', lawyer_user.username)

    # 🚫 лимит пользователя
        if is_limit_reached:
            context = {
                "lawyer": lawyer,
                "active_clients": active_clients,
                "limit": limit,
                "is_full": is_full,
                "is_my_lawyer": bool(relation),
                "is_limit_reached": True,
                "user": current_user,
                "error": "Вы достигли лимита адвокатов"
            }
            return render(request, "paintings/profile_lawyer.html", context)

        # 🚫 у адвоката нет мест
        if is_full:
            context = {
                "lawyer": lawyer,
                "active_clients": active_clients,
                "limit": limit,
                "is_full": is_full,
                "is_my_lawyer": bool(relation),
                "is_limit_reached": is_limit_reached,
                "user": current_user,
                "error": "У адвоката нет свободных мест"
            }
            return render(request, "paintings/profile_lawyer.html", context)

        # ✅ ВСЁ ОК — создаём связь
        UserLawyer.objects.create(
            user=current_user,
            lawyer=lawyer
        )

        return redirect('chat', lawyer_user.username)

    context = {
        "lawyer": lawyer,
        "active_clients": active_clients,
        "limit": limit,
        "is_full": is_full,
        "is_my_lawyer": bool(relation),
        "user": current_user,
        "is_limit_reached": is_limit_reached,
    }

    return render(request, "paintings/profile_lawyer.html", context)
from .models import User, Message, UserLawyer, Zakon_sbornik


def chat(request, username):
    user_id = request.session.get('user_id')
    user = None

    if user_id:
        user = User.objects.get(id=user_id)
    if not user_id:
        messages.error(request, "Сначала войдите в систему")
        return redirect('login')

    current_user = User.objects.get(id=user_id)

    other_user = get_object_or_404(User, username=username)

    # 🔒 проверка доступа
    if current_user.is_lawyer:
        allowed = UserLawyer.objects.filter(
            user=other_user,
            lawyer__user=current_user,
            status="active"
        ).exists()
    else:
        allowed = UserLawyer.objects.filter(
            user=current_user,
            lawyer__user=other_user,
            status="active"
        ).exists()

    if not allowed:
        return redirect('lawyers_and_users')
    userislawyer=None
    # 💬 сообщения
    messages_qs = Message.objects.filter(
        Q(sender=current_user, receiver=other_user) |
        Q(sender=other_user, receiver=current_user)
    ).order_by("created_at")

    # =========================
    # 🔍 ПОИСК ЗАКОНОВ (только адвокат)
    # =========================
    zakons_list = []
    all_categories = []

    if current_user.is_lawyer:
        userislawyer=current_user.is_lawyer

        query = request.GET.get('q', '').strip()
        category = request.GET.get('category', '').strip()
        zakon_id_raw = request.GET.get('zakon_id', '').strip()

        zakons_list = Zakon_sbornik.objects.all()
        all_categories = Zakon_sbornik.objects.values_list('category', flat=True).distinct()

        if zakon_id_raw and zakon_id_raw.isdigit():
            zakons_list = zakons_list.filter(zakon_id__icontains=zakon_id_raw)

        if category:
            zakons_list = zakons_list.filter(category__icontains=category)

        if query:
            zakons_list = zakons_list.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )

        zakons_list = zakons_list[:10]  # ограничим

    # =========================
    # ✉️ ОТПРАВКА
    # =========================
    if request.method == "POST":
        text = request.POST.get("text")
        law_id = request.POST.get("law_id")

        law = None
        if law_id:
            law = Zakon_sbornik.objects.filter(id=law_id).first()

        if text or law:
            Message.objects.create(
                sender=current_user,
                receiver=other_user,
                text=text or "",
                law=law
            )

        return redirect('chat', username=other_user.username)

    context = {
        "user":user,
        "userislawyer":userislawyer,
        "messages": messages_qs,
        "other_user": other_user,
        "zakons": zakons_list,
        "categories": all_categories,
        "user":user
    }

    return render(request, "paintings/chat.html", context)



































def ai_advocate_chat(request):

    user_id = request.session.get('user_id')

    if not user_id:
        return redirect('login')

    user = User.objects.get(id=user_id)

    # ищем активную связь
    relation = (
        UserLawyer.objects
        .filter(
            user=user,
            status="active"
        )
        .select_related("lawyer__user")
        .first()
    )

    if not relation:
        return HttpResponse("У вас нет назначенного адвоката")

    lawyer_profile = relation.lawyer
    lawyer_user = lawyer_profile.user

    return HttpResponse(
        f"Чат с адвокатом: "
        f"{lawyer_user.username}"
    )

def assign_lawyer(request, id):

    user_id = request.session.get('user_id')

    if not user_id:
        return redirect('login')

    user = User.objects.get(id=user_id)

    lawyer = LawyerProfile.objects.get(id=id)

    # 🔹 проверка лимита пользователя

    user_active_count = UserLawyer.objects.filter(
        user=user,
        status="active"
    ).count()

    if user_active_count >= user.get_lawyer_limit():

        return HttpResponse(
            "Вы достигли лимита адвокатов по подписке"
        )

    # 🔹 проверка лимита адвоката

    lawyer_active_count = UserLawyer.objects.filter(
        lawyer=lawyer,
        status="active"
    ).count()

    if lawyer_active_count >= lawyer.get_client_limit():

        return HttpResponse(
            "Адвокат занят (достиг лимита клиентов)"
        )

    # 🔹 проверка существующей связи

    existing = UserLawyer.objects.filter(
        user=user,
        lawyer=lawyer,
        status="active"
    ).first()

    if existing:

        return redirect('/chat/')

    # 🔹 создаём связь

    UserLawyer.objects.create(
        user=user,
        lawyer=lawyer
    )

    return redirect('/chat/')

def lawyer_detail(request, id):

    lawyer = LawyerProfile.objects.select_related(
        "user"
    ).get(id=id)

    user = None
    current_relations = None

    user_id = request.session.get('user_id')

    if user_id:

        user = User.objects.filter(
            id=user_id
        ).first()

        if user:

            current_relations = UserLawyer.objects.filter(
                user=user,
                status="active"
            )
        # Считаем активных клиентов адвоката
    client_count = UserLawyer.objects.filter(
        lawyer=lawyer,
        status="active"
    ).count

    return render(
        request,
        'paintings/lawyer_detail.html',
        {
            'lawyer': lawyer,
            'current_relations': current_relations,
            'client_count': client_count,  # передаём в шаблон
        }
    )

def proverka(request):

    user = None

    user_id = request.session.get('user_id')

    if user_id:

        user = User.objects.filter(
            id=user_id
        ).first()

    # параметры поиска

    query = request.GET.get('q', '').strip()

    specialty = request.GET.get(
        'specialty',
        ''
    ).strip()

    busy = request.GET.get(
        'busy',
        ''
    ).strip()

    lawyers_list = (
        LawyerProfile.objects
        .select_related("user")
        .annotate(
            client_count=Count(
                "lawyer_clients",
                filter=Q(
                    lawyer_clients__status="active"
                )
            )
        )
    )

    # 🔍 поиск по имени

    if query:

        lawyers_list = lawyers_list.filter(

            Q(user__username__icontains=query)
        )

    # 🔍 фильтр по специализации

    if specialty:

        lawyers_list = lawyers_list.filter(
            specialty__icontains=specialty
        )

    # 🔍 фильтр занятости

    if busy == "free":

        lawyers_list = [
            l for l in lawyers_list
            if l.client_count < l.get_client_limit()
        ]

    elif busy == "busy":

        lawyers_list = [
            l for l in lawyers_list
            if l.client_count >= l.get_client_limit()
        ]

    # специализации для datalist

    all_specialties = (
        LawyerProfile.objects
        .values_list(
            'specialty',
            flat=True
        )
        .distinct()
    )

    current_relations = None

    if user:

        current_relations = UserLawyer.objects.filter(
            user=user,
            status="active"
        )

    favorite_ids = []

    if user and hasattr(user, 'favorite_lawyers'):

        favorite_ids = list(
            user.favorite_lawyers
            .values_list('id', flat=True)
        )

    return render(
        request,
        'paintings/proverka.html',
        {
            'lawyers_list': lawyers_list,
            'query': query,
            'specialty': specialty,
            'busy': busy,
            'all_specialties': all_specialties,
            'favorite_ids': favorite_ids,
            'user': user,
            'current_relations': current_relations,
        }
    )










from .models import LawyerProfile, UserLawyer, User, Message, Zakon_sbornik
from django.utils import timezone

def lawyers_list(request):
    user = request.user
    query = request.GET.get("q", "")
    specialty = request.GET.get("specialty", "")
    available = request.GET.get("available", "")

    if user.is_lawyer:
        # адвокат ищет клиентов
        clients = User.objects.all()
        if query:
            clients = clients.filter(username__icontains=query)
        if specialty:
            clients = clients.filter(subscription_level__icontains=specialty)

        # выделяем клиентов, которые уже связаны с адвокатом
        my_clients_ids = UserLawyer.objects.filter(lawyer=user.lawyer_profile, status="active").values_list('user_id', flat=True)

        return render(request, 'lawyers/lawyers_list.html', {
            'is_lawyer': True,
            'clients': clients,
            'my_clients_ids': my_clients_ids
        })

    # обычный пользователь ищет адвокатов
    lawyers = LawyerProfile.objects.all()
    if query:
        lawyers = lawyers.filter(user__username__icontains=query)
    if specialty:
        lawyers = lawyers.filter(specialty__icontains=specialty)

    for l in lawyers:
        l.is_full = l.lawyer_clients.filter(status="active").count() >= l.get_client_limit()

    my_lawyers_ids = UserLawyer.objects.filter(user=user, status="active").values_list("lawyer_id", flat=True)

    if available == "1":
        lawyers = [l for l in lawyers if not l.is_full]

    return render(request, 'lawyers/lawyers_list.html', {
        'is_lawyer': False,
        'lawyers': lawyers,
        'my_lawyers_ids': my_lawyers_ids
    })


def lawyers_profile(request, username):
    lawyer = LawyerProfile.objects.get(user__username=username)
    user = request.user

    is_my = UserLawyer.objects.filter(user=user, lawyer=lawyer, status="active").exists()
    is_full = lawyer.lawyer_clients.filter(status="active").count() >= lawyer.get_client_limit()

    return render(request, 'lawyers/lawyers_profile.html', {
        'lawyer': lawyer,
        'is_my': is_my,
        'is_full': is_full
    })


@transaction.atomic
def take_lawyer(request, username):
    user = request.user
    lawyer = LawyerProfile.objects.select_for_update().get(user__username=username)

    if lawyer.lawyer_clients.filter(status="active").count() >= lawyer.get_client_limit():
        return redirect('lawyers_list')

    if UserLawyer.objects.filter(user=user, status="active").count() >= user.get_lawyer_limit():
        return redirect('lawyers_list')

    UserLawyer.objects.create(user=user, lawyer=lawyer)

    return redirect('chat', username=lawyer.user.username)


def chat_view(request, username):
    other = User.objects.get(username=username)
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other) | Q(sender=other, receiver=request.user)
    ).order_by("created_at")

    if request.method == "POST":
        text = request.POST.get("text")
        law_id = request.POST.get("law_id")
        law = Zakon_sbornik.objects.filter(zakon_id=law_id).first() if law_id else None

        Message.objects.create(
            sender=request.user,
            receiver=other,
            text=text,
            law=law
        )

        return redirect('chat', username=username)

    return render(request, 'lawyers/chat.html', {
        'messages': messages,
        'other': other,
        'is_lawyer': request.user.is_lawyer
    })

























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
    if request.session.get('user_id'):
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
    else:
        user=None


    


    return render(request, 'paintings/ui.html', {
        "user": user
    })

@csrf_exempt
def save_ui_settings(request):

    if request.method == "POST":

        user_id = request.session.get("user_id")
        if not user_id:
            return JsonResponse({"status": "error", "message": "not logged"})

        data = json.loads(request.body)

        theme = data.get("theme")
        font_size = data.get("font_size")

        user = User.objects.get(id=user_id)

        if theme:
            user.theme = theme

        if font_size:
            user.font_size = font_size

        user.save()

        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "error"})

def indedx(request):
    latest_laws = Zakon_sbornik.objects.order_by('-date_added')[:3]
    user = None
    isAuthenticated = False
    user_id = request.session.get('user_id')

    if user_id:
        user = User.objects.filter(id=user_id).first()
        isAuthenticated = user.is_authenticated

    return render(request, 'paintings/index.html', {
        'latest_laws': latest_laws,
        'user': user,
        'isAuthenticated': isAuthenticated
    })


def index(request):
    latest_laws = Zakon_sbornik.objects.order_by('-date_added')[:3]
    user = None
    isAuthenticated = False
    user_id = request.session.get('user_id')

    if user_id:
        user = User.objects.filter(id=user_id).first()
        isAuthenticated = user.is_authenticated
    now = timezone.now()
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)

    # 🔥 подзапрос: самый частый вопрос для конкретного ответа
    most_common_question = OTVET_REQUEST.objects.filter(
        answer=OuterRef('pk')
    ).values('user_question').annotate(
        q_count=Count('id')
    ).order_by('-q_count').values('user_question')[:1]

    # 🔥 за день (ТОП 5)
    popular_today = (
        OTVET.objects
        .annotate(
            usage_count=Count(
                'otvet_request',
                filter=Q(otvet_request__created_at__gte=day_ago)
            ),
            common_question=Subquery(most_common_question)
        )
        .filter(usage_count__gt=0)
        .order_by('-usage_count')[:5]
    )

    # 📅 за месяц (ТОП 5)
    popular_month = (
        OTVET.objects
        .annotate(
            usage_count=Count(
                'otvet_request',
                filter=Q(otvet_request__created_at__gte=month_ago)
            ),
            common_question=Subquery(most_common_question)
        )
        .filter(usage_count__gt=0)
        .order_by('-usage_count')[:5]
    )

    return render(request, 'paintings/index.html', {
        'latest_laws': latest_laws,
        'user': user,
        'isAuthenticated': isAuthenticated,
        'popular_today': popular_today,
        'popular_month': popular_month,
    })



def base(request):
    user = None
    user_id = request.session.get('user_id')
    if user_id:
        user = User.objects.filter(id=user_id).first()
        isAuthenticated = user.is_authenticated

    return render(request, 'paintings/.html', {
        'user': user,
        'isAuthenticated': isAuthenticated
    })


def aiadvocat(request):
    user = None
    user_id = request.session.get('user_id')
    if user_id:
        user = User.objects.filter(id=user_id).first()

    return render(request, 'paintings/aiadvocat.html',{
        'user': user,
    })






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
    if user_id:
        user = User.objects.filter(id=user_id).first()
        isAuthenticated = user.is_authenticated

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
        first_day = date(2026, month, 1)
        first_weekday = first_day.weekday()  # 0=понедельник
        first_day_offset = list(range(first_weekday))
        month_name = calendar.month_name[month]
        monthly_stats[month_name] = {
            "top_category": None,
            "ai_count": 0,
            "view_count": 0,
            "weeks": {},
            "first_day_offset": list(range(first_weekday)),
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
    # данные для графика
    chart_data = {}

    for month_name, month_data in monthly_stats.items():
        days = []
        activity_ai = []
        activity_zakon=[]
        activity=[]
        for week in month_data["weeks"].values():
            for day, day_data in week["days"].items():
                if day_data:
                    days.append(day.day)
                    activity_ai.append(day_data["ai_count"])
                    activity_zakon.append(day_data["view_count"])
                    activity.append(day_data["ai_count"] + day_data["view_count"])
        chart_data[month_name] = {
            "days": days,
            "activityAI": activity_ai,
            "activityZAKON":activity_zakon,
            "activity":activity
            }
    chart_data = json.dumps(chart_data) 


     # 👇 все активные адвокаты пользователя
    relations = UserLawyer.objects.filter(
        user=user,
        status="active"
    ).select_related("lawyer__user")
    users=None
    lawyers = [rel.lawyer for rel in relations]
    if user.is_lawyer:
        users = User.objects.filter(
        client_lawyers__lawyer__user=user,
        client_lawyers__status="active"
        ).distinct()








    #
    context = {
        "user": user,
        "monthly_stats": monthly_stats,
        "total_ai_requests": total_ai_requests,
        "total_zakon_views": total_zakon_views,
        "last_ai_request": last_ai_request,
        "last_zakon_view": last_zakon_view,
        "favorite_category": favorite_category,
        "weekdays": weekdays,
        "chart_data": chart_data,
        "isAuthenticated": isAuthenticated,
        "users":users,

        "lawyers": lawyers,
        "lawyers_count": len(lawyers),
        "limit": user.get_lawyer_limit(),
    }
    for month in monthly_stats.values():
        for week in month["weeks"].values():
            for day in week["days"].values():
                day["ai_requests"] = json.dumps(day["ai_requests"])
                day["zakon_views"] = json.dumps(day["zakon_views"])
    

    return render(request, "paintings/profile.html", context)




def zakons(request):
    user=None
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
        "user":user,
    })


def zakon_detail(request, pk):
    user=None
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
        'is_favorite': is_favorite,
        'user':user
    })









def can_send_email(request, session_key, max_attempts, time_window, error_message):
    """
    Проверяет, можно ли отправлять email по лимиту.
    session_key - ключ в сессии, где хранятся попытки
    max_attempts - максимум попыток
    time_window - timedelta, за который считаем попытки
    error_message - сообщение об ошибке, если превышен лимит
    """
    now = timezone.now()
    if session_key not in request.session:
        request.session[session_key] = []

    attempts = [t for t in request.session[session_key] if now - timezone.datetime.fromisoformat(t) < time_window]
    request.session[session_key] = attempts

    if len(attempts) >= max_attempts:
        messages.error(request, error_message)
        return False, attempts

    # добавляем текущую попытку
    attempts.append(now.isoformat())
    request.session[session_key] = attempts
    return True, attempts


# Вход
def login_view(request):
    MAX_ATTEMPTS = 10
    TIME_WINDOW = timedelta(minutes=15)
    if request.method == 'POST':
        form = LoginForm(request.POST,request=request)
        # Инициализация данных сессии для логина
        if 'login_attempts' not in request.session:
            request.session['login_attempts'] = []
        # Фильтруем старые попытки
        now = timezone.now()
        attempts = [t for t in request.session['login_attempts'] if now - timezone.datetime.fromisoformat(t) < TIME_WINDOW]
        request.session['login_attempts'] = attempts

        if len(attempts) >= MAX_ATTEMPTS:
            messages.error(request, "Слишком много попыток входа. Попробуйте позже.")
            return render(request, 'paintings/login.html', {'form': form})
        if form.is_valid():
            try:
                user = User.objects.get(username=form.cleaned_data['username'])
                if user.check_password(form.cleaned_data['password']):
                    request.session['user_id'] = user.id
                    messages.success(request, f"Добро пожаловать, {user.username}!")
                    # Очистка попыток при успешном входе
                    request.session['login_attempts'] = []
                    return redirect('profile')
                else:
                    messages.error(request, "Неверный пароль")
            except User.DoesNotExist:
                messages.error(request, "Пользователь не найден")
            # Сохраняем неудачную попытку
            attempts.append(now.isoformat())
            request.session['login_attempts'] = attempts
    else:
        form = LoginForm(request=request)
    return render(request, 'paintings/login.html', {'form': form})



def password_reset_view(request):
    MAX_EMAIL_ATTEMPTS = 5
    EMAIL_TIME_WINDOW = timedelta(minutes=30)    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST,request=request)
        # Инициализация сессии для подсчёта отправок
        if 'email_attempts' not in request.session:
            request.session['email_attempts'] = []

        now = timezone.now()
        # фильтруем старые попытки
        attempts = [
            t for t in request.session['email_attempts']
            if now - timezone.datetime.fromisoformat(t) < EMAIL_TIME_WINDOW
        ]
        request.session['email_attempts'] = attempts

        if len(attempts) >= MAX_EMAIL_ATTEMPTS:
            messages.error(request, "Вы превысили лимит отправки кодов. Попробуйте позже.")
            return render(request, 'paintings/password_reset.html', {'form': form})
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
 # Сохраняем попытку
                attempts.append(now.isoformat())
                request.session['email_attempts'] = attempts
                request.session['email_sent'] = True
                request.session['email_sent_count'] = len(attempts)

                messages.success(request, "Код для сброса пароля отправлен на email!")
                return redirect('password_reset_confirm', user_id=user.id)
            except User.DoesNotExist:
                messages.error(request, "Пользователь с таким email не найден")
    else:
        form = PasswordResetForm(request=request)
    return render(request, 'paintings/password_reset.html', {'form': form})




class SetNewPasswordForm(forms.Form):
    code = forms.CharField(max_length=6)
    new_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

def password_reset_confirm_view(request, user_id):
    MAX_RESEND_ATTEMPTS = 5
    RESEND_WINDOW = timedelta(minutes=15)

    user = get_object_or_404(User, id=user_id)

    # Инициализация попыток
    if 'reset_confirm_attempts' not in request.session:
        request.session['reset_confirm_attempts'] = []

    now = timezone.now()
    attempts = [
        t for t in request.session['reset_confirm_attempts']
        if now - timezone.datetime.fromisoformat(t) < RESEND_WINDOW
    ]
    request.session['reset_confirm_attempts'] = attempts

    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST, request=request)

        # 🔁 ПОВТОРНАЯ ОТПРАВКА КОДА
        if "resend_code" in request.POST:
            if len(attempts) >= MAX_RESEND_ATTEMPTS:
                messages.error(request, "Вы превысили лимит повторных отправок. Попробуйте позже.")
            else:
                code = user.generate_code()  # ⚡ генерируем НОВЫЙ код

                send_verification_email(
                    user.email,
                    "Сброс пароля",
                    f"Ваш новый код для сброса пароля: {code}"
                )

                attempts.append(now.isoformat())
                request.session['reset_confirm_attempts'] = attempts

                messages.success(request, "Новый код отправлен на email!")

        # ✅ ПОДТВЕРЖДЕНИЕ КОДА
        elif form.is_valid():
            code = form.cleaned_data['code']
            new_password = form.cleaned_data['new_password']

            if user.email_verification_code == code and user.code_is_valid():
                user.set_password(new_password)
                user.email_verification_code = None
                user.code_created_at = None
                user.save()

                # очистка попыток
                request.session['reset_confirm_attempts'] = []

                messages.success(request, "Пароль успешно изменен!")
                return redirect('login')
            else:
                messages.error(request, "Неверный или просроченный код")

    else:
        form = SetNewPasswordForm()

    return render(request, 'paintings/password_reset_confirm.html', {'form': form})


def registration_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST,request=request)

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
    MAXS_RESEND_ATTEMPTS = 5
    RESEND_WINDOW = timedelta(minutes=15)

    if 'verify_email_attempts' not in request.session:
        request.session['verify_email_attempts'] = []

    now = timezone.now()
    # фильтруем старые попытки
    attempts = [
        t for t in request.session['verify_email_attempts']
        if now - timezone.datetime.fromisoformat(t) < RESEND_WINDOW
    ]
    request.session['verify_email_attempts'] = attempts

    if request.method == 'POST':
        form = VerifyEmailForm(request.POST, request=request)

        if "resend_code" in request.POST:
            if len(attempts) >= MAXS_RESEND_ATTEMPTS:
                messages.error(request, "Вы превысили лимит повторных отправок. Попробуйте позже.")
            else:
                data = request.session.get('registration_data')
                if data:
                    # генерируем новый код
                    new_code = str(random.randint(100000, 999999))
                    request.session['email_verification_code'] = new_code
                    request.session['code_created_at'] = timezone.now().isoformat()
            
                    email = data.get('email')
                    send_verification_email(
                        email,
                        "Подтверждение email",
                        f"Ваш код подтверждения: {new_code}"
                    )
                    attempts.append(now.isoformat())
                    request.session['verify_email_attempts'] = attempts
                    messages.success(request, "Новый код отправлен на ваш email!")

        elif form.is_valid():
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
                    request.session.flush()
                    messages.success(request, "Email подтверждён! Теперь можете войти.")
                    return redirect('login')

            messages.error(request, "Неверный код подтверждения.")
    else:
        form = VerifyEmailForm(request=request)

    return render(request, 'paintings/verify_email.html', {'form': form})

def delete_account_view(request):
    user_id = request.session.get('user_id')

    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    

    MAX_ATTEMPTS = 5
    TIME_WINDOW = timedelta(minutes=15)

    # лимиты
    if 'delete_attempts' not in request.session:
        request.session['delete_attempts'] = []

    now = timezone.now()
    attempts = [
        t for t in request.session['delete_attempts']
        if now - timezone.datetime.fromisoformat(t) < TIME_WINDOW
    ]
    request.session['delete_attempts'] = attempts

    show_code_form = False
    form = None

    if request.method == "POST":

        # 🔁 ОТПРАВКА / ПЕРЕОТПРАВКА КОДА
        if "send_code" in request.POST or "resend_code" in request.POST:

            if len(attempts) >= MAX_ATTEMPTS:
                messages.error(request, "Вы превысили лимит запросов. Попробуйте позже.")
            else:
                code = user.generate_code()

                try:
                    send_verification_email(
                        user.email,
                        "Удаление аккаунта",
                        f"Ваш код для удаления аккаунта: {code}\n\nДействует 10 минут."
                    )

                    attempts.append(now.isoformat())
                    request.session['delete_attempts'] = attempts

                    messages.success(request, "Код отправлен на вашу почту.")
                    show_code_form = True
                    form = DeleteAccountForm()

                except Exception as e:
                    messages.error(request, "Не удалось отправить письмо.")
                    print("Ошибка отправки email:", e)

        # ✅ ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ
        elif "confirm_delete" in request.POST:
            form = DeleteAccountForm(request.POST)
            show_code_form = True

            if form.is_valid():
                code_entered = form.cleaned_data["code"].strip()

                if code_entered == user.email_verification_code and user.code_is_valid():
                    try:
                        user.delete()

                        # очистка
                        request.session.flush()

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
        "show_code_form": show_code_form,
        "form": form,
    })

def forgot_username_view(request):
    MAX_ATTEMPTS = 5
    TIME_WINDOW = timedelta(minutes=30)

    # Инициализация
    if 'forgot_username_attempts' not in request.session:
        request.session['forgot_username_attempts'] = []

    now = timezone.now()

    # фильтрация старых попыток
    attempts = [
        t for t in request.session['forgot_username_attempts']
        if now - timezone.datetime.fromisoformat(t) < TIME_WINDOW
    ]
    request.session['forgot_username_attempts'] = attempts

    if request.method == "POST":
        form = ForgotUsernameForm(request.POST, request=request)

        # 🚫 Проверка лимита
        if len(attempts) >= MAX_ATTEMPTS:
            messages.error(request, "Вы превысили лимит запросов. Попробуйте позже.")
            return render(request, "paintings/forgot_username.html", {"form": form})

        if form.is_valid():
            email = form.cleaned_data["email"]

            try:
                user = User.objects.get(email=email)

                send_verification_email(
                    email,
                    "Ваш логин",
                    f"Ваш логин для входа: {user.username}"
                )

                # ✅ сохраняем попытку
                attempts.append(now.isoformat())
                request.session['forgot_username_attempts'] = attempts

                messages.success(request, "Логин отправлен на ваш email!")

            except User.DoesNotExist:
                messages.error(request, "Пользователь с таким email не найден")

    else:
        form = ForgotUsernameForm(request=request)

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

    return render(request, "paintings/aiadvocat.html", {"history": history, "user_authenticated": bool(user),"user":user})










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



def admin_panel(request):
    user = None
    user_id = request.session.get('user_id')
    if user_id:
        user = User.objects.filter(id=user_id).first()

    # ❌ нет аккаунта
    if not user_id:
        return HttpResponse("Без админки нельзя) глупый хакер")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponse("Без админки нельзя) глупый хакер")

    # ❌ не админ
    if not user.is_admin:
        return HttpResponse("Без админки нельзя) глупый хакер")
    section = request.GET.get('section', 'zakons')
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
    zakons = zakons_list
    otvet_query = request.GET.get('otvet_q', '').strip()
    otvet_keyword = request.GET.get('keyword', '').strip()
    otvet_zakon_id = request.GET.get('otvet_zakon_id', '').strip()

    otvets_list = OTVET.objects.all()

    # ✅ фильтр по ключевым словам
    if otvet_keyword:
        otvets_list = otvets_list.filter(keywords__icontains=otvet_keyword)

# ✅ поиск по тексту ответа
    if otvet_query:
        otvets_list = otvets_list.filter(answer__icontains=otvet_query)

# ✅ фильтр по связанному закону (ID)
    if otvet_zakon_id:
        if otvet_zakon_id.isdigit():
            otvets_list = otvets_list.filter(laws__zakon_id__icontains=otvet_zakon_id)
        else:
            messages.error(request, "ZAKONID должен содержать только цифры!")

    otvets = otvets_list.distinct()

    zakon_form = ZakonForm()
    otvet_form = OtvetForm()
    categories = Zakon_sbornik.objects.values_list('category', flat=True).distinct()
    
    return render(request, 'paintings/admin_panel.html', {
        'zakons': zakons,
        'otvets': otvets,
        'zakon_form': zakon_form,
        'otvet_form': otvet_form,
        'categories': categories,
        'user': user,
        'otvet_query': otvet_query,
        'otvet_keyword': otvet_keyword,
        'otvet_zakon_id': otvet_zakon_id,
        'section': section,
    })


# ====== СОЗДАНИЕ ======

def create_zakon(request):
    if request.method == 'POST':
        form = ZakonForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect('admin_panel')


def create_otvet(request):
    if request.method == 'POST':
        form = OtvetForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect('admin_panel')


# ====== УДАЛЕНИЕ ======

def delete_zakon(request, pk):
    Zakon_sbornik.objects.filter(pk=pk).delete()
    return redirect('admin_panel')


def delete_otvet(request, pk):
    OTVET.objects.filter(pk=pk).delete()
    return redirect('admin_panel')


# ====== РЕДАКТИРОВАНИЕ (inline) ======

def edit_zakon(request, pk):
    zakon = get_object_or_404(Zakon_sbornik, pk=pk)
    form = ZakonForm(request.POST, instance=zakon)
    if form.is_valid():
        form.save()
    return redirect('admin_panel')


def edit_otvet(request, pk):
    otvet = get_object_or_404(OTVET, pk=pk)
    form = OtvetForm(request.POST, instance=otvet)
    if form.is_valid():
        form.save()
    return redirect('admin_panel')