import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import AsyncSessionLocal
from database.models import CloudCredential, CloudResource, HealingAction, DesiredState
from sqlalchemy import delete

async def cleanup():
    print("--- 🗑️  Cleaning up Demo/Mock Data ---")
    async with AsyncSessionLocal() as db:
        # Delete credentials that have "Demo" in the name or 'mock-encrypted-data'
        q = delete(CloudCredential).where(
            (CloudCredential.name.like("%Demo%")) | 
            (CloudCredential.encrypted_data == "mock-encrypted-data")
        )
        res = await db.execute(q)
        print(f"  - Removed {res.rowcount} mock credentials.")

        # Delete the seeded "Legacy DB" resource
        q = delete(CloudResource).where(CloudResource.resource_id == "db-master-01")
        res = await db.execute(q)
        print(f"  - Removed {res.rowcount} demo resources.")

        # Delete any associated healing actions for demo resources
        q = delete(HealingAction).where(HealingAction.resource_id == "db-master-01")
        res = await db.execute(q)
        print(f"  - Removed {res.rowcount} demo healing actions.")

        # Delete the desired state baseline for the demo DB
        q = delete(DesiredState).where(DesiredState.resource_id == "db-master-01")
        res = await db.execute(q)
        print(f"  - Removed {res.rowcount} demo baselines.")

        await db.commit()
    print("DONE: Your system is now 100% clean and ready for REAL cloud data only.")

if __name__ == "__main__":
    asyncio.run(cleanup())
