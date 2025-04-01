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
        now = datetime.now()
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
        
        context['recent_activities'] = sorted(
            recent_activities,
            key=lambda x: datetime.strptime(x['time'], '%d/%m/%Y %H:%M'),
            reverse=True
        )[:5]
        
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

class CreditPurchaseView(LoginRequiredMixin, View):
    template_name = 'user/credit_purchase.html'
    
    def get(self, request):
        context = {
            'credit_packages': [
                {'amount': 100, 'price': 1000, 'bonus': 0},
                {'amount': 500, 'price': 4500, 'bonus': 50},
                {'amount': 1000, 'price': 8000, 'bonus': 150},
                {'amount': 2000, 'price': 15000, 'bonus': 400},
            ],
            'user': request.user,
            'is_staff': request.user.is_staff
        }
        return render(request, self.template_name, context)

@method_decorator(require_POST, name='dispatch')
class ProcessPaymentView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            amount = int(data.get('amount', 0))
            price = Decimal(str(data.get('price', 0)))  # Conversion en Decimal
            payment_method = data.get('payment_method')
            promo_code = data.get('promo_code')

            # Vérifier le code promo si fourni
            final_price = price
            promo_instance = None
            if promo_code:
                try:
                    promo_instance = PromoCode.objects.get(code=promo_code)
                    if promo_instance.is_valid():
                        final_price = promo_instance.apply_discount(price)
                        promo_instance.increment_usage()
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

            # Créer la transaction
            transaction = CreditTransaction.objects.create(
                user=request.user,
                transaction_type='PURCHASE',
                amount=amount,
                price=final_price,
                payment_method=payment_method,
                promo_code=promo_instance,
                status='PENDING'
            )

            # Simuler le traitement du paiement
            transaction.process_payment()

            # Générer et envoyer la facture
            try:
                # Générer la facture PDF
                invoice_generator = InvoiceGenerator(transaction)
                invoice_filename = invoice_generator.generate()

                # Envoyer la facture par email
                InvoiceSender.send_invoice(request.user, invoice_filename)
            except Exception as e:
                print(f"Erreur lors de la génération/envoi de la facture: {str(e)}")
                # Ne pas bloquer la transaction si la facture échoue

            return JsonResponse({
                'success': True,
                'message': 'Paiement traité avec succès. La facture a été envoyée à votre adresse email.',
                'transaction_id': transaction.id
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

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
