# import os
# from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI
# from langchain_community.tools.tavily_search import TavilySearchResults

# load_dotenv()

# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
# search_tool = TavilySearchResults(max_results=5)

# query = "Latest updates in LangGraph in 2026"
# search_results = search_tool.invoke({"query": query})

# prompt = f"Summarize these web search results:\n\n{search_results}"
# response = llm.invoke(prompt)

# print("=== Search Results ===")
# print(search_results)
# print("\n=== LLM Summary ===")
# print(response.content)