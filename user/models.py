from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
import pytz
from django.utils import timezone
from decimal import Decimal
import logging
from threading import Thread

# Configuration du logger
logger = logging.getLogger(__name__)

class User(AbstractUser):
    class AccountTypes(models.TextChoices):
        ENTREPRISE = "ENTREPRISE", "Entreprise"
        PARTICULIER = "PARTICULIER", "Particulier"

    class UserTypes(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        SUPPORT = "SUPPORT", "Support"
        REVENDEUR = "REVENDEUR", "Revendeur"
        CLIENT = "CLIENT", "Client"

    class VerificationStatus(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        VERIFIE = "VERIFIE", "Vérifié"
        REJETE = "REJETE", "Rejeté"

    # Type et statut
    account_type = models.CharField(
        _("Type de compte"), max_length=50, choices=AccountTypes.choices, default=AccountTypes.PARTICULIER
    )
    user_type = models.CharField(
        _("Type d'utilisateur"), max_length=50, choices=UserTypes.choices, default=UserTypes.CLIENT
    )
    verification_status = models.CharField(
        _("Statut de vérification"), max_length=50, choices=VerificationStatus.choices, default=VerificationStatus.EN_ATTENTE
    )

    # Informations personnelles
    nom = models.CharField(_("Nom"), max_length=100)
    prenom = models.CharField(_("Prénom"), max_length=100)
    phone_regex = RegexValidator(
        regex=r'^\+237[6]\d{8}$',
        message="Le numéro de téléphone doit être au format: '+237 6XX XXX XXX' (9 chiffres après +237)"
    )
    telephone = models.CharField(
        _("Téléphone"), validators=[phone_regex], max_length=17
    )
    nationalite = models.CharField(_("Nationalité"), max_length=100)
    adresse = models.TextField(_("Adresse physique"), blank=True)
    ville = models.CharField(_("Ville"), max_length=100)
    pays = models.CharField(_("Pays"), max_length=100)

    # Informations professionnelles
    secteur_activite = models.CharField(_("Secteur d'activité"), max_length=200)
    niu = models.CharField(_("NIU"), max_length=100, blank=True, null=True)
    rccm = models.CharField(_("RCCM"), max_length=100, blank=True, null=True)

    # Champs spécifiques entreprise
    logo = models.ImageField(_("Logo"), upload_to='logos/', blank=True, null=True)
    site_web = models.URLField(_("Site web"), blank=True, null=True)
    description = models.TextField(_("Description de l'entreprise"), blank=True, null=True)
    nombre_employes = models.PositiveIntegerField(_("Nombre d'employés"), blank=True, null=True)

    # Relations
    revendeur = models.ForeignKey(
        'self', 
        verbose_name=_("Revendeur"),
        on_delete=models.SET_NULL,
        related_name='clients',
        null=True,
        blank=True,
        limit_choices_to={'user_type': UserTypes.REVENDEUR}
    )
    parrain = models.ForeignKey(
        'self',
        verbose_name=_("Parrain"),
        on_delete=models.SET_NULL,
        related_name='parraines',
        null=True,
        blank=True
    )

    # Préférences
    TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]
    LANGUAGE_CHOICES = [
        ('fr', _('Français')),
        ('en', _('Anglais')),
    ]

    langue = models.CharField(
        _("Langue préférée"),
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='fr'
    )
    fuseau_horaire = models.CharField(
        _("Fuseau horaire"),
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='UTC'
    )
    notifications_sms = models.BooleanField(_("Notifications SMS"), default=True)
    notifications_email = models.BooleanField(_("Notifications email"), default=True)

    # Gestion des crédits
    credits = models.DecimalField(
        _("Crédits SMS"),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Solde de crédits SMS disponibles")
    )

    # Métadonnées
    date_creation = models.DateTimeField(_("Date de création"), auto_now_add=True)
    date_modification = models.DateTimeField(_("Dernière modification"), auto_now=True)

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering = ['-date_creation']

    def __str__(self):
        if self.account_type == self.AccountTypes.ENTREPRISE:
            return f"{self.nom} (Entreprise - {self.get_user_type_display()})"
        return f"{self.nom} {self.prenom} ({self.get_user_type_display()})"

    def save(self, *args, **kwargs):
        if self.account_type == self.AccountTypes.PARTICULIER:
            # Réinitialiser les champs spécifiques aux entreprises
            self.niu = None
            self.rccm = None
            self.logo = None
            self.site_web = None
            self.description = None
            self.nombre_employes = None
        super().save(*args, **kwargs)

    @property
    def is_verified(self):
        return self.verification_status == self.VerificationStatus.VERIFIE

    def add_credits(self, amount):
        """Ajoute des crédits au compte de l'utilisateur."""
        self.credits += amount
        self.save()

    def deduct_credits(self, amount):
        """Déduit des crédits du compte de l'utilisateur."""
        if self.credits >= amount:
            self.credits -= amount
            self.save()
            return True
        return False

    def has_sufficient_credits(self, amount):
        """Vérifie si l'utilisateur a suffisamment de crédits."""
        return self.credits >= amount


class PromoCode(models.Model):
    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        help_text=_("Code promo unique")
    )
    discount_percentage = models.DecimalField(
        _("Pourcentage de réduction"),
        max_digits=5,
        decimal_places=2,
        help_text=_("Pourcentage de réduction à appliquer")
    )
    is_active = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_("Indique si le code promo est actif")
    )
    valid_from = models.DateTimeField(
        _("Valide à partir de"),
        help_text=_("Date de début de validité")
    )
    valid_until = models.DateTimeField(
        _("Valide jusqu'au"),
        help_text=_("Date de fin de validité")
    )
    max_uses = models.PositiveIntegerField(
        _("Utilisations maximales"),
        null=True,
        blank=True,
        help_text=_("Nombre maximum d'utilisations (laissez vide pour illimité)")
    )
    current_uses = models.PositiveIntegerField(
        _("Utilisations actuelles"),
        default=0,
        help_text=_("Nombre d'utilisations actuelles")
    )
    created_at = models.DateTimeField(_("Date de création"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Date de modification"), auto_now=True)

    class Meta:
        verbose_name = _("Code promo")
        verbose_name_plural = _("Codes promo")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.discount_percentage}%)"

    def is_valid(self):
        """Vérifie si le code promo est valide."""
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_until and
            (self.max_uses is None or self.current_uses < self.max_uses)
        )

    def apply_discount(self, amount):
        """Applique la réduction au montant."""
        if not self.is_valid():
            return amount
        amount = Decimal(str(amount))
        discount = amount * (self.discount_percentage / Decimal('100'))
        return amount - discount

    def increment_usage(self):
        """Incrémente le compteur d'utilisations."""
        if self.max_uses is not None:
            self.current_uses += 1
            self.save()


