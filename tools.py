from langchain.tools import tool

from llm import chat_llm

@tool
def web_search(query: str) -> str:
    """Search the web for information"""
    return chat_llm.invoke(f"Search the web for information about {query}")