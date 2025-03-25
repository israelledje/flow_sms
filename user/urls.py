from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'user'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Profil et paramètres
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('settings/', views.SettingsView.as_view(), name='settings'),

    # Contacts
    path('contacts/', views.ContactsView.as_view(), name='contacts'),

    # Authentification
    path('register/', views.RegistrationView.as_view(), name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    
    # Gestion du mot de passe
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='user/password_reset_done.html'),
         name='password_reset_done'),
    path('password/reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='user/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password/reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='user/password_reset_complete.html'),
         name='password_reset_complete'),
         
    # Désactivation du compte
    path('account/deactivate/', views.AccountDeactivationView.as_view(), name='account_deactivate'),

    # Sender ID URLs
    path('sender-ids/', views.sender_id_list, name='sender_id_list'),
    path('sender-ids/create/', views.sender_id_create, name='sender_id_create'),
    path('sender-ids/<int:pk>/edit/', views.sender_id_edit, name='sender_id_edit'),
    path('sender-ids/<int:pk>/delete/', views.sender_id_delete, name='sender_id_delete'),
    path('sender-ids/<int:pk>/set-default/', views.sender_id_set_default, name='sender_id_set_default'),
    
    # Admin Sender ID URLs
    path('admin/sender-ids/', views.sender_id_admin_list, name='sender_id_admin_list'),
    path('admin/sender-ids/<int:pk>/review/', views.sender_id_admin_review, name='sender_id_admin_review'),
]
