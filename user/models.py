from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
import pytz

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
