"""
Common Mermaid syntax rules shared across all diagram types.
Import and use these instead of duplicating in every prompt.
"""

# Core syntax rules that apply to ALL Mermaid diagram types
COMMON_MERMAID_RULES = """
🎨 **VISUAL ENHANCEMENT**: Use emojis INSIDE labels (NOT in IDs) for visual clarity.

⚠️ **CRITICAL SYNTAX RULES**:

1. **Node IDs**: Simple alphanumeric only (a-z, A-Z, 0-9, underscore)
   - ✅ GOOD: user, processA, db1, apiGateway
   - ❌ BAD: user-input, api🔥, page-dashboard

2. **Reserved Keywords**: NEVER use as IDs: end, start, subgraph, graph, class, style, click
   - Use: startNode, endNode, beginFlow instead

3. **Text in Labels**: Plain ASCII characters only (keyboard chars)
   - ✅ GOOD: "SHA-256" (regular hyphen -)
   - ❌ BAD: "SHA‑256" (Unicode hyphen ‑)
   - ✅ GOOD: "User's data" (regular quote ')
   - ❌ BAD: "User's data" (smart quote ')
   - Emojis OK, but text must be ASCII

4. **No Styling**: Don't add style, class, classDef, click directives

5. **Output Format**:
   - ONLY Mermaid code
   - NO markdown fences (```mermaid)
   - NO explanations
   - Start with diagram type declaration

6. **Validation Checklist**:
   - ✓ Node IDs: alphanumeric only
   - ✓ No reserved keywords as IDs
   - ✓ Emojis in labels only
   - ✓ ASCII text characters only
"""

# Common emoji recommendations by category
EMOJI_GUIDE = """
🎨 **EMOJI GUIDE**:
- Start/End: 🎯 🏁 🚀 ✨
- User/Person: 👤 👥 👨‍💼 👩‍💼
- Process: ⚙️ 🔧 🔨 ⚡
- Decision: ❓ ⁉️ 🤔
- Success: ✅ 🎉 ✨ 👍
- Error: ❌ ⚠️ 🚫 ⛔
- Database: 💾 🗄️ 📊
- Network: 🌐 🔗 📡 🔌
- Security: 🔒 🔐 🛡️ 🔑
- Email: 📧 📬 🔔 📲
- File: 📄 📝 📋 📁
"""

def get_common_rules():
    """Returns common rules for all diagram types"""
    return COMMON_MERMAID_RULES

def get_emoji_guide():
    """Returns emoji recommendations"""
    return EMOJI_GUIDE

def get_full_common_section():
    """Returns complete common rules + emoji guide"""
    return COMMON_MERMAID_RULES + "\n" + EMOJI_GUIDE
