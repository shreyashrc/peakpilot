import asyncio

from mcp.skills.gpx_skill import GPXSkill, TRAIL_GPX_DATA


def test_gpx_skill_known_trail():
	skill = GPXSkill()
	ctx = {"entities": {"trail": "Kedarkantha"}}
	res = asyncio.run(skill.execute(ctx))
	assert "gpx_data" in res and res["gpx_data"]["distance"]
	assert res["trail_map_url"].startswith("https://www.openstreetmap.org/")


def test_gpx_skill_unknown_trail():
	skill = GPXSkill()
	ctx = {"entities": {"trail": "Imaginary Peak"}}
	res = asyncio.run(skill.execute(ctx))
	assert "gpx_data" in res and res["gpx_data"]["distance"] == "-"
