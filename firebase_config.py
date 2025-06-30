import firebase_admin
from firebase_admin import credentials, firestore
import os

# Firebase configuration
# Replace these with your actual Firebase project credentials
FIREBASE_CONFIG =  {
  "type": "service_account",
  "project_id": "grad-proj-68c3e",
  "private_key_id": "738ef261c3750be9185c6e47eb0f8a3c456c5b70",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCp1nuiIq2XJGMH\n83rbBhZwElHIDDDqsH59SY1bP3Z7/y7/5lkog/CI3TYmyR33SEMVY3uYCrkj7K4H\ni/MZ1rumfk89au9h6MDRhI71vOchD3O+51/mHtyEHNtU+U/k+8gNx9cNik1WjBp+\ny+NlGUo/iCyGavMgsthUVGqLaeu2phnV86VXKM+aTEIkSLQcmBmCfWVGix8aEbSA\nPcesOYY2BE4xLnV1YmJa1e/uiUKvtTNb7A1YqJEMK0miHpcnWf4GndurynhSoM2Y\nlof+uhVw0UYSB9PbsUmcgQBsij89540tg02X1rMUEcyIjkpNY+3unhPNbZCaYTuW\n01TkyCjNAgMBAAECggEAAIiNwITHB8uo9fbuoq53tpK60rEwcXmWxBz4MS+srGyw\n60PVcYT3O0QlQzpBelaDQ2zEZXCvLoIz9Q5xooSj9+dl/KWP1T5ju09lGuIk1bE/\nO1EYYi15otPrtRjIBp+V0W6YadCj4orecG8tKn2fApO9FA+qQ3wxpWjTIYH2fWSH\nLMIQs7RmbN8zInn4C2VnD/CjmsD/wz8NWCvRLFHusyF4CrM3Okzl5Hu4zp9m1hRZ\nTDPDHFQRz58cfwxG5LZKIRNtuPdXgsyybb+ZnSrkOW2fjPoUmGKFQhV1arKvrdha\nyMXVGdPf9yrOto5Z/kv+7ZY+czv2iKIUbgX8wRozcQKBgQDnkwujkcrwSnRaw73Y\nTywWbQ/aUi0fGDZxzfrpJVT26xWgP+bwGV8gP79o+yj6pYKwSTqOjMG03EEbe2js\nfj95PB7C69vmmCyry9fMh9WY47KLvedCtoN7XFWB2htMbc4fk119bTX/2g/mMGoU\nfAzOMnvjqQbwWTLtRTdTqiwiFQKBgQC7wG5g/qiKm44Z8YPI5ly5fDMISg4seeYi\nSgCGDUqFQ6zBN6Tj3MoDpxJvTlKmyyi3CemyF1ZqJg/ClAZf1+4mOlwbyFnD7FvN\ngG1wghRMEBulD48rM/WpBDOT72CXXC8ISZM18+8a0Wb/Y3Y8DyAezYn+Nor7jH4I\nirdvmgRx2QKBgFnPjJ8GZwdkSNX+vj0LD5Uu/Qv1/OvnTw46DYqoYNhWeg+pWN5b\naKowLwL/DXiQAixuahho/KMxHMsUxK+bkvBo4aFFKga3k/OY3fvD3pIqFM/febZE\n5J9OQxdWSGoO1/clBwgi9+NfZfUnZ6zEI49Aww2bO0axwW+F/ZwkDnO1AoGAF673\nfX7CLfHfZABmOlJswe0b1uDYlt2tnQeutzo3+0WFJj5pq2CvjvRlS+saW/Xmpeg3\nNYLiILO6azYW88IeRW45LjwArslC71JS+8082Ddz9UdYLP/57h8cjn20toMnX6lA\nS58Au2ZM0sxuHrdduuT8kje5InAfed5ds1M/WkkCgYEAm+xeBbV5TpUJwaGbDeST\nV/ZXS8geCKprVoOdwQMg1kNLjl9fSk1FrLV1eRwKWjHJIMKl6BSAyQbwBSkQiEy9\nWTCHAMUALjshbYU1DZYLZMiE7WFkWx/CDDixxApLYuqlt98089y9Q3jgcJOz+way\nkiG6x4HHeFoHAdrSnTUHTLk=\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@grad-proj-68c3e.iam.gserviceaccount.com",
  "client_id": "101795253073668774334",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40grad-proj-68c3e.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}


# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK with credentials"""
    try:
        # Check if Firebase app is already initialized
        firebase_admin.get_app()
        print("Firebase already initialized")
        return firestore.client()
    except ValueError:
        # Initialize Firebase with credentials
        cred = credentials.Certificate(FIREBASE_CONFIG)
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully")
        return firestore.client()

# Get Firestore client
def get_firestore_client():
    """Get Firestore client instance"""
    return initialize_firebase()

# Firebase operations for users
def save_user_to_firebase(user_data):
    """Save user data to Firebase Firestore"""
    try:
        db = get_firestore_client()
        # Save to 'users' collection with user_id as document ID
        doc_ref = db.collection('users').document(str(user_data['id']))
        doc_ref.set({
            'username': user_data['username'],
            'email': user_data['email'],
            'password': user_data['password'],  # Plain text password (for testing)
            'created_at': user_data['created_at'],
            'last_login': user_data['last_login'],
            'failed_login_attempts': user_data['failed_login_attempts'],
            'is_active': user_data['is_active'],
            'verification_token': user_data['verification_token']
        })
        print(f"User {user_data['username']} saved to Firebase")
        return True
    except Exception as e:
        print(f"Error saving user to Firebase: {str(e)}")
        return False

def get_user_from_firebase(user_id):
    """Get user data from Firebase Firestore"""
    try:
        db = get_firestore_client()
        doc_ref = db.collection('users').document(str(user_id))
        doc = doc_ref.get()
        if doc.exists:
            user_data = doc.to_dict()
            user_data['id'] = int(user_id)
            return user_data
        return None
    except Exception as e:
        print(f"Error getting user from Firebase: {str(e)}")
        return None

def get_all_users_from_firebase():
    """Get all users from Firebase Firestore"""
    try:
        db = get_firestore_client()
        users_ref = db.collection('users')
        docs = users_ref.stream()
        users = []
        for doc in docs:
            user_data = doc.to_dict()
            user_data['id'] = int(doc.id)
            users.append(user_data)
        return users
    except Exception as e:
        print(f"Error getting users from Firebase: {str(e)}")
        return []

def update_user_in_firebase(user_data):
    """Update user data in Firebase Firestore"""
    try:
        db = get_firestore_client()
        doc_ref = db.collection('users').document(str(user_data['id']))
        doc_ref.update({
            'username': user_data['username'],
            'email': user_data['email'],
            'password': user_data['password'],
            'last_login': user_data['last_login'],
            'failed_login_attempts': user_data['failed_login_attempts'],
            'is_active': user_data['is_active'],
            'verification_token': user_data['verification_token']
        })
        print(f"User {user_data['username']} updated in Firebase")
        return True
    except Exception as e:
        print(f"Error updating user in Firebase: {str(e)}")
        return False

def delete_user_from_firebase(user_id):
    """Delete user from Firebase Firestore"""
    try:
        db = get_firestore_client()
        doc_ref = db.collection('users').document(str(user_id))
        doc_ref.delete()
        print(f"User {user_id} deleted from Firebase")
        return True
    except Exception as e:
        print(f"Error deleting user from Firebase: {str(e)}")
        return False 