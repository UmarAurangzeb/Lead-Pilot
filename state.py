from typing import TypedDict, List, Dict, NotRequired


class LeadState(TypedDict):
    niche: NotRequired[str]
    countries: NotRequired[List[str]]
    queries: List[str]
    raw_leads: List[Dict]
    enriched_leads: List[Dict]
    scored_leads: List[Dict]
    high_quality: List[Dict]
    rejected: List[Dict]
    emails: List[str]
    iterations: int