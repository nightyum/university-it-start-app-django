from django.urls import path
from . import views


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
    path("delete_account/<int:user_id>/", views.delete_account_view, name="delete_account"),
    path('profile/favorite/<int:pk>/remove/', views.remove_from_favorites_profile, name='remove_from_favorites_profile'),
    path('forgot_username/', views.forgot_username_view, name='forgot_username'),
    path("aiadvocat/", views.ai_advocate, name="ai_advocate"),
    path('analytics/', views.analytics_view, name='analytics'),
    path('ui/', views.ui_views, name='ui')
]


