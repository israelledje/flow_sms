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
    path('contacts/<int:pk>/update/', views.ContactUpdateView.as_view(), name='contact_update'),
    path('contacts/<int:pk>/delete/', views.ContactDeleteView.as_view(), name='contact_delete'),
    path('contacts/import/', views.ContactImportView.as_view(), name='contact_import'),
    path('contacts/export/', views.ContactExportView.as_view(), name='contact_export'),
    path('contacts/template/', views.DownloadTemplateView.as_view(), name='contact_template'),
    path('contacts/add-to-group/', views.AddContactsToGroupView.as_view(), name='add_contacts_to_group'),
    
    # Gestion des groupes de contacts
    path('contact-groups/', views.ContactGroupListView.as_view(), name='contact_group_list'),
    path('contact-groups/create/', views.ContactGroupCreateView.as_view(), name='contact_group_create'),
    path('contact-groups/<int:pk>/edit/', views.ContactGroupUpdateView.as_view(), name='contact_group_edit'),
    path('contact-groups/<int:pk>/delete/', views.ContactGroupDeleteView.as_view(), name='contact_group_delete'),
    
    # API endpoints pour les contacts
    path('api/group-contacts/', views.GetGroupContactsView.as_view(), name='get_group_contacts'),
    
    # Rapports
    path('reports/', views.ReportsView.as_view(), name='reports'),
    
    # URLs pour les modèles de SMS
    path('templates/', views.SMSTemplateListView.as_view(), name='sms_template_list'),
    path('templates/create/', views.SMSTemplateCreateView.as_view(), name='sms_template_create'),
    path('templates/<int:pk>/edit/', views.SMSTemplateUpdateView.as_view(), name='sms_template_edit'),
    path('templates/<int:pk>/delete/', views.SMSTemplateDeleteView.as_view(), name='sms_template_delete'),
    path('api/templates/', views.GetSMSTemplatesView.as_view(), name='get_templates'),
    path('api/templates/<int:template_id>/', views.GetTemplateDetailsView.as_view(), name='get_template_details'),
    
    # API endpoints
    path('api/', include('campaigns.api.urls')),
]
