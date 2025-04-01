from django.core.mail import EmailMessage
from django.conf import settings
import os

class InvoiceSender:
    @staticmethod
    def send_invoice(user, invoice_filename):
        # Chemin complet vers la facture
        invoice_path = os.path.join(settings.MEDIA_ROOT, 'invoices', invoice_filename)
        
        # Création du message
        subject = 'Votre facture FLOW SMS'
        message = f"""Cher(e) {user.get_full_name() or user.username},

Nous vous remercions pour votre achat de crédits SMS sur FLOW SMS.

Vous trouverez ci-joint votre facture.

Pour toute question, n'hésitez pas à nous contacter.

Cordialement,
L'équipe FLOW SMS
Résonance Multiservices Sarl"""
        
        # Création de l'email
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        
        # Ajout de la pièce jointe
        if os.path.exists(invoice_path):
            with open(invoice_path, 'rb') as f:
                email.attach(invoice_filename, f.read(), 'application/pdf')
        
        # Envoi de l'email
        email.send() 