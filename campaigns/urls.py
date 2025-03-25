from django.urls import path, include
from . import views


app_name = 'campaigns'

urlpatterns = [
    # Gestion des campagnes
    path('', views.CampaignListView.as_view(), name='campaign_list'),
    path('create/', views.CampaignCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CampaignDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CampaignUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.CampaignDeleteView.as_view(), name='delete'),
    path('<int:pk>/send/', views.CampaignSendView.as_view(), name='send'),
    
    # Gestion des Sender IDs
    path('sender-ids/', views.SenderIdListView.as_view(), name='sender_id_list'),
    path('sender-ids/create/', views.SenderIdCreateView.as_view(), name='sender_id_create'),
    
    # Gestion des contacts
    path('contacts/', views.ContactListView.as_view(), name='contact_list'),
    path('contacts/create/', views.ContactCreateView.as_view(), name='contact_create'),
    path('contacts/import/', views.ContactImportView.as_view(), name='contact_import'),
   
    
    # Rapports
    path('reports/', views.ReportsView.as_view(), name='reports'),
    
    # API endpoints
    path('api/', include('campaigns.api.urls')),
]
