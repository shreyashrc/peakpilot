from typing import Any, Dict, List

import aiohttp


async def fetch_wikivoyage_page(base_url: str, title: str) -> str:
    url = f"{base_url}{title}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            resp.raise_for_status()
            return await resp.text()


async def extract_wikivoyage_content(html: str) -> List[Dict[str, Any]]:
    # TODO: parse with BeautifulSoup and extract sections
    return [{"source": "wikivoyage", "content": html[:1000]}]
