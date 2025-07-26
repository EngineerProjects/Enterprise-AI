#!/usr/bin/env python3
"""
Enterprise AI - Email vs @Mention Test

Tests that the mention parser correctly distinguishes between:
- Email addresses (sarah@gmail.com) 
- Agent mentions (@sarah)
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enterprise_ai.team.communication.mentions import MentionParser

def test_email_vs_mention_parsing():
    """Test that email addresses don't get parsed as agent mentions."""
    
    print("🧪 Testing Email vs @Mention Parsing")
    print("=" * 60)
    
    parser = MentionParser()
    parser.update_valid_agents(["sarah", "alex", "jordan", "maya"])
    
    test_cases = [
        # Valid agent mentions (should be detected)
        ("@sarah can you help with this?", ["sarah"], "Valid agent mention"),
        ("Hey @alex and @jordan, thoughts?", ["alex", "jordan"], "Multiple agent mentions"),
        ("@team meeting at 3pm", ["team"], "Team broadcast"),
        ("I think @sarah is right about this", ["sarah"], "Mid-sentence mention"),
        
        # Email addresses (should NOT be detected as mentions)
        ("Contact sarah@gmail.com for details", [], "Email address - no mentions"),
        ("Send reports to team@company.org", [], "Email with team name"),
        ("My email is alex@domain.co.uk", [], "Email with agent name"),
        ("Visit https://sarah@website.com/path", [], "URL with @ symbol"),
        
        # Mixed content (should only detect agent mentions)
        ("@sarah, email me at alex@gmail.com", ["sarah"], "Agent mention + email"),
        ("Email sarah@gmail.com or ping @jordan", ["jordan"], "Email + agent mention"),
        ("@alex @jordan, contact team@company.org", ["alex", "jordan"], "Multiple mentions + email"),
        
        # Edge cases
        ("sarah@gmail.com @sarah different things", ["sarah"], "Email followed by mention"),
        ("@sarah sarah@gmail.com are different", ["sarah"], "Mention followed by email"),
        ("user@domain.org and @team are not the same", ["team"], "Email and team mention"),
    ]
    
    print(f"\n🔍 Testing {len(test_cases)} cases:")
    print("-" * 60)
    
    all_passed = True
    
    for i, (message, expected_mentions, description) in enumerate(test_cases, 1):
        print(f"\n{i:2d}. {description}")
        print(f"    Input: '{message}'")
        
        # Parse the message
        parsed = parser.parse_message(message)
        actual_mentions = parsed.mentioned_agents
        
        # Check if parsing is correct
        if set(actual_mentions) == set(expected_mentions):
            print(f"    ✅ PASS: Found mentions: {actual_mentions}")
        else:
            print(f"    ❌ FAIL: Expected {expected_mentions}, got {actual_mentions}")
            all_passed = False
        
        # Show validation
        if parsed.has_mentions:
            valid, invalid = parser.validate_mentions(parsed)
            print(f"    📋 Validation: Valid={valid}, Invalid={invalid}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Email addresses are correctly ignored")
        print("✅ Agent mentions are correctly detected")
        print("✅ Mixed content is handled properly")
    else:
        print("❌ SOME TESTS FAILED!")
        print("💡 Check the regex pattern and parsing logic")
    
    print("\n🔬 Technical Details:")
    print(f"📝 Regex pattern: {parser.MENTION_PATTERN.pattern}")
    print("📝 Pattern explanation: (?<![a-zA-Z0-9])@([a-zA-Z0-9_]+)")
    print("   - (?<![a-zA-Z0-9]): Negative lookbehind - @ not preceded by alphanumeric")
    print("   - @: Literal @ symbol")
    print("   - ([a-zA-Z0-9_]+): Capture group for agent name")
    print("   - This prevents matching emails like sarah@gmail.com")

if __name__ == "__main__":
    test_email_vs_mention_parsing()
