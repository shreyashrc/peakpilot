import asyncio

from mcp.mcp_server import MCPOchestrator


def test_orchestrator_full_pipeline_smoke():
	orch = MCPOchestrator()
	ctx = asyncio.run(orch.run("Is Kedarkantha safe in December?"))
	assert "answer" in ctx
	assert isinstance(ctx.get("retrieved_context", []), list)
