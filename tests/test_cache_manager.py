from utils.cache import CacheManager, QUESTION_CACHE, WEATHER_CACHE


def test_cache_basic_set_get_invalidate():
	c = CacheManager(max_entries=2)
	c.set("a", 1, ttl_minutes=1)
	c.set("b", 2, ttl_minutes=1)
	assert c.get("a") == 1
	assert c.get("b") == 2
	removed = c.invalidate(pattern="a")
	assert removed == 1
	assert c.get("a") is None


def test_cache_lru_eviction():
	c = CacheManager(max_entries=2)
	c.set("a", 1, ttl_minutes=10)
	c.set("b", 2, ttl_minutes=10)
	# Access 'a' to make it most-recent
	assert c.get("a") == 1
	# Insert 'c' -> should evict least recent 'b'
	c.set("c", 3, ttl_minutes=10)
	assert c.get("b") is None
	assert c.get("a") == 1 and c.get("c") == 3


def test_question_key_generation():
	c = CacheManager()
	k1 = c.generate_key_from_question(" Kedarkantha safe in December? ")
	k2 = c.generate_key_from_question("kedarkantha safe in december?")
	assert k1 == k2
