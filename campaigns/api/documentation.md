# FLOW SMS API - Documentation

Cette API permet aux utilisateurs de la plateforme FLOW SMS d'intégrer facilement les fonctionnalités d'envoi de SMS dans leurs applications tierces.

## Authentification

L'API utilise JWT (JSON Web Tokens) pour l'authentification. Vous devez d'abord obtenir un token en vous authentifiant avec votre nom d'utilisateur et mot de passe.

### Obtenir un token

```
POST /campaigns/api/token/
```

**Corps de la requête:**
```json
{
    "username": "votre_nom_utilisateur",
    "password": "votre_mot_de_passe"
}
```

**Réponse:**
```json
{
    "access": "votre_token_access",
    "refresh": "votre_token_refresh"
}
```

### Rafraîchir un token

```
POST /campaigns/api/token/refresh/
```

**Corps de la requête:**
```json
{
    "refresh": "votre_token_refresh"
}
```

## Envoi de SMS

### Envoyer des SMS

```
POST /campaigns/api/send-sms/
```

**En-têtes:**
```
Authorization: Bearer votre_token_access
Content-Type: application/json
```

**Corps de la requête:**
```json
{
    "sender_id": "NomSenderID",
    "message": "Contenu de votre message",
    "phone_numbers": ["+33612345678", "+33687654321"],
    "schedule_time": "2025-04-01T12:00:00Z"  // Optionnel
}
```

**Notes:**
- `sender_id` doit être un Sender ID approuvé appartenant à votre compte
- `phone_numbers` doit contenir au moins un numéro de téléphone valide
- `schedule_time` est optionnel et permet de programmer l'envoi des SMS

**Réponse:**
```json
{
    "success": true,
    "campaign_id": 123,
    "messages_sent": 2,
    "messages_failed": 0,
    "failed_messages": [],
    "messages": [
        {
            "id": 1,
            "contact": {
                "id": 1,
                "phone_number": "+33612345678"
            },
            "content": "Contenu de votre message",
            "status": "sent",
            "sent_at": "2025-03-25T12:34:56Z",
            "delivered_at": null,
            "message_id": "api-message-id-123",
            "error_description": null
        },
        {
            "id": 2,
            "contact": {
                "id": 2,
                "phone_number": "+33687654321"
            },
            "content": "Contenu de votre message",
            "status": "sent",
            "sent_at": "2025-03-25T12:34:56Z",
            "delivered_at": null,
            "message_id": "api-message-id-456",
            "error_description": null
        }
    ]
}
```

## Gestion des Sender IDs

### Lister vos Sender IDs

```
GET /campaigns/api/senderids/
```

**En-têtes:**
```
Authorization: Bearer votre_token_access
```

### Créer un Sender ID

```
POST /campaigns/api/senderids/
```

**En-têtes:**
```
Authorization: Bearer votre_token_access
Content-Type: application/json
```

**Corps de la requête:**
```json
{
    "name": "NouveauID"
}
```

**Note:** Le nouveau Sender ID aura le statut "pending" (en attente d'approbation) jusqu'à validation par l'administrateur.

## Gestion des Contacts

### Lister vos Contacts

```
GET /campaigns/api/contacts/
```

**En-têtes:**
```
Authorization: Bearer votre_token_access
```

## Exemples d'intégration

### Exemple en Python

```python
import requests

# Configuration
API_BASE_URL = 'https://votredomaine.com/campaigns/api/'
USERNAME = 'votre_nom_utilisateur'
PASSWORD = 'votre_mot_de_passe'

# Authentification
def get_token():
    response = requests.post(f'{API_BASE_URL}token/', json={
        'username': USERNAME,
        'password': PASSWORD
    })
    return response.json()['access']

# Envoi de SMS
def send_sms(sender_id, message, phone_numbers):
    token = get_token()
    response = requests.post(
        f'{API_BASE_URL}send-sms/',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'sender_id': sender_id,
            'message': message,
            'phone_numbers': phone_numbers
        }
    )
    return response.json()

# Exemple d'utilisation
result = send_sms('MonSenderID', 'Votre message ici', ['+33612345678'])
print(result)
```

### Exemple en JavaScript

```javascript
// Configuration
const API_BASE_URL = 'https://votredomaine.com/campaigns/api/';
const USERNAME = 'votre_nom_utilisateur';
const PASSWORD = 'votre_mot_de_passe';

// Authentification
async function getToken() {
    const response = await fetch(`${API_BASE_URL}token/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: USERNAME,
            password: PASSWORD
        })
    });
    const data = await response.json();
    return data.access;
}

// Envoi de SMS
async function sendSMS(senderId, message, phoneNumbers) {
    const token = await getToken();
    const response = await fetch(`${API_BASE_URL}send-sms/`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            sender_id: senderId,
            message: message,
            phone_numbers: phoneNumbers
        })
    });
    return await response.json();
}

// Exemple d'utilisation
sendSMS('MonSenderID', 'Votre message ici', ['+33612345678'])
    .then(result => console.log(result))
    .catch(error => console.error(error));
```
