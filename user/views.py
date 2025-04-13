from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, 
    PasswordResetView, PasswordResetConfirmView
)
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from datetime import timedelta, datetime
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from decimal import Decimal
import json
import pytz
from django.core.paginator import Paginator
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

from .forms import UserRegistrationForm, AccountDeactivationForm, SenderIDForm, SenderIDAdminForm
from .models import User, SenderID, CreditTransaction, PromoCode
from .backends import EmailBackend
from campaigns.models import Campaign, Message, Contact, ContactGroup
from campaigns.services import SMSAPIService
from .invoices.generator import InvoiceGenerator
from .invoices.sender import InvoiceSender

class CustomLoginView(LoginView):
    template_name = 'user/login.html'
    success_url = reverse_lazy('user:dashboard')
    redirect_authenticated_user = True

    def form_valid(self, form):
        email = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        
        # Tentative d'authentification avec l'email
        user = authenticate(self.request, username=email, password=password, backend='user.backends.EmailBackend')
        
        if user is not None:
            login(self.request, user)
            messages.success(self.request, "Connexion réussie!")
            return redirect(self.success_url)
        else:
            form.add_error(None, "Email ou mot de passe incorrect")
            return self.form_invalid(form)

class CustomLogoutView(LogoutView):
    template_name = 'user/logout.html'
    next_page = 'user:login'
    http_method_names = ['get', 'post']

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            messages.info(request, "Vous avez été déconnecté avec succès.")
            return super().dispatch(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

class RegistrationView(CreateView):
    template_name = 'user/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('user:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Compte créé avec succès! Vous pouvez maintenant vous connecter.")
        return response

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'user/password_change.html'
    success_url = reverse_lazy('user:dashboard')

    def form_valid(self, form):
        messages.success(self.request, "Votre mot de passe a été changé avec succès!")
        return super().form_valid(form)

class CustomPasswordResetView(PasswordResetView):
    template_name = 'user/password_reset.html'
    email_template_name = 'user/password_reset_email.html'
    success_url = reverse_lazy('user:password_reset_done')

    def form_valid(self, form):
        messages.info(self.request, "Si un compte existe avec cette adresse email, vous recevrez les instructions de réinitialisation.")
        return super().form_valid(form)

class AccountDeactivationView(LoginRequiredMixin, FormView):
    template_name = 'user/account_deactivation.html'
    form_class = AccountDeactivationForm
    success_url = reverse_lazy('user:login')

    def form_valid(self, form):
        password = form.cleaned_data['password']
        if self.request.user.check_password(password):
            user = self.request.user
            user.is_active = False
            user.save()
            logout(self.request)
            messages.success(self.request, "Votre compte a été désactivé avec succès.")
            return super().form_valid(form)
        else:
            messages.error(self.request, "Mot de passe incorrect.")
            return self.form_invalid(form)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'user/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sms_service = SMSAPIService()
        
        # Statistiques de livraison sur les 30 derniers jours
        delivery_stats = sms_service.get_delivery_stats(days=30)
        
        # Statistiques des campagnes
        now = timezone.now()
        active_campaigns = Campaign.objects.filter(
            user=self.request.user,
            status='active'
        ).count()
        
        # Pour l'instant, on ne compte que les campagnes actives
        campaigns_ending = 0
        
        # Statistiques des contacts
        total_contacts = Contact.objects.filter(user=self.request.user).count()
        new_contacts = Contact.objects.filter(
            user=self.request.user,
            created_at__gte=now - timedelta(days=30)
        ).count()
        
        # Statistiques des messages
        messages_sent = Message.objects.filter(
            campaign__user=self.request.user,
            sent_at__gte=now - timedelta(days=30)
        ).count()
        
        # Calcul de la croissance des messages
        last_month_messages = Message.objects.filter(
            campaign__user=self.request.user,
            sent_at__gte=now - timedelta(days=60),
            sent_at__lt=now - timedelta(days=30)
        ).count()
        
        messages_growth = 0
        if last_month_messages > 0:
            messages_growth = ((messages_sent - last_month_messages) / last_month_messages) * 100
        
        # Statistiques des crédits
        user_credits = self.request.user.credits
        credits_used = Message.objects.filter(
            campaign__user=self.request.user,
            sent_at__gte=now - timedelta(days=30)
        ).aggregate(total=Sum('credits_used'))['total'] or 0
        
        # Calcul du pourcentage d'utilisation des crédits
        credits_usage_percentage = 0
        if user_credits > 0:
            credits_usage_percentage = (credits_used / user_credits) * 100
        
        context['stats'] = {
            'messages_sent': messages_sent,
            'messages_growth': round(messages_growth, 1),
            'active_campaigns': active_campaigns,
            'campaigns_ending': campaigns_ending,
            'total_contacts': total_contacts,
            'new_contacts': new_contacts,
            'delivery_rate': delivery_stats['delivery_rate'],
            'credits': user_credits,
            'credits_used': credits_used,
            'credits_usage_percentage': round(credits_usage_percentage, 1)
        }
        
        # Activité récente
        recent_activities = []
        
        # Messages récents
        recent_messages = Message.objects.filter(
            campaign__user=self.request.user
        ).select_related('campaign').order_by('-sent_at')[:5]
        
        for msg in recent_messages:
            recent_activities.append({
                'type': 'message',
                'title': f'Message envoyé à {msg.phone_number}',
                'description': f'Campagne: {msg.campaign.name}',
                'time': msg.sent_at.strftime('%d/%m/%Y %H:%M')
            })
        
        # Campagnes récentes
        recent_campaigns = Campaign.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:5]
        
        for campaign in recent_campaigns:
            recent_activities.append({
                'type': 'campaign',
                'title': f'Nouvelle campagne: {campaign.name}',
                'description': f'Statut: {campaign.get_status_display()}',
                'time': campaign.created_at.strftime('%d/%m/%Y %H:%M')
            })
        
        # Transactions de crédit récentes
        recent_transactions = CreditTransaction.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:5]
        
        for transaction in recent_transactions:
            recent_activities.append({
                'type': 'transaction',
                'title': f'Achat de {transaction.amount} crédits',
                'description': f'Prix: {transaction.price} FCFA - {transaction.get_status_display()}',
                'time': transaction.created_at.strftime('%d/%m/%Y %H:%M')
            })
        
        context['recent_activities'] = sorted(
            recent_activities,
            key=lambda x: datetime.strptime(x['time'], '%d/%m/%Y %H:%M'),
            reverse=True
        )[:5]
        
        return context

