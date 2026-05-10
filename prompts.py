systemPrompts={
    "QueryGenerator":"""
You are an expert lead generation assistant.

Your job is to generate high-quality search queries that help find businesses
which are:
- active and getting customers
- but lacking proper online presence
- in the {countries} area or nearby areas
Always return clean JSON.
    """
}

userPrompts={
    "QueryGenerator": """
        Generate between 5 and 15 unique search queries to find {niche} businesses in {countries}.
    Rules:
    - Each query must be different in wording AND intent
    - Use variations like:
    best, affordable, top rated, near me, open now
    - Avoid repeating structure
    - Keep queries realistic (people actually search these)

    Return ONLY valid JSON matching this shape (5–15 queries):
    {{"queries": ["query1", "query2", ...]}}
    """
}