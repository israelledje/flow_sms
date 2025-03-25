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

from .forms import UserRegistrationForm, AccountDeactivationForm, SenderIDForm, SenderIDAdminForm
from .models import User, SenderID
from .backends import EmailBackend

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
        
        # Liste vide pour le template
        context['empty_list'] = []
        
        # Statistiques du tableau de bord
        context['stats'] = {
            'messages_sent': 0,  # À remplacer par le vrai nombre
            'messages_growth': 15,  # Exemple de croissance
            'active_campaigns': 0,  # À remplacer par le nombre réel
            'campaigns_ending': 0,  # Nombre de campagnes se terminant bientôt
            'total_contacts': 0,  # À remplacer par le nombre réel
            'new_contacts': 0,  # Nouveaux contacts ce mois
            'delivery_rate': 98,  # Exemple de taux de livraison
        }

        # Activités récentes (exemple)
        context['recent_activities'] = [
            {
                'type': 'message',
                'title': 'Campagne terminée',
                'description': 'La campagne "Promotion été" est terminée avec un taux de livraison de 98%',
                'time': 'Il y a 2h'
            },
            {
                'type': 'campaign',
                'title': 'Nouvelle campagne',
                'description': 'La campagne "Newsletter mensuelle" a été créée',
                'time': 'Il y a 5h'
            }
        ]

        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'user/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'user/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

class ContactsView(LoginRequiredMixin, TemplateView):
    template_name = 'user/contacts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
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