class CreditPurchaseView(LoginRequiredMixin, TemplateView):
    template_name = 'user/credit_purchase.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        
        # Packages prédéfinis avec les nouveaux tarifs
        context['credit_packages'] = [
            {'amount': 5000, 'price': 60000, 'description': 'Pack Découverte - 12 FCFA/SMS'},
            {'amount': 10000, 'price': 95000, 'description': 'Pack Standard - 9.5 FCFA/SMS'},
            {'amount': 50000, 'price': 475000, 'description': 'Pack Pro - 9.5 FCFA/SMS'},
            {'amount': 100000, 'price': 800000, 'description': 'Pack Business - 8 FCFA/SMS'},
            {'amount': 500000, 'price': 4000000, 'description': 'Pack Entreprise - 8 FCFA/SMS'},
            {'amount': 1000000, 'price': 6500000, 'description': 'Pack Platinum - 6.5 FCFA/SMS'}
        ]
        
        # Ajouter les méthodes de paiement disponibles
        context['payment_methods'] = [
            {'value': 'CREDIT_CARD', 'label': 'Carte de crédit'},
            {'value': 'ORANGE_MONEY', 'label': 'Orange Money'},
            {'value': 'MTN_MONEY', 'label': 'MTN Mobile Money'}
        ]
        
        return context