class SenderID(models.Model):
    class Status(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        APPROUVE = "APPROUVE", "Approuvé"
        REJETE = "REJETE", "Rejeté"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sender_ids',
        verbose_name=_("Utilisateur")
    )
    name = models.CharField(
        _("Nom"), 
        max_length=11,
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z0-9]+$',
                message="Le Sender ID ne doit contenir que des lettres et des chiffres"
            )
        ]
    )
    description = models.TextField(_("Description"), blank=True)
    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=Status.choices,
        default=Status.EN_ATTENTE
    )
    is_default = models.BooleanField(_("Par défaut"), default=False)
    rejection_reason = models.TextField(_("Raison du rejet"), blank=True)
    
    # Métadonnées
    date_creation = models.DateTimeField(_("Date de création"), auto_now_add=True)
    date_modification = models.DateTimeField(_("Date de modification"), auto_now=True)
    date_approbation = models.DateTimeField(_("Date d'approbation"), null=True, blank=True)

    class Meta:
        verbose_name = _("Sender ID")
        verbose_name_plural = _("Sender IDs")
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_sender_id_per_user'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Convertir le nom en majuscules
        self.name = self.name.upper()
        
        # Si c'est le premier Sender ID de l'utilisateur, le définir par défaut
        if not self.pk and not SenderID.objects.filter(user=self.user).exists():
            self.is_default = True
        
        # Si ce Sender ID est défini par défaut, retirer le statut par défaut des autres
        if self.is_default:
            SenderID.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)


