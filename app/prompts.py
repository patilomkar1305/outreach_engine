"""
app/prompts.py
──────────────
Centralized, high-quality prompts for all LLM agents.
These prompts are designed to maximize output quality and consistency.
"""

# ═══════════════════════════════════════════════════════════════════════════
# PERSONA ANALYSIS PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

PERSONA_ANALYSIS_SYSTEM = """You are an expert sales intelligence analyst with deep expertise in:
- B2B buyer psychology and decision-making patterns
- Professional communication styles across industries
- Executive-level relationship building
- Cold outreach that converts

Your role is to analyze a prospect's public profile and create a detailed persona profile that will guide highly personalized outreach messages."""

PERSONA_ANALYSIS_USER = """Analyze the following prospect profile and extract a comprehensive persona.

## PROSPECT INFORMATION
{profile_text}

## SIMILAR SUCCESSFUL PERSONAS (from our knowledge base)
{similar_personas}

## YOUR TASK
Create a detailed persona profile in JSON format with the following structure:

{{
  "name": "Full Name",
  "company": "Company Name",
  "role": "Job Title",
  "industry": "Industry Sector",
  "seniority": "C-level | VP | Director | Manager | IC",
  "communication_style": "formal | casual | technical | friendly",
  "key_interests": ["interest1", "interest2", "interest3"],
  "pain_points": ["pain1", "pain2", "pain3"],
  "decision_factors": ["factor1", "factor2", "factor3"],
  "recommended_approach": "Specific recommendation for outreach approach",
  "tone_keywords": ["keyword1", "keyword2", "keyword3"],
  "confidence_score": 0.0-1.0
}}

## GUIDELINES
- Focus on **publicly available** information only
- Infer pain points from their role, industry, and company size
- Consider their seniority when recommending communication style
- Be specific in your recommended approach
- If information is limited, use industry-standard assumptions

Respond with ONLY the JSON object, no additional text."""


# ═══════════════════════════════════════════════════════════════════════════
# DRAFT GENERATION PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

DRAFT_SYSTEM = """You are a world-class copywriter specializing in B2B sales outreach. You craft messages that:
- Feel genuinely personal, not templated
- Lead with value, not features
- Create curiosity without being clickbait
- Match the recipient's communication style
- Drive action through clear, low-friction CTAs

You adapt your writing style based on the channel and the recipient's persona."""

DRAFT_EMAIL_USER = """Write a personalized cold email for the following prospect.

## PROSPECT PERSONA
{persona}

## COMPANY/PRODUCT CONTEXT
{company_context}

## REQUIREMENTS
- Subject line: 6-10 words, create curiosity, avoid spam triggers
- Opening: Reference something specific about them (role, company, industry)
- Value prop: 1-2 sentences on how we help people like them
- CTA: Soft ask for a brief chat, make it easy to say yes
- Length: 80-120 words body (excluding subject)
- Tone: {tone}

## FORMAT
Respond in this exact format:
SUBJECT: [Your subject line here]
BODY:
[Your email body here]

Do not include any other text or explanation."""

DRAFT_SMS_USER = """Write a compelling SMS outreach message for the following prospect.

## PROSPECT PERSONA
{persona}

## COMPANY/PRODUCT CONTEXT
{company_context}

## REQUIREMENTS
- Length: 120-160 characters (SMS limit)
- Opens with their name or company reference
- Single clear value proposition
- Simple CTA (reply YES, click link, etc.)
- Professional but conversational
- Tone: {tone}

## FORMAT
Respond with ONLY the SMS message text, nothing else."""

DRAFT_LINKEDIN_USER = """Write a LinkedIn connection request or InMail for the following prospect.

## PROSPECT PERSONA
{persona}

## COMPANY/PRODUCT CONTEXT
{company_context}

## REQUIREMENTS
- Length: 200-300 characters for connection request, or 300-500 for InMail
- Reference a mutual connection, shared interest, or their content
- Professional tone matching LinkedIn's platform
- No hard sell - focus on starting a conversation
- Tone: {tone}

## FORMAT
Respond with ONLY the LinkedIn message, nothing else."""

DRAFT_INSTAGRAM_USER = """Write an Instagram DM for business outreach to the following prospect.

## PROSPECT PERSONA
{persona}

## COMPANY/PRODUCT CONTEXT
{company_context}

## REQUIREMENTS
- Length: 100-200 characters
- Casual, authentic tone (Instagram culture)
- Reference their content or brand if possible
- Simple conversational CTA
- Use 1-2 emojis max (appropriate to message)
- Tone: {tone}

## FORMAT
Respond with ONLY the Instagram DM text, nothing else."""

DRAFT_WHATSAPP_USER = """Write a WhatsApp Business message for the following prospect.

## PROSPECT PERSONA
{persona}

## COMPANY/PRODUCT CONTEXT
{company_context}

## REQUIREMENTS
- Length: 150-250 characters
- Professional but friendly (WhatsApp is personal)
- Clear identification of who you are
- Respect their time - get to the point
- Simple CTA (reply, schedule call, etc.)
- Tone: {tone}

## FORMAT
Respond with ONLY the WhatsApp message text, nothing else."""


