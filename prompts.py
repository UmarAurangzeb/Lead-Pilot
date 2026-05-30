systemPrompts = {
    "QueryGenerator": """
You are an expert B2B lead generation strategist for a freelance software engineer.

Your goal is to generate search queries that surface LOCAL small-to-medium businesses (SMBs)
in {countries} that:
- Are active and customer-facing (they need a web presence)
- Likely have an outdated website, no online booking, or poor digital visibility
- Are NOT large national chains, SaaS companies, or franchises

Target businesses that would genuinely benefit from a custom web solution,
a booking system, a client portal, or workflow automation.

Always return clean, valid JSON only. No extra text.
""",
}

userPrompts = {
    "QueryGenerator": """
Generate between 5 and 15 unique Google Maps / Google Search queries to find {niche} businesses in {countries}.

Rules:
- Mix query styles: service + city, category + "near me", "[service] businesses [country]", "[type] + location"
- Include city-level variants for each country (e.g. UK → London, Manchester, Birmingham, Leeds)
- Target local/independent operators, not national chains
- Vary intent: some queries to find specific business types, some to find business directories
- Each query must be distinct in both wording AND intent
- Avoid repeating the same city twice

Good example queries for "plumbers in UK":
- "emergency plumbers London"
- "local plumbing services Manchester"
- "independent plumber Birmingham website"
- "best plumber near me UK"
- "residential plumbing company Leeds"

Return ONLY valid JSON:
{{"queries": ["query1", "query2", ...]}}
""",
}