class CreditTransaction(models.Model):
    class TransactionType(models.TextChoices):
        PURCHASE = "PURCHASE", "Achat"
        USAGE = "USAGE", "Utilisation"
        REFUND = "REFUND", "Remboursement"

    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = "CREDIT_CARD", "Carte de crédit"
        ORANGE_MONEY = "ORANGE_MONEY", "Orange Money"
        MTN_MONEY = "MTN_MONEY", "MTN Mobile Money"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='credit_transactions',
        verbose_name=_("Utilisateur")
    )
    transaction_type = models.CharField(
        _("Type de transaction"),
        max_length=20,
        choices=TransactionType.choices
    )
    amount = models.DecimalField(
        _("Montant"),
        max_digits=10,
        decimal_places=2
    )
    price = models.DecimalField(
        _("Prix"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Prix total de la transaction")
    )
    payment_method = models.CharField(
        _("Méthode de paiement"),
        max_length=20,
        choices=PaymentMethod.choices,
        null=True,
        blank=True
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Code promo"),
        help_text=_("Code promo appliqué à la transaction")
    )
    promo_discount = models.DecimalField(
        _("Réduction promo"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Pourcentage de réduction appliqué")
    )
    phone_number = models.CharField(
        _("Numéro de téléphone"),
        max_length=20,
        null=True,
        blank=True,
        help_text=_("Numéro de téléphone pour le paiement mobile")
    )
    pin = models.CharField(
        _("Code PIN"),
        max_length=10,
        null=True,
        blank=True,
        help_text=_("Code PIN pour le paiement mobile")
    )
    description = models.TextField(_("Description"), blank=True)
    reference = models.CharField(
        _("Référence"),
        max_length=100,
        unique=True,
        help_text=_("Référence unique de la transaction")
    )
    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=[
            ('PENDING', 'En attente'),
            ('COMPLETED', 'Complétée'),
            ('FAILED', 'Échouée'),
            ('REFUNDED', 'Remboursée')
        ],
        default='PENDING'
    )
    created_at = models.DateTimeField(_("Date de création"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Date de modification"), auto_now=True)

    class Meta:
        verbose_name = _("Transaction de crédits")
        verbose_name_plural = _("Transactions de crédits")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.get_transaction_type_display()} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.reference:
            # Générer une référence unique
            from datetime import datetime
            import random
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            self.reference = f"CRD-{timestamp}-{random_suffix}"
            logger.info(f"Génération d'une nouvelle référence de transaction: {self.reference}")

        if self.status == 'COMPLETED' and self.transaction_type == 'PURCHASE':
            # Ajouter les crédits au compte de l'utilisateur
            logger.info(f"Tentative d'ajout de {self.amount} crédits pour l'utilisateur {self.user.username}")
            self.user.add_credits(self.amount)
            logger.info(f"Crédits ajoutés avec succès. Nouveau solde: {self.user.credits}")
        elif self.status == 'COMPLETED' and self.transaction_type == 'REFUND':
            # Rembourser les crédits
            logger.info(f"Tentative de remboursement de {self.amount} crédits pour l'utilisateur {self.user.username}")
            self.user.add_credits(self.amount)
            logger.info(f"Remboursement effectué avec succès. Nouveau solde: {self.user.credits}")

        super().save(*args, **kwargs)
        logger.info(f"Transaction {self.reference} sauvegardée avec le statut {self.status}")

    def process_payment(self):
        """
        Traite le paiement et ajoute les crédits au compte de l'utilisateur
        """
        try:
            logger.info(f"Début du traitement du paiement pour la transaction {self.reference}")
            
            # Vérifier si la transaction a déjà été traitée
            if self.status == 'COMPLETED':
                logger.warning(f"Transaction {self.reference} déjà traitée")
                return True
                
            # Vérifier si la transaction a échoué
            if self.status == 'FAILED':
                logger.warning(f"Transaction {self.reference} déjà marquée comme échouée")
                return False
            
            # Simuler un paiement réussi
            self.status = 'COMPLETED'
            self.save()
            logger.info(f"Statut de la transaction {self.reference} mis à jour à COMPLETED")
            
            # Ajouter les crédits au compte de l'utilisateur
            logger.info(f"Tentative d'ajout de {self.amount} crédits pour l'utilisateur {self.user.username}")
            self.user.add_credits(self.amount)
            logger.info(f"Crédits ajoutés avec succès. Nouveau solde: {self.user.credits}")
            
            # Envoyer l'email de confirmation de manière asynchrone
            from django.core.mail import send_mail
            from django.conf import settings
            
            def send_confirmation_email():
                try:
                    subject = f'Confirmation d\'achat de crédits SMS - {self.amount} crédits'
                    message = f'''
                    Bonjour {self.user.username},
                    
                    Votre achat de {self.amount} crédits SMS a été traité avec succès.
                    Montant payé : {self.price} FCFA
                    Date : {self.created_at.strftime('%d/%m/%Y %H:%M')}
                    
                    Votre nouveau solde est de {self.user.credits} crédits.
                    
                    Merci de votre confiance,
                    L'équipe Flow SMS
                    '''
                    
                    logger.info(f"Tentative d'envoi d'email de confirmation à {self.user.email}")
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [self.user.email],
                        fail_silently=True,
                    )
                    logger.info("Email de confirmation envoyé avec succès")
                except Exception as e:
                    logger.error(f"Erreur lors de l'envoi de l'email: {str(e)}")
            
            # Démarrer l'envoi d'email dans un thread séparé
            email_thread = Thread(target=send_confirmation_email)
            email_thread.start()
            
            logger.info(f"Traitement du paiement terminé avec succès pour la transaction {self.reference}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du traitement du paiement pour la transaction {self.reference}: {str(e)}")
            self.status = 'FAILED'
            self.save()
            logger.error(f"Transaction {self.reference} marquée comme échouée")
            return False
