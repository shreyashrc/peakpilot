from rag.rag_skill import RAGSkill


def test_rag_skill_pipeline_smoke(tmp_path, monkeypatch):
	# Use a fresh store per test by redirecting persist dir
	import os
	os.environ['PWD'] = str(tmp_path)

	rag = RAGSkill()

	# Process simple docs
	ids = rag.process_documents([
		{"text": "Kedarkantha is a popular winter trek in Uttarakhand.", "source": "wikivoyage", "trail_name": "Kedarkantha", "section_type": "overview", "url": "https://example.com/ked"},
		{"text": "Triund near McLeod Ganj is beginner friendly.", "source": "wikivoyage", "trail_name": "Triund", "section_type": "overview", "url": "https://example.com/triund"},
	])
	assert len(ids) == 2

	# Retrieve context
	ctx = rag.retrieve_context("winter trek Kedarkantha", k=2)
	assert len(ctx) >= 1

	# Generate answer (will fallback if no API key)
	ans = rag.generate_answer("Is Kedarkantha safe in December?", ctx)
	assert isinstance(ans, str) and len(ans) > 0
