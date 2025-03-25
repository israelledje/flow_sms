from rest_framework import serializers
from campaigns.models import SenderId, Contact, Campaign, Message
from django.conf import settings
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'phone_number']
        
    def validate_phone_number(self, value):
        try:
            parsed = parse(value, None)
            if not is_valid_number(parsed):
                raise serializers.ValidationError('Numéro de téléphone invalide')
            return value
        except:
            raise serializers.ValidationError('Format de numéro incorrect')

class SenderIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = SenderId
        fields = ['id', 'name', 'status', 'created_at', 'updated_at']
        read_only_fields = ['status', 'created_at', 'updated_at']

class MessageSerializer(serializers.ModelSerializer):
    contact = ContactSerializer()
    
    class Meta:
        model = Message
        fields = ['id', 'contact', 'content', 'status', 'sent_at', 'delivered_at', 'message_id', 'error_description']
        read_only_fields = ['status', 'sent_at', 'delivered_at', 'message_id', 'error_description']

class SMSSerializer(serializers.Serializer):
    sender_id = serializers.CharField(max_length=11)
    message = serializers.CharField()
    phone_numbers = serializers.ListField(
        child=serializers.CharField(max_length=15),
        min_length=1
    )
    schedule_time = serializers.DateTimeField(required=False)
    
    def validate_sender_id(self, value):
        user = self.context.get('request').user
        try:
            sender = SenderId.objects.get(name=value, user=user)
            if sender.status != 'approved':
                raise serializers.ValidationError(
                    f"Le Sender ID '{value}' n'est pas approuvé. Statut actuel: {sender.get_status_display()}"
                )
            return value
        except SenderId.DoesNotExist:
            raise serializers.ValidationError(f"Le Sender ID '{value}' n'existe pas ou ne vous appartient pas")
    
    def validate_phone_numbers(self, value):
        valid_numbers = []
        invalid_numbers = []
        
        for phone_number in value:
            try:
                parsed = parse(phone_number, None)
                if is_valid_number(parsed):
                    valid_numbers.append(phone_number)
                else:
                    invalid_numbers.append(phone_number)
            except:
                invalid_numbers.append(phone_number)
        
        if invalid_numbers:
            raise serializers.ValidationError(
                f"Les numéros suivants sont invalides: {', '.join(invalid_numbers)}"
            )
        
        return value
