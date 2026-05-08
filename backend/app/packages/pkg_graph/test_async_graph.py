import pytest
import asyncio
import pytest_asyncio
from app.packages.pkg_graph.async_graph import AsyncGraphEngine

@pytest_asyncio.fixture
async def graph_engine():
    engine = AsyncGraphEngine(max_workers=2)
    yield engine
    await engine.shutdown()

@pytest.mark.asyncio
async def test_blast_radius_calculation(graph_engine):
    """Ensure the async executor maps dependencies properly without blocking."""
    tenant = "tenant-prod-a"
    
    # 1. Provide authentic test topography
    await graph_engine.add_resource(tenant, "db-1", {"type": "rds", "status": "running"})
    await graph_engine.add_resource(tenant, "api-server-1", {"type": "ec2", "status": "running"})
    await graph_engine.add_resource(tenant, "web-front-1", {"type": "ec2", "status": "running"})
    
    # Dependencies: web -> api -> db
    # Thus, if db fails, api and web are in the blast radius (descendants)
    await graph_engine.add_dependency(tenant, "db-1", "api-server-1")
    await graph_engine.add_dependency(tenant, "api-server-1", "web-front-1")
    
    # 2. Trigger async CPU intense blast radius graph traversal
    impacts = await graph_engine.calculate_blast_radius(tenant, "db-1")
    
    # 3. Validation
    assert set(impacts) == {"api-server-1", "web-front-1"}

@pytest.mark.asyncio
async def test_tenant_isolation(graph_engine):
    """Validate cross-tenant leakage does not occur."""
    tenant_1 = "tenant-secure-vpc"
    tenant_2 = "tenant-public-vpc"
    
    await graph_engine.add_resource(tenant_1, "shared-naming-db", {"secret": "t1"})
    await graph_engine.add_resource(tenant_2, "shared-naming-db", {"secret": "t2"})
    await graph_engine.add_dependency(tenant_1, "shared-naming-db", "downstream-t1")
    
    impacts_t1 = await graph_engine.calculate_blast_radius(tenant_1, "shared-naming-db")
    impacts_t2 = await graph_engine.calculate_blast_radius(tenant_2, "shared-naming-db")
    
    assert "downstream-t1" in impacts_t1
    assert "downstream-t1" not in impacts_t2
    assert len(impacts_t2) == 0
