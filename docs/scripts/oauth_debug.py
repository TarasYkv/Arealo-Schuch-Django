#!/usr/bin/env python3
"""
OAuth Configuration Diagnostic Tool
Run: python manage.py shell < oauth_debug.py
"""

from accounts.models import ZohoAPISettings
from django.contrib.auth import get_user_model
import requests

User = get_user_model()
user = User.objects.first()

print("=" * 60)
print("ZOHO OAUTH CONFIGURATION DIAGNOSTIC")
print("=" * 60)

try:
    settings = ZohoAPISettings.objects.get(user=user)
    
    print("✅ ZohoAPISettings found")
    print(f"Region: {settings.region}")
    print(f"Client ID: {settings.client_id[:10]}..." if settings.client_id else "❌ No Client ID")
    print(f"Client Secret: {'✅ Set' if settings.client_secret else '❌ Not set'}")
    print(f"Redirect URI: {settings.redirect_uri}")
    
    print("\n" + "=" * 40)
    print("CHECKING ZOHO APP STATUS")
    print("=" * 40)
    
    # Test if we can reach the auth endpoint
    auth_url = f"{settings.auth_url}?response_type=code&client_id={settings.client_id}&redirect_uri={settings.redirect_uri}&scope=ZohoMail.accounts.READ&state=test"
    
    try:
        response = requests.head(auth_url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            print("✅ Auth endpoint reachable")
        else:
            print(f"⚠️  Auth endpoint status: {response.status_code}")
    except Exception as e:
        print(f"❌ Auth endpoint error: {e}")
    
    print("\n" + "=" * 40)
    print("COMMON ISSUES TO CHECK:")
    print("=" * 40)
    print("1. ✅ Zoho Console > Your App > Client Details")
    print("   - Client ID matches:", settings.client_id)
    print("   - Client Secret is current (not regenerated)")
    print("")
    print("2. ✅ Zoho Console > Your App > Redirect URLs")
    print("   - Must contain exactly:", settings.redirect_uri)
    print("   - No trailing slash differences")
    print("")
    print("3. ✅ Zoho Console > Your App > Scopes")
    print("   - ZohoMail.accounts.READ")
    print("   - ZohoMail.folders.READ") 
    print("   - ZohoMail.messages.READ")
    print("   - ZohoMail.messages.CREATE")
    print("")
    print("4. ✅ Zoho Console > Your App > Status")
    print("   - App must be 'Published' or in 'Development'")
    print("   - Not 'Draft' or 'Rejected'")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("If issues persist:")
print("1. Regenerate Client Secret in Zoho Console")
print("2. Update ZohoAPISettings with new secret")  
print("3. Try OAuth flow again immediately")
print("=" * 60)