class ProfileView(LoginRequiredMixin, View):
    template_name = 'user/profile.html'

    def get(self, request):
        context = {
            'user': request.user,
            'LANGUAGE_CHOICES': User.LANGUAGE_CHOICES,
            'TIMEZONE_CHOICES': [(tz, tz) for tz in pytz.all_timezones],
        }
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get('action', '')
        user = request.user

        if action == 'personal_info':
            try:
                # Mise à jour des informations personnelles
                if user.account_type == 'ENTREPRISE':
                    user.nom = request.POST.get('nom')
                    user.secteur_activite = request.POST.get('secteur_activite')
                    user.niu = request.POST.get('niu')
                    user.rccm = request.POST.get('rccm')
                    user.site_web = request.POST.get('site_web')
                    user.nombre_employes = request.POST.get('nombre_employes')
                else:
                    user.nom = request.POST.get('nom')
                    user.prenom = request.POST.get('prenom')
                
                user.telephone = request.POST.get('telephone')
                user.email = request.POST.get('email')
                user.save()
                
                messages.success(request, "Informations personnelles mises à jour avec succès")
            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")

        elif action == 'address':
            try:
                # Mise à jour de l'adresse
                user.adresse = request.POST.get('adresse')
                user.ville = request.POST.get('ville')
                user.pays = request.POST.get('pays')
                user.save()
                
                messages.success(request, "Adresse mise à jour avec succès")
            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")

        elif action == 'preferences':
            try:
                # Mise à jour des préférences
                user.langue = request.POST.get('langue')
                user.fuseau_horaire = request.POST.get('fuseau_horaire')
                user.notifications_sms = request.POST.get('notifications_sms') == 'on'
                user.notifications_email = request.POST.get('notifications_email') == 'on'
                user.save()
                
                messages.success(request, "Préférences mises à jour avec succès")
            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")

        elif action == 'security':
            try:
                # Changement de mot de passe
                current_password = request.POST.get('current_password')
                new_password1 = request.POST.get('new_password1')
                new_password2 = request.POST.get('new_password2')

                if not user.check_password(current_password):
                    messages.error(request, "Le mot de passe actuel est incorrect")
                elif new_password1 != new_password2:
                    messages.error(request, "Les nouveaux mots de passe ne correspondent pas")
                else:
                    user.set_password(new_password1)
                    user.save()
                    update_session_auth_hash(request, user)  # Maintient la session active
                    messages.success(request, "Mot de passe modifié avec succès")
            except Exception as e:
                messages.error(request, f"Erreur lors du changement de mot de passe: {str(e)}")

        return redirect('user:profile')

class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'user/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

class ContactsView(LoginRequiredMixin, TemplateView):
    template_name = 'campaigns/contact_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contacts'] = Contact.objects.filter(user=self.request.user)
        context['contact_groups'] = ContactGroup.objects.filter(user=self.request.user)
        return context

@login_required
def sender_id_list(request):
    sender_ids = SenderID.objects.filter(user=request.user)
    return render(request, 'user/sender_id/list.html', {
        'sender_ids': sender_ids
    })

@login_required
def sender_id_create(request):
    if request.method == 'POST':
        form = SenderIDForm(request.POST)
        if form.is_valid():
            # Récupérer le nom du formulaire et le convertir en majuscules
            name = form.cleaned_data['name'].upper()
            
            # Vérifier si ce sender ID existe déjà pour cet utilisateur
            if SenderID.objects.filter(user=request.user, name=name).exists():
                form.add_error('name', 'Un expéditeur avec ce nom existe déjà pour votre compte.')
                messages.error(request, "Un expéditeur avec ce nom existe déjà pour votre compte.")
            else:
                sender_id = form.save(commit=False)
                sender_id.user = request.user
                sender_id.save()
                messages.success(request, "Votre Sender ID a été créé et est en attente d'approbation.")
                return redirect('user:sender_id_list')
    else:
        form = SenderIDForm()
    
    return render(request, 'user/sender_id/form.html', {
        'form': form,
        'title': 'Nouveau Sender ID'
    })

