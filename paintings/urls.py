from django.urls import path
from . import views
from .views import save_ui_settings

urlpatterns = [
    path('', views.index, name='index'),

    path('zakons/', views.zakons, name='zakons'),
    path('zakons/<int:pk>/', views.zakon_detail, name='zakon_detail'),
    path('zakons/<int:pk>/favorite/', views.add_to_favorites, name='add_to_favorites'),
    path('zakons/<int:pk>/unfavorite/', views.remove_from_favorites, name='remove_from_favorites'),
    path('proverka/', views.proverka, name='proverka'),
    path('profile/', views.profile_view, name='profile'),
    path('registration/', views.registration_view, name='registration'),
    path('login/', views.login_view, name='login'),
    path('password_reset/', views.password_reset_view, name='password_reset'),
    path('verify_email/', views.verify_email_view, name='verify_email'),
    path('password_reset_confirm/<int:user_id>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('logout/', views.logout_view, name='logout'),
    path("delete_account/", views.delete_account_view, name="delete_account"),
    path('profile/favorite/<int:pk>/remove/', views.remove_from_favorites_profile, name='remove_from_favorites_profile'),
    path('forgot_username/', views.forgot_username_view, name='forgot_username'),
    path("aiadvocat/", views.ai_advocate, name="ai_advocate"),
    path('analytics/', views.analytics_view, name='analytics'),
    path('ui/', views.ui_views, name='ui'),
    path('save-ui/', save_ui_settings, name='save_ui'),
    # список адвокатов / клиентов
    path('lawyersandusers/',views.lawyers_and_users,name='lawyers_and_users'),
    # профиль адвоката
    path('profilelawyer/<str:username>/',views.profile_lawyer,name='profile_lawyer'),

    # чат
    path('chat/<str:username>/',views.chat,name='chat'
    ),



    path('admin-panel/', views.admin_panel, name='admin_panel'),

    path('admin-panel/zakon/create/', views.create_zakon, name='create_zakon'),
    path('admin-panel/zakon/<int:pk>/delete/', views.delete_zakon, name='delete_zakon'),
    path('admin-panel/zakon/<int:pk>/edit/', views.edit_zakon, name='edit_zakon'),

    path('admin-panel/otvet/create/', views.create_otvet, name='create_otvet'),
    path('admin-panel/otvet/<int:pk>/delete/', views.delete_otvet, name='delete_otvet'),
    path('admin-panel/otvet/<int:pk>/edit/', views.edit_otvet, name='edit_otvet'),
    # подписки
    path("subscribe/<str:level>/",views.subscribe,name="subscribe"),

    path("save-rating/", views.save_rating, name="save_rating"),
    path('subscriptions/', views.subscriptions_page, name='subscriptions'),
    path(
    "cancel-subscription/",
    views.cancel_subscription,
    name="cancel_subscription"
)

]


