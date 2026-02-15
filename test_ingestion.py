"""
Test ingestion agent to verify email/phone extraction works
"""
from app.agents.ingestion_agent import ingestion_node
from app.graph.state import OutreachState

# Test with a profile that has email and phone
test_input = """
John Doe
VP of Engineering at TechCorp
Email: johndoe@techcorp.com
Phone: +1-555-123-4567
LinkedIn: https://linkedin.com/in/johndoe
"""

state: OutreachState = {
    "raw_input": test_input
}

result = ingestion_node(state)

print("=" * 60)
print("INGESTION TEST RESULTS")
print("=" * 60)
print(f"Name:     {result.get('target_name')}")
print(f"Company:  {result.get('company')}")
print(f"Role:     {result.get('role')}")
print(f"Industry: {result.get('industry')}")
print(f"\nExtracted Links:")
for channel, value in result.get('links', {}).items():
    print(f"  {channel:12s}: {value}")

print("\n✅ Email extracted:", "email" in result.get('links', {}))
print("✅ Phone extracted:", "phone" in result.get('links', {}))
print("\nIf email/phone are missing, fallback will use:")
print(f"  Email: patilomkar2580@gmail.com")
print(f"  Phone: +919309843992")
