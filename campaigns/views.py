from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.views import View
from .models import Campaign, Contact, SenderId, Message
from django.db.models import Count, Q
import pandas as pd
import phonenumbers
from io import BytesIO
from django.utils import timezone
from django.contrib import messages
import re

class SenderIdListView(LoginRequiredMixin, ListView):
    model = SenderId
    template_name = 'campaigns/sender_id_list.html'
    context_object_name = 'sender_ids'

    def get_queryset(self):
        return SenderId.objects.filter(user=self.request.user)

class SenderIdCreateView(LoginRequiredMixin, CreateView):
    model = SenderId
    template_name = 'campaigns/sender_id_form.html'
    fields = ['name']
    success_url = reverse_lazy('campaigns:sender_id_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        # Vérifier si un sender ID avec le même nom existe déjà
        name = form.cleaned_data['name']
        existing_sender = SenderId.objects.filter(name=name).exists()
        
        # Vérifier aussi dans l'app user
        try:
            from django.apps import apps
            User_SenderId = apps.get_model('user', 'SenderID')
            existing_user_sender = User_SenderId.objects.filter(name=name).exists()
        except Exception:
            existing_user_sender = False
            
        if existing_sender or existing_user_sender:
            # Si le sender ID existe déjà, ajouter un message d'erreur au contexte
            form.add_error('name', 'Un expéditeur avec ce nom existe déjà')
            return self.form_invalid(form)
            
        return super().form_valid(form)

class ContactListView(LoginRequiredMixin, ListView):
    model = Contact
    template_name = 'campaigns/contact_list.html'
    context_object_name = 'contacts'

class ContactCreateView(LoginRequiredMixin, CreateView):
    model = Contact
    template_name = 'campaigns/contact_form.html'
    fields = ['phone_number']
    success_url = reverse_lazy('campaigns:contact_list')

class CampaignListView(LoginRequiredMixin, ListView):
    model = Campaign
    template_name = 'campaigns/campaign_list.html'
    context_object_name = 'campaigns'

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['draft_count'] = self.get_queryset().filter(status='draft').count()
        context['sending_count'] = self.get_queryset().filter(status='sending').count()
        context['sent_count'] = self.get_queryset().filter(status='sent').count()
        return context

class CampaignCreateView(LoginRequiredMixin, CreateView):
    model = Campaign
    template_name = 'campaigns/campaign_form.html'
    fields = ['name', 'message_content', 'sender', 'scheduled_date', 'is_rich_sms', 'rich_content']

    def get_success_url(self):
        return reverse('campaigns:campaign_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Sauvegarde la campagne
        self.object = form.save()
        
        # Récupérer et traiter les numéros de contact
        contact_numbers = self.request.POST.get('contact_numbers', '')
        if contact_numbers:
            # Créer ou récupérer les contacts et les associer à la campagne
            numbers = [num.strip() for num in contact_numbers.split(',') if num.strip()]
            for number in numbers:
                # Validation basique du numéro
                if not number or not re.match(r'^237\d{8,9}$', number):
                    continue
                
                # Créer ou récupérer le contact
                contact, created = Contact.objects.get_or_create(
                    phone_number=number,
                )
                
                # Associer le contact à la campagne via le modèle Message
                Message.objects.create(
                    campaign=self.object,
                    contact=contact,
                    content=self.object.message_content,
                    is_rich_sms=self.object.is_rich_sms,
                    rich_content=self.object.rich_content,
                    sender=self.object.sender
                )
        
        # Gérer l'action selon le bouton cliqué
        action = self.request.POST.get('action', 'save')
        if action == 'start':
            try:
                campaign = self.object
                
                # Si la date planifiée est dans le futur, changer le statut à 'scheduled'
                if campaign.scheduled_date and campaign.scheduled_date > timezone.now():
                    campaign.status = 'scheduled'
                    campaign.save()
                    messages.success(self.request, f"La campagne '{campaign.name}' a été programmée pour {campaign.scheduled_date}.")
                else:
                    # Sinon, démarrer la campagne immédiatement
                    campaign.status = 'sending'
                    campaign.save()
                    campaign.send()
                    messages.success(self.request, f"La campagne '{campaign.name}' a été démarrée avec succès.")
            except Exception as e:
                messages.error(self.request, f"Erreur lors du démarrage de la campagne: {str(e)}")
        else:
            # Même en mode "save", vérifier si une date est programmée
            if self.object.scheduled_date and self.object.scheduled_date > timezone.now():
                self.object.status = 'scheduled'
                self.object.save()
                messages.success(self.request, f"La campagne '{self.object.name}' a été programmée pour {self.object.scheduled_date}.")
            else:
                messages.success(self.request, f"La campagne '{self.object.name}' a été enregistrée en tant que brouillon.")
        
        return redirect('campaigns:campaign_list')
        
    def form_invalid(self, form):
        # Ajouter un message pour aider l'utilisateur à comprendre pourquoi le formulaire n'est pas valide
        errors = form.errors.as_data()
        for field, error_list in errors.items():
            for error in error_list:
                messages.error(self.request, f"Erreur: {field} - {error.message}")
        
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Récupérer les sender IDs depuis l'application user
        try:
            from django.apps import apps
            User_SenderId = apps.get_model('user', 'SenderID')
            
            # Si l'utilisateur est admin, il peut voir tous les Sender IDs approuvés
            if user.is_staff or user.is_superuser:
                user_approved_senders = User_SenderId.objects.filter(status="APPROUVE")
                print(f"DEBUG - Admin - Tous les Sender IDs approuvés: {list(user_approved_senders.values('id', 'name', 'user__username'))}")
            else:
                # Sinon, l'utilisateur ne peut voir que ses propres Sender IDs approuvés
                user_approved_senders = User_SenderId.objects.filter(
                    user=user,
                    status="APPROUVE"
                )
                print(f"DEBUG - Utilisateur - Sender IDs approuvés: {list(user_approved_senders.values('id', 'name'))}")
            
            # Récupérer ou créer les SenderId de l'application campaigns correspondants
            campaign_senders = []
            for user_sender in user_approved_senders:
                # Vérifier si un SenderId correspondant existe déjà
                campaign_sender, created = SenderId.objects.get_or_create(
                    user_sender_id=user_sender,
                    defaults={
                        'name': user_sender.name,
                        'user': user,
                        'status': 'approved'  # Status dans campaigns.SenderId
                    }
                )
                campaign_senders.append(campaign_sender)
            
            context['senders'] = campaign_senders
                
        except Exception as e:
            print(f"DEBUG - Erreur en essayant de récupérer les Sender IDs depuis l'app user: {str(e)}")
            # Fallback sur les Sender IDs de l'application campaigns
            if user.is_staff or user.is_superuser:
                context['senders'] = SenderId.objects.filter(status='approved')
            else:
                context['senders'] = SenderId.objects.filter(
                    user=user,
                    status='approved'
                )
        
        # Vérifier les variables de user pour débogage
        print(f"DEBUG - User ID: {user.id}, Username: {user.username}, Is staff: {user.is_staff}, Is superuser: {user.is_superuser}")
        
        return context

class CampaignDetailView(LoginRequiredMixin, DetailView):
    model = Campaign
    template_name = 'campaigns/campaign_detail.html'
    context_object_name = 'campaign'

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        messages = Message.objects.filter(campaign=self.object)
        context['messages'] = messages
        context['stats'] = {
            'total': messages.count(),
            'sent': messages.filter(status='sent').count(),
            'delivered': messages.filter(status='delivered').count(),
            'failed': messages.filter(status='failed').count(),
        }
        return context

class CampaignUpdateView(LoginRequiredMixin, UpdateView):
    model = Campaign
    template_name = 'campaigns/campaign_form.html'
    fields = ['name', 'message_content', 'sender', 'scheduled_date', 'is_rich_sms', 'rich_content']

    def get_success_url(self):
        return reverse('campaigns:campaign_list')

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user, status='draft')

    def form_valid(self, form):
        # Sauvegarde la campagne
        self.object = form.save()
        
        # Supprimer les messages existants pour cette campagne
        Message.objects.filter(campaign=self.object).delete()
        
        # Récupérer et traiter les numéros de contact
        contact_numbers = self.request.POST.get('contact_numbers', '')
        if contact_numbers:
            # Créer ou récupérer les contacts et les associer à la campagne
            numbers = [num.strip() for num in contact_numbers.split(',') if num.strip()]
            for number in numbers:
                # Validation basique du numéro
                if not number or not re.match(r'^237\d{8,9}$', number):
                    continue
                
                # Créer ou récupérer le contact
                contact, created = Contact.objects.get_or_create(
                    phone_number=number,
                )
                
                # Associer le contact à la campagne via le modèle Message
                Message.objects.create(
                    campaign=self.object,
                    contact=contact,
                    content=self.object.message_content,
                    is_rich_sms=self.object.is_rich_sms,
                    rich_content=self.object.rich_content,
                    sender=self.object.sender
                )
        
        # Gérer l'action selon le bouton cliqué
        action = self.request.POST.get('action', 'save')
        if action == 'start':
            try:
                campaign = self.object
                
                # Si la date planifiée est dans le futur, changer le statut à 'scheduled'
                if campaign.scheduled_date and campaign.scheduled_date > timezone.now():
                    campaign.status = 'scheduled'
                    campaign.save()
                    messages.success(self.request, f"La campagne '{campaign.name}' a été programmée pour {campaign.scheduled_date}.")
                else:
                    # Sinon, démarrer la campagne immédiatement
                    campaign.status = 'sending'
                    campaign.save()
                    campaign.send()
                    messages.success(self.request, f"La campagne '{campaign.name}' a été démarrée avec succès.")
            except Exception as e:
                messages.error(self.request, f"Erreur lors du démarrage de la campagne: {str(e)}")
        else:
            # Même en mode "save", vérifier si une date est programmée
            if self.object.scheduled_date and self.object.scheduled_date > timezone.now():
                self.object.status = 'scheduled'
                self.object.save()
                messages.success(self.request, f"La campagne '{self.object.name}' a été programmée pour {self.object.scheduled_date}.")
            else:
                messages.success(self.request, f"La campagne '{self.object.name}' a été mise à jour.")
        
        return redirect('campaigns:campaign_list')
        
    def form_invalid(self, form):
        # Ajouter un message pour aider l'utilisateur à comprendre pourquoi le formulaire n'est pas valide
        errors = form.errors.as_data()
        for field, error_list in errors.items():
            for error in error_list:
                messages.error(self.request, f"Erreur: {field} - {error.message}")
        
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Récupérer les sender IDs depuis l'application user
        try:
            from django.apps import apps
            User_SenderId = apps.get_model('user', 'SenderID')
            
            # Si l'utilisateur est admin, il peut voir tous les Sender IDs approuvés
            if user.is_staff or user.is_superuser:
                user_approved_senders = User_SenderId.objects.filter(status="APPROUVE")
                print(f"DEBUG - Admin - Tous les Sender IDs approuvés: {list(user_approved_senders.values('id', 'name', 'user__username'))}")
            else:
                # Sinon, l'utilisateur ne peut voir que ses propres Sender IDs approuvés
                user_approved_senders = User_SenderId.objects.filter(
                    user=user,
                    status="APPROUVE"
                )
                print(f"DEBUG - Utilisateur - Sender IDs approuvés: {list(user_approved_senders.values('id', 'name'))}")
            
            # Récupérer ou créer les SenderId de l'application campaigns correspondants
            campaign_senders = []
            for user_sender in user_approved_senders:
                # Vérifier si un SenderId correspondant existe déjà
                campaign_sender, created = SenderId.objects.get_or_create(
                    user_sender_id=user_sender,
                    defaults={
                        'name': user_sender.name,
                        'user': user,
                        'status': 'approved'  # Status dans campaigns.SenderId
                    }
                )
                campaign_senders.append(campaign_sender)
            
            context['senders'] = campaign_senders
                
        except Exception as e:
            print(f"DEBUG - Erreur en essayant de récupérer les Sender IDs depuis l'app user: {str(e)}")
            # Fallback sur les Sender IDs de l'application campaigns
            if user.is_staff or user.is_superuser:
                context['senders'] = SenderId.objects.filter(status='approved')
            else:
                context['senders'] = SenderId.objects.filter(
                    user=user,
                    status='approved'
                )
        
        # Vérifier les variables de user pour débogage
        print(f"DEBUG - User ID: {user.id}, Username: {user.username}, Is staff: {user.is_staff}, Is superuser: {user.is_superuser}")
        
        return context

class CampaignDeleteView(LoginRequiredMixin, DeleteView):
    model = Campaign
    template_name = 'campaigns/campaign_confirm_delete.html'
    success_url = reverse_lazy('campaigns:campaign_list')

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user, status='draft')

class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'campaigns/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaigns = Campaign.objects.filter(user=self.request.user)
        
        context['stats'] = {
            'total_campaigns': campaigns.count(),
            'total_messages': Message.objects.filter(campaign__in=campaigns).count(),
            'delivery_rate': Message.objects.filter(
                campaign__in=campaigns,
                status='delivered'
            ).count() / Message.objects.filter(campaign__in=campaigns).count() * 100 if Message.objects.filter(campaign__in=campaigns).exists() else 0,
            'campaigns_by_status': campaigns.values('status').annotate(count=Count('id'))
        }
        
        return context

class CampaignSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
        try:
            campaign.send()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class ContactImportView(LoginRequiredMixin, View):
    """Vue pour importer des contacts à partir d'un fichier Excel ou CSV"""
    
    def post(self, request):
        if 'file' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'Aucun fichier fourni'}, status=400)
        
        contact_file = request.FILES['file']
        file_extension = contact_file.name.split('.')[-1].lower()
        
        # Vérifier l'extension du fichier
        if file_extension not in ['csv', 'xlsx', 'xls']:
            return JsonResponse({
                'status': 'error', 
                'message': 'Format de fichier non pris en charge. Utilisez CSV ou Excel (.xlsx, .xls)'
            }, status=400)
        
        try:
            # Lire le fichier selon son format
            if file_extension == 'csv':
                # Essayer différents encodages courants
                encodings = ['utf-8', 'latin-1', 'ISO-8859-1']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(contact_file, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Impossible de lire le fichier CSV avec les encodages supportés'
                    }, status=400)
            else:
                # Excel
                df = pd.read_excel(contact_file)
            
            # S'assurer qu'il y a au moins une colonne
            if df.empty or len(df.columns) == 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Le fichier est vide ou ne contient pas de colonnes'
                }, status=400)
            
            # Extraire les numéros de téléphone de la première colonne
            phone_numbers = df.iloc[:, 0].astype(str).tolist()
            
            # Nettoyer et valider les numéros
            cleaned_numbers = []
            valid_numbers = []
            invalid_numbers = []
            
            for number in phone_numbers:
                # Supprimer les espaces, tirets, etc.
                cleaned = ''.join(filter(str.isdigit, number))
                
                # Ignorer les lignes vides
                if not cleaned:
                    continue
                
                cleaned_numbers.append(cleaned)
                
                # Vérifier si le numéro commence par 237 et a 12 chiffres (237 + 8-9 chiffres)
                if cleaned.startswith('237') and 11 <= len(cleaned) <= 12:
                    valid_numbers.append(cleaned)
                else:
                    invalid_numbers.append(cleaned)
            
            # Rechercher les doublons
            seen = set()
            duplicates = []
            
            for number in valid_numbers:
                if number in seen:
                    duplicates.append(number)
                else:
                    seen.add(number)
            
            # Préparer les statistiques pour la réponse
            unique_valid_numbers = list(seen)
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'total_numbers': len(cleaned_numbers),
                    'valid_numbers': unique_valid_numbers,
                    'valid_count': len(unique_valid_numbers),
                    'invalid_numbers': invalid_numbers,
                    'invalid_count': len(invalid_numbers),
                    'duplicate_count': len(duplicates)
                }
            })
            
        except Exception as e:
            # Capturer toutes les exceptions possibles lors du traitement
            import traceback
            return JsonResponse({
                'status': 'error',
                'message': f'Erreur lors du traitement du fichier: {str(e)}',
                'details': traceback.format_exc()
            }, status=500)
