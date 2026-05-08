"""
Live AWS credential check from inside the backend container.
Run with: docker exec aiops_backend python scripts/check_aws_live.py
"""
import asyncio
import sys
sys.path.insert(0, '/app')

import boto3


async def main():
    from database.database import AsyncSessionLocal
    from database.models import CloudCredential
    from services.encryption import decrypt_credentials
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CloudCredential))
        creds = result.scalars().all()
        print(f"Found {len(creds)} stored credential(s)\n")

        for c in creds:
            decrypted = decrypt_credentials(c.encrypted_data)
            region = decrypted.get("region", "us-east-1")
            access_key = decrypted.get("access_key_id", "")
            print(f"  cred_id={c.id}  provider={c.provider}  region={region}")
            print(f"  access_key_id={access_key[:8]}***")

            aws_session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=decrypted.get("secret_access_key"),
                region_name=region,
            )

            # STS identity check
            try:
                identity = aws_session.client("sts").get_caller_identity()
                account = identity["Account"]
                arn = identity["Arn"]
                print(f"  STS: VALID  account={account}  arn={arn}")
            except Exception as e:
                print(f"  STS: FAILED  {e}")
                continue

            # EC2 list
            try:
                ec2 = aws_session.client("ec2")
                pages = ec2.get_paginator("describe_instances").paginate()
                instances = []
                for page in pages:
                    for r in page.get("Reservations", []):
                        for i in r.get("Instances", []):
                            name = next(
                                (t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"),
                                i["InstanceId"],
                            )
                            instances.append(f"{i['InstanceId']} ({i['State']['Name']}) — {name}")
                if instances:
                    print(f"  EC2: {len(instances)} instance(s) found:")
                    for inst in instances:
                        print(f"    - {inst}")
                else:
                    print(f"  EC2: 0 instances in {region} (try other regions if expected)")
            except Exception as e:
                print(f"  EC2: FAILED  {e}")

            # S3 list
            try:
                s3 = aws_session.client("s3")
                buckets = s3.list_buckets().get("Buckets", [])
                print(f"  S3:  {len(buckets)} bucket(s): {[b['Name'] for b in buckets]}")
            except Exception as e:
                print(f"  S3:  FAILED  {e}")

            print()


asyncio.run(main())
