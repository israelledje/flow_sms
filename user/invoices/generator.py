from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import os
from datetime import datetime
from decimal import Decimal

class InvoiceGenerator:
    def __init__(self, transaction):
        self.transaction = transaction
        self.user = transaction.user
        self.output_path = os.path.join(settings.MEDIA_ROOT, 'invoices')
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        
        self.filename = f"facture_{transaction.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        self.full_path = os.path.join(self.output_path, self.filename)
        
        # Configuration des styles
        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1e40af')  # Bleu royal
        ))
        
    def generate(self):
        # Création du document
        doc = SimpleDocTemplate(
            self.full_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Contenu du document
        story = []
        
        # En-tête avec logo
        logo_path = os.path.join(settings.STATIC_ROOT, 'img', 'logo.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=180, height=60)
            story.append(img)
        
        # Informations de l'entreprise
        story.append(Spacer(1, 20))
        story.append(Paragraph("Résonance Multiservices Sarl", self.styles['Heading1']))
        story.append(Paragraph("NIU : M082179512599", self.styles['Normal']))
        story.append(Paragraph("Tel : +237 694 58 15 00 / +237 242 98 35 97", self.styles['Normal']))
        
        # Informations de facturation
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"FACTURE N° : {self.transaction.id}", self.styles['CustomTitle']))
        story.append(Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y')}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Informations du client
        story.append(Paragraph("Informations client :", self.styles['Heading2']))
        story.append(Paragraph(f"Nom : {self.user.get_full_name() or self.user.username}", self.styles['Normal']))
        story.append(Paragraph(f"Email : {self.user.email}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Détails de la transaction
        data = [
            ['Description', 'Quantité', 'Prix unitaire', 'Total'],
            [
                'Crédits SMS',
                str(self.transaction.amount),
                f"{self.transaction.price / self.transaction.amount:.2f} FCFA",
                f"{self.transaction.price} FCFA"
            ]
        ]
        
        # Si un code promo a été utilisé
        if self.transaction.promo_code:
            original_price = self.transaction.price / (1 - self.transaction.promo_code.discount_percentage / 100)
            discount_amount = original_price - self.transaction.price
            data.append(['Réduction code promo', '', f"-{self.transaction.promo_code.discount_percentage}%", f"-{discount_amount:.2f} FCFA"])
        
        # Création du tableau
        table = Table(data, colWidths=[8*cm, 3*cm, 4*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Total
        story.append(Paragraph(f"Total : {self.transaction.price} FCFA", self.styles['Heading2']))
        
        # Pied de page
        story.append(Spacer(1, 40))
        story.append(Paragraph("Merci de votre confiance !", self.styles['Heading3']))
        story.append(Spacer(1, 10))
        story.append(Paragraph("Pour toute question concernant cette facture, veuillez nous contacter :", self.styles['Normal']))
        story.append(Paragraph("Email : contact@resonancetech.site", self.styles['Normal']))
        story.append(Paragraph("Tel : +237 694 58 15 00", self.styles['Normal']))
        
        # Génération du PDF
        doc.build(story)
        return self.filename 