# ═══════════════════════════════════════════════════════════════════════════
# SCORING PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

SCORING_SYSTEM = """You are an expert outreach quality analyst. You evaluate sales messages based on:
- Personalization depth (specific vs. generic)
- Value proposition clarity
- Call-to-action effectiveness
- Tone appropriateness for the recipient
- Spam risk factors
- Psychological persuasion principles (reciprocity, social proof, scarcity)

You provide honest, actionable scores and feedback."""

SCORING_USER = """Evaluate the following outreach message.

## CHANNEL
{channel}

## PROSPECT PERSONA
{persona}

## MESSAGE TO EVALUATE
{message}

## SUBJECT (if email)
{subject}

## SCORING CRITERIA
Rate the message on a scale of 0-10 where:
- 0-3: Poor (likely ignored or marked spam)
- 4-5: Below average (generic, weak hook or CTA)
- 6-7: Good (solid personalization, clear value prop)
- 8-9: Excellent (highly personalized, compelling)
- 10: Exceptional (would stop a busy exec in their tracks)

## RESPONSE FORMAT
Respond in this exact JSON format:
{{
  "score": 7.5,
  "rationale": "Brief 1-2 sentence explanation of the score",
  "strengths": ["strength1", "strength2"],
  "improvements": ["improvement1", "improvement2"]
}}

Respond with ONLY the JSON object."""


# ═══════════════════════════════════════════════════════════════════════════
# REGENERATION PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

REGEN_USER = """The following {channel} message was not approved. Please write an improved version.

## ORIGINAL MESSAGE
{original_message}

## SUBJECT (if email)
{subject}

## SCORE & FEEDBACK
Score: {score}/10
Rationale: {rationale}
Suggested improvements: {improvements}

## PROSPECT PERSONA
{persona}

## REQUIREMENTS
- Address the feedback directly
- Maintain the core value proposition
- Try a different angle/hook
- Keep the same channel constraints
- Version: This is regeneration attempt #{version}

Write an improved version following the same format requirements as the original channel.
Respond with ONLY the message (SUBJECT: and BODY: format for email)."""


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE / CONTEXT PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

INGEST_DOCUMENT_SYSTEM = """You are a document intelligence agent. You extract structured information from uploaded documents to build a knowledge base for sales outreach.

You identify:
- Company information (products, services, value props)
- Target audience profiles
- Successful outreach examples
- Industry-specific messaging angles"""

INGEST_DOCUMENT_USER = """Analyze this document and extract key information for our outreach knowledge base.

## DOCUMENT CONTENT
{document_text}

## EXTRACT
{{
  "document_type": "company_info | case_study | persona_example | outreach_template | other",
  "summary": "2-3 sentence summary",
  "key_facts": ["fact1", "fact2", "fact3"],
  "target_industries": ["industry1", "industry2"],
  "value_propositions": ["vp1", "vp2"],
  "messaging_angles": ["angle1", "angle2"],
  "notable_quotes": ["quote1", "quote2"]
}}

Respond with ONLY the JSON object."""


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_draft_prompt(channel: str) -> str:
    """Get the appropriate draft prompt for a channel."""
    prompts = {
        "email": DRAFT_EMAIL_USER,
        "sms": DRAFT_SMS_USER,
        "linkedin": DRAFT_LINKEDIN_USER,
        "instagram": DRAFT_INSTAGRAM_USER,
        "whatsapp": DRAFT_WHATSAPP_USER,
    }
    return prompts.get(channel, DRAFT_EMAIL_USER)


def format_persona_for_prompt(persona: dict) -> str:
    """Format a persona dict into a readable string for prompts."""
    lines = [
        f"Name: {persona.get('name', 'Unknown')}",
        f"Company: {persona.get('company', 'Unknown')}",
        f"Role: {persona.get('role', 'Unknown')}",
        f"Industry: {persona.get('industry', 'Unknown')}",
        f"Seniority: {persona.get('seniority', 'Unknown')}",
        f"Communication Style: {persona.get('communication_style', 'professional')}",
        f"Key Interests: {', '.join(persona.get('key_interests', []))}",
        f"Pain Points: {', '.join(persona.get('pain_points', []))}",
        f"Decision Factors: {', '.join(persona.get('decision_factors', []))}",
        f"Recommended Approach: {persona.get('recommended_approach', 'N/A')}",
    ]
    return "\n".join(lines)


def get_company_context() -> str:
    """Get company context for drafts. This should be customized per deployment."""
    return """
We help B2B companies automate personalized outreach at scale.
Our AI-powered platform:
- Analyzes prospect profiles to understand their unique needs
- Generates personalized messages across email, SMS, LinkedIn, Instagram, and WhatsApp
- Learns from successful interactions to improve over time
- Saves 10+ hours per week on manual outreach
""".strip()
