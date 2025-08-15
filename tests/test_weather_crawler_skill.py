import asyncio

from crawler.weather_crawler import WeatherCrawler
from mcp.skills.weather_skill import WeatherSkill


def test_weather_crawler_smoke():
	crawler = WeatherCrawler(rate_delay_seconds=0.0, ttl_minutes=1)
	data = asyncio.run(crawler.fetch_weather("Kedarkantha"))
	assert data["trail"] == "Kedarkantha"
	assert "forecast_date" in data
	assert "elevations" in data


def test_weather_skill_skips_when_not_needed():
	skill = WeatherSkill()
	ctx = {"entities": {"intent": "permits", "trail": "Kedarkantha"}}
	res = asyncio.run(skill.execute(ctx))
	assert "weather" not in res

