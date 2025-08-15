from rag.vector_store import VectorStore


def test_vector_store_add_and_search(tmp_path):
	# Use a temp dir to avoid polluting local storage
	vs = VectorStore(persist_directory=str(tmp_path / "chroma_db_test"))
	vs.clear_session()

	texts = [
		"Triund is a beginner-friendly trek near McLeod Ganj.",
		"Kedarkantha is a popular winter trek in Uttarakhand.",
		"Hampta Pass connects Kullu valley with Lahaul.",
	]
	metas = [
		{"source": "wikivoyage", "trail_name": "Triund", "section_type": "overview", "url": "https://en.wikivoyage.org/wiki/Triund"},
		{"source": "wikivoyage", "trail_name": "Kedarkantha", "section_type": "overview", "url": "https://en.wikivoyage.org/wiki/Kedarkantha"},
		{"source": "wikivoyage", "trail_name": "Hampta Pass", "section_type": "overview", "url": "https://en.wikivoyage.org/wiki/Hampta_Pass"},
	]

	ids = vs.add_documents(texts, metas)
	assert len(ids) == 3

	res = vs.search("winter trek Kedarkantha", k=2)
	assert len(res) >= 1
	# Basic shape checks (embedding may fallback without API key)
	assert all(isinstance(r.get("metadata", {}), dict) for r in res)
	assert all("text" in r for r in res)
