from typing import TypedDict, List, Dict, NotRequired


class LeadState(TypedDict):
    niche: NotRequired[str]
    countries: NotRequired[List[str]]
    iteration: NotRequired[int]
    queries: NotRequired[List[str]]
    raw_leads: NotRequired[List[Dict]]
    enriched_leads: NotRequired[List[Dict]]
    scored_leads: NotRequired[List[Dict]]
    scoring_summary: NotRequired[Dict]
    high_quality: NotRequired[List[Dict]]
    rejected: NotRequired[List[Dict]]
    emails: NotRequired[List[str]]