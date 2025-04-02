from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, PromoCode, SenderID, CreditTransaction

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'nom', 'prenom', 'telephone', 'account_type', 
                   'user_type', 'verification_status', 'credits', 'date_creation')
    list_filter = ('account_type', 'user_type', 'verification_status', 'is_active', 
                  'is_staff', 'date_creation')
    search_fields = ('username', 'email', 'nom', 'prenom', 'telephone')
    ordering = ('-date_creation',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Informations personnelles'), {'fields': (
            'nom', 'prenom', 'email', 'telephone', 'nationalite', 'adresse', 
            'ville', 'pays', 'secteur_activite'
        )}),
        (_('Type et statut'), {'fields': (
            'account_type', 'user_type', 'verification_status'
        )}),
        (_('Informations entreprise'), {'fields': (
            'niu', 'rccm', 'logo', 'site_web', 'description', 'nombre_employes'
        )}),
        (_('Relations'), {'fields': ('revendeur', 'parrain')}),
        (_('Crédits et préférences'), {'fields': (
            'credits', 'langue', 'fuseau_horaire', 'notifications_sms', 
            'notifications_email'
        )}),
        (_('Permissions'), {'fields': (
            'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
        )}),
        (_('Dates importantes'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'is_active', 'valid_from', 
                   'valid_until', 'max_uses', 'current_uses')
    list_filter = ('is_active', 'valid_from', 'valid_until')
    search_fields = ('code',)
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('code', 'discount_percentage')}),
        (_('Validité'), {'fields': ('is_active', 'valid_from', 'valid_until')}),
        (_('Utilisation'), {'fields': ('max_uses', 'current_uses')}),
    )

@admin.register(SenderID)
class SenderIDAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'is_default', 'date_creation', 
                   'date_approbation')
    list_filter = ('status', 'is_default', 'date_creation')
    search_fields = ('name', 'user__username', 'user__email')
    ordering = ('-date_creation',)
    
    fieldsets = (
        (None, {'fields': ('user', 'name', 'description')}),
        (_('Statut'), {'fields': ('status', 'is_default', 'rejection_reason')}),
        (_('Dates'), {'fields': ('date_approbation',)}),
    )

@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'transaction_type', 'amount', 'status', 
                   'payment_method', 'created_at')
    list_filter = ('transaction_type', 'status', 'payment_method', 'created_at')
    search_fields = ('reference', 'user__username', 'user__email')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('user', 'transaction_type', 'amount', 'price')}),
        (_('Paiement'), {'fields': ('payment_method', 'promo_code', 'status')}),
        (_('Détails'), {'fields': ('reference', 'description')}),
    )
    
    readonly_fields = ('reference',)