@login_required
def sender_id_edit(request, pk):
    sender_id = get_object_or_404(SenderID, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = SenderIDForm(request.POST, instance=sender_id)
        if form.is_valid():
            form.save()
            messages.success(request, "Le Sender ID a été mis à jour.")
            return redirect('user:sender_id_list')
    else:
        form = SenderIDForm(instance=sender_id)
    
    return render(request, 'user/sender_id/form.html', {
        'form': form,
        'sender_id': sender_id,
        'title': 'Modifier le Sender ID'
    })

@login_required
def sender_id_delete(request, pk):
    sender_id = get_object_or_404(SenderID, pk=pk, user=request.user)
    
    if request.method == 'POST':
        sender_id.delete()
        messages.success(request, "Le Sender ID a été supprimé.")
        return redirect('user:sender_id_list')
    
    return render(request, 'user/sender_id/delete.html', {
        'sender_id': sender_id
    })

@login_required
def sender_id_set_default(request, pk):
    sender_id = get_object_or_404(SenderID, pk=pk, user=request.user)
    
    if request.method == 'POST':
        sender_id.is_default = True
        sender_id.save()
        messages.success(request, f"{sender_id.name} est maintenant votre Sender ID par défaut.")
    
    return redirect('user:sender_id_list')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def sender_id_admin_list(request):
    sender_ids = SenderID.objects.select_related('user').all()
    return render(request, 'user/sender_id/admin_list.html', {
        'sender_ids': sender_ids
    })

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def sender_id_admin_review(request, pk):
    sender_id = get_object_or_404(SenderID, pk=pk)
    
    if request.method == 'POST':
        form = SenderIDAdminForm(request.POST, instance=sender_id)
        if form.is_valid():
            sender_id = form.save(commit=False)
            if sender_id.status == SenderID.Status.APPROUVE:
                sender_id.date_approbation = timezone.now()
            sender_id.save()
            
            # Envoyer une notification à l'utilisateur
            if sender_id.status == SenderID.Status.APPROUVE:
                messages.success(request, f"Le Sender ID {sender_id.name} a été approuvé.")
            elif sender_id.status == SenderID.Status.REJETE:
                messages.warning(request, f"Le Sender ID {sender_id.name} a été rejeté.")
            
            return redirect('user:sender_id_admin_list')
    else:
        form = SenderIDAdminForm(instance=sender_id)
    
    return render(request, 'user/sender_id/admin_review.html', {
        'form': form,
        'sender_id': sender_id
    })

@method_decorator(require_POST, name='dispatch')
class ProcessPaymentView(LoginRequiredMixin, View):
    """
    Vue pour traiter le paiement des crédits SMS
    """
    def post(self, request, *args, **kwargs):
        try:
            # Log des données reçues
            logger.info(f"Données reçues pour le paiement: {request.body}")
            
            data = json.loads(request.body)
            logger.info(f"Données JSON parsées: {data}")
            
            # Récupération et validation des données
            amount = data.get('amount')
            price = data.get('price')
            payment_method = data.get('method')
            promo_code = data.get('promoCode')
            phone_number = data.get('phoneNumber')
            pin = data.get('pin')
            
            # Log des données extraites
            logger.info(f"Données extraites - amount: {amount}, price: {price}, payment_method: {payment_method}")
            
            # Vérifications de base avec messages d'erreur plus détaillés
            if not amount:
                return JsonResponse({
                    'success': False,
                    'message': 'Le montant des crédits est requis'
                }, status=400)
            
            if not price:
                return JsonResponse({
                    'success': False,
                    'message': 'Le prix est requis'
                }, status=400)
            
            if not payment_method:
                return JsonResponse({
                    'success': False,
                    'message': 'La méthode de paiement est requise'
                }, status=400)
            
            # Conversion des types
            try:
                amount = int(amount)
                price = Decimal(str(price))
            except (ValueError, TypeError) as e:
                logger.error(f"Erreur de conversion des types: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': 'Format de données invalide'
                }, status=400)
            
            # Vérifier si une transaction est déjà en cours pour cet utilisateur
            pending_transaction = CreditTransaction.objects.filter(
                user=request.user,
                status='PENDING'
            ).first()
            
            if pending_transaction:
                logger.warning(f"Transaction en cours trouvée pour l'utilisateur {request.user.username}")
                return JsonResponse({
                    'success': False,
                    'message': 'Une transaction est déjà en cours'
                }, status=400)
            
            # Vérifier le code promo si fourni
            promo_discount = data.get('promoDiscount', 0)
            if promo_code:
                try:
                    promo = PromoCode.objects.get(
                        code=promo_code,
                        is_active=True,
                        valid_until__gte=timezone.now()
                    )
                    promo_discount = promo.discount_percentage
                    logger.info(f"Code promo valide trouvé: {promo_code}")
                except PromoCode.DoesNotExist:
                    logger.warning(f"Code promo invalide ou expiré: {promo_code}")
                    return JsonResponse({
                        'success': False,
                        'message': 'Code promo invalide ou expiré'
                    }, status=400)
            
            # Créer la transaction
            transaction = CreditTransaction.objects.create(
                user=request.user,
                amount=amount,
                price=price,
                payment_method=payment_method,
                promo_code=promo_code if promo_code else None,
                promo_discount=promo_discount,
                phone_number=phone_number,
                pin=pin
            )
            logger.info(f"Transaction créée avec succès: {transaction.id}")
            
            # Traiter le paiement
            if transaction.process_payment():
                logger.info(f"Paiement traité avec succès pour la transaction {transaction.id}")
                return JsonResponse({
                    'success': True,
                    'message': 'Paiement traité avec succès',
                    'transaction_id': transaction.id,
                    'new_balance': request.user.credits
                })
            else:
                logger.error(f"Échec du traitement du paiement pour la transaction {transaction.id}")
                return JsonResponse({
                    'success': False,
                    'message': 'Erreur lors du traitement du paiement'
                }, status=500)
                
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de décodage JSON: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Format de données JSON invalide'
            }, status=400)
        except Exception as e:
            logger.error(f"Erreur inattendue lors du traitement du paiement: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Une erreur est survenue lors du traitement du paiement'
            }, status=500)

class TransactionHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'user/transaction_history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = CreditTransaction.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
        return context

class VerifyPromoCodeView(LoginRequiredMixin, View):
    def get(self, request):
        code = request.GET.get('code')
        if not code:
            return JsonResponse({
                'success': False,
                'message': 'Code promo requis'
            })

        try:
            promo = PromoCode.objects.get(code=code)
            if promo.is_valid():
                return JsonResponse({
                    'success': True,
                    'discount': float(promo.discount_percentage)
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Code promo invalide ou expiré'
                })
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Code promo non trouvé'
            })

class PromoCodeAdminView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.user.is_staff:
            messages.error(request, "Vous n'avez pas les permissions nécessaires.")
            return redirect('user:dashboard')
            
        promo_codes = PromoCode.objects.all().order_by('-created_at')
        return render(request, 'user/admin/promo_codes.html', {
            'promo_codes': promo_codes
        })

    def post(self, request):
        if not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'message': 'Permission refusée'
            }, status=403)

        try:
            data = json.loads(request.body)
            promo = PromoCode.objects.create(
                code=data['code'],
                discount_percentage=data['discount_percentage'],
                valid_from=data['valid_from'],
                valid_until=data['valid_until'],
                max_uses=data.get('max_uses'),
                is_active=data['is_active']
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Code promo créé avec succès'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

class PromoCodeDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'message': 'Permission refusée'
            }, status=403)

        try:
            promo = PromoCode.objects.get(pk=pk)
            return JsonResponse({
                'id': promo.id,
                'code': promo.code,
                'discount_percentage': float(promo.discount_percentage),
                'valid_from': promo.valid_from.isoformat(),
                'valid_until': promo.valid_until.isoformat(),
                'max_uses': promo.max_uses,
                'is_active': promo.is_active
            })
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Code promo non trouvé'
            }, status=404)

    def put(self, request, pk):
        if not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'message': 'Permission refusée'
            }, status=403)

        try:
            data = json.loads(request.body)
            promo = PromoCode.objects.get(pk=pk)
            
            promo.code = data['code']
            promo.discount_percentage = data['discount_percentage']
            promo.valid_from = data['valid_from']
            promo.valid_until = data['valid_until']
            promo.max_uses = data.get('max_uses')
            promo.is_active = data['is_active']
            promo.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Code promo mis à jour avec succès'
            })
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Code promo non trouvé'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

    def delete(self, request, pk):
        if not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'message': 'Permission refusée'
            }, status=403)

        try:
            promo = PromoCode.objects.get(pk=pk)
            promo.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Code promo supprimé avec succès'
            })
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Code promo non trouvé'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

