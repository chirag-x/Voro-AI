import logging
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def search_web(query: str, max_results: int = 3) -> str:
    logger.info(f'[tools] Searching web for: {query}')
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                return 'No real-time web results found for this query.'
                
            formatted_results = ['--- LIVE WEB SEARCH RESULTS ---']
            for idx, r in enumerate(results):
                title = r.get('title', 'No Title')
                body = r.get('body', '')
                href = r.get('href', '')
                formatted_results.append(f'[{idx+1}] {title}\nURL: {href}\nSnippet: {body}\n')
                
            return '\n'.join(formatted_results)
    except Exception as e:
        logger.error(f'[tools] Web search failed: {e}')
        return f'Live web search failed: {e}'
