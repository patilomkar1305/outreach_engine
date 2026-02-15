"""
Quick test script to verify Gmail and Twilio tools work independently
Run this BEFORE testing the full workflow
"""
import logging
logging.basicConfig(level=logging.INFO)

print("=" * 60)
print("TESTING GMAIL TOOL")
print("=" * 60)
try:
    from app.tools.gmail_tool import send_gmail
    result = send_gmail(
        to="patilomkar2580@gmail.com",
        subject="🧪 Test Email from Outreach Engine",
        body="This is a test email to verify Gmail integration is working.\n\nIf you receive this, the setup is successful!"
    )
    print(f"✅ Gmail Result: {result}")
except Exception as e:
    print(f"❌ Gmail Error: {e}")
    print("   Note: First run will open browser for OAuth authentication")

print("\n" + "=" * 60)
print("TESTING TWILIO SMS TOOL")
print("=" * 60)
try:
    from app.tools.twilio_tool import send_sms
    result = send_sms(
        to_number="+919309843992",
        body="🧪 Test SMS from Outreach Engine. Setup works!"
    )
    print(f"✅ SMS Result: {result}")
except Exception as e:
    print(f"❌ SMS Error: {e}")

print("\n" + "=" * 60)
print("DONE - Check your email and phone!")
print("=" * 60)