class UserDetailView(LoginRequiredMixin, View):
    template_name = 'user/admin/user_detail.html'

    def get(self, request, pk):
        user_detail = get_object_or_404(User, pk=pk)
        transactions = CreditTransaction.objects.filter(user=user_detail).order_by('-created_at')[:5]
        sender_ids = SenderID.objects.filter(user=user_detail)
        
        context = {
            'user_detail': user_detail,
            'transactions': transactions,
            'sender_ids': sender_ids,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        user_detail = get_object_or_404(User, pk=pk)
        action = request.POST.get('action')

        if action == 'credit_sms':
            try:
                amount = int(request.POST.get('credit_amount'))
                reason = request.POST.get('credit_reason')
                
                if amount <= 0:
                    raise ValueError("Le montant doit être positif")
                
                # Créer la transaction
                transaction = CreditTransaction.objects.create(
                    user=user_detail,
                    amount=amount,
                    transaction_type='CREDIT',
                    status='COMPLETED',
                    description=reason
                )
                
                # Mettre à jour les crédits de l'utilisateur
                user_detail.credits += amount
                user_detail.save()
                
                messages.success(request, f"{amount} SMS ont été crédités avec succès")
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, "Une erreur est survenue lors du crédit des SMS")
        
        elif action == 'update_info':
            try:
                user_detail.email = request.POST.get('email')
                user_detail.telephone = request.POST.get('telephone')
                user_detail.user_type = request.POST.get('user_type')
                
                if user_detail.account_type == 'ENTREPRISE':
                    user_detail.nom = request.POST.get('nom')
                else:
                    user_detail.nom = request.POST.get('nom')
                    user_detail.prenom = request.POST.get('prenom')
                
                user_detail.save()
                messages.success(request, "Les informations ont été mises à jour avec succès")
            except Exception as e:
                messages.error(request, "Une erreur est survenue lors de la mise à jour des informations")
        
        return redirect('user:admin_user_detail', pk=pk)

class AdminUserListView(LoginRequiredMixin, View):
    template_name = 'user/admin/user_list.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, "Vous n'avez pas les permissions nécessaires.")
            return redirect('user:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Filtres
        account_type = request.GET.get('account_type')
        verification_status = request.GET.get('verification_status')
        search_query = request.GET.get('q')
        
        # Base de la requête
        users = User.objects.all()
        
        # Appliquer les filtres
        if account_type:
            users = users.filter(account_type=account_type)
        
        if verification_status:
            users = users.filter(verification_status=verification_status)
        
        if search_query:
            users = users.filter(
                Q(email__icontains=search_query) |
                Q(nom__icontains=search_query) |
                Q(prenom__icontains=search_query) |
                Q(telephone__icontains=search_query)
            )
        
        # Statistiques
        total_users = users.count()
        active_users = users.filter(is_active=True).count()
        pending_verification = users.filter(verification_status='EN_ATTENTE').count()
        new_users = users.filter(
            date_creation__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        context = {
            'users': users.order_by('-date_creation'),
            'stats': {
                'total': total_users,
                'active': active_users,
                'pending': pending_verification,
                'new': new_users,
            },
            'filters': {
                'account_type': account_type,
                'verification_status': verification_status,
                'search_query': search_query,
            },
            'account_types': User.AccountTypes.choices,
            'verification_statuses': User.VerificationStatus.choices,
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'pending_verification': User.objects.filter(verification_status=User.VerificationStatus.EN_ATTENTE).count(),
            'new_users': User.objects.filter(date_creation__gte=timezone.now() - timezone.timedelta(days=30)).count(),
        }
        
        return render(request, self.template_name, context)

class AdminDashboardView(LoginRequiredMixin, View):
    template_name = 'user/admin/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, "Vous n'avez pas les permissions nécessaires.")
            return redirect('user:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Période de 30 jours
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Statistiques utilisateurs
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        pending_verification = User.objects.filter(verification_status='EN_ATTENTE').count()
        new_users = User.objects.filter(date_creation__gte=thirty_days_ago).count()
        
        # Statistiques Sender IDs
        total_sender_ids = SenderID.objects.count()
        pending_sender_ids = SenderID.objects.filter(status='EN_ATTENTE').count()
        approved_sender_ids = SenderID.objects.filter(status='APPROUVE').count()
        rejected_sender_ids = SenderID.objects.filter(status='REJETE').count()
        
        # Statistiques des transactions
        transaction_stats = {
            'credits_sold': CreditTransaction.objects.filter(
                created_at__gte=thirty_days_ago,
                status='COMPLETED'
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'revenue': CreditTransaction.objects.filter(
                created_at__gte=thirty_days_ago,
                status='COMPLETED'
            ).aggregate(total=Sum('price'))['total'] or 0,
            'pending': CreditTransaction.objects.filter(
                status='PENDING'
            ).count(),
            'failed': CreditTransaction.objects.filter(
                created_at__gte=thirty_days_ago,
                status='FAILED'
            ).count()
        }
        
        # Données de vente sur 30 jours
        sales_data = []
        for i in range(30):
            date = timezone.now() - timedelta(days=i)
            day_sales = CreditTransaction.objects.filter(
                status='COMPLETED',
                created_at__date=date.date()
            ).aggregate(
                total=Sum('price')
            )['total'] or 0
            
            sales_data.append({
                'date': date.strftime('%d/%m'),
                'amount': float(day_sales)
            })
        
        sales_data.reverse()
        
        # Activités récentes
        recent_activities = []
        
        # Nouveaux utilisateurs
        new_users_list = User.objects.filter(
            date_creation__gte=thirty_days_ago
        ).order_by('-date_creation')[:5]
        
        for user in new_users_list:
            recent_activities.append({
                'type': 'user',
                'title': f'Nouvel utilisateur: {user.get_full_name()}',
                'description': f'Type: {user.get_account_type_display()}',
                'time': user.date_creation
            })
        
        # Transactions récentes
        recent_transactions = CreditTransaction.objects.filter(
            created_at__gte=thirty_days_ago
        ).select_related('user').order_by('-created_at')[:5]
        
        for transaction in recent_transactions:
            recent_activities.append({
                'type': 'transaction',
                'title': f'Transaction: {transaction.reference}',
                'description': f'{transaction.amount} crédits - {transaction.get_status_display()}',
                'time': transaction.created_at
            })
        
        # Sender IDs récents
        recent_sender_ids = SenderID.objects.filter(
            date_creation__gte=thirty_days_ago
        ).select_related('user').order_by('-date_creation')[:5]
        
        for sender_id in recent_sender_ids:
            recent_activities.append({
                'type': 'sender_id',
                'title': f'Nouveau Sender ID: {sender_id.name}',
                'description': f'Status: {sender_id.get_status_display()}',
                'time': sender_id.date_creation
            })
        
        # Trier toutes les activités par date
        recent_activities.sort(key=lambda x: x['time'], reverse=True)
        recent_activities = recent_activities[:10]
        
        context = {
            'user_stats': {
                'total': total_users,
                'active': active_users,
                'pending': pending_verification,
                'new': new_users
            },
            'sender_id_stats': {
                'total': total_sender_ids,
                'pending': pending_sender_ids,
                'approved': approved_sender_ids,
                'rejected': rejected_sender_ids
            },
            'transaction_stats': transaction_stats,
            'sales_data': sales_data,
            'recent_activities': recent_activities
        }
        
        return render(request, self.template_name, context)

class AdminTransactionListView(LoginRequiredMixin, View):
    template_name = 'user/admin/transaction_list.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, "Vous n'avez pas les permissions nécessaires.")
            return redirect('user:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Récupérer les paramètres de filtrage
        search_query = request.GET.get('q', '')
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        # Construire la requête de base
        transactions = CreditTransaction.objects.all().order_by('-created_at')

        # Appliquer les filtres
        if search_query:
            transactions = transactions.filter(
                Q(user__email__icontains=search_query) |
                Q(user__nom__icontains=search_query) |
                Q(user__prenom__icontains=search_query) |
                Q(reference__icontains=search_query)
            )

        if status_filter:
            transactions = transactions.filter(status=status_filter)

        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d')
                transactions = transactions.filter(created_at__gte=date_from)
            except ValueError:
                pass

        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d')
                transactions = transactions.filter(created_at__lte=date_to)
            except ValueError:
                pass

        # Calculer les statistiques
        total_transactions = transactions.count()
        total_amount = transactions.filter(status='COMPLETED').aggregate(
            total=Sum('price')
        )['total'] or 0

        # Pagination
        paginator = Paginator(transactions, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'transactions': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'total_transactions': total_transactions,
            'total_amount': total_amount,
        }
        return render(request, self.template_name, context)
