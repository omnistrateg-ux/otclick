#!/usr/bin/env python3
"""Full cycle API test script.

Tests the main API endpoints to verify they work without 500 errors.
"""

import asyncio
import sys
from datetime import datetime, timezone

import httpx

UTC = timezone.utc

BASE_URL = "http://176.126.166.94:8000/api/v1"
# For local testing:
# BASE_URL = "http://localhost:8000/api/v1"


async def test_api():
    """Run API tests."""
    errors = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("Full Cycle API Test")
        print("=" * 60)
        print(f"Base URL: {BASE_URL}")
        print()

        # Step 1: Health check
        print("Step 1: Health check...")
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                print(f"  ✓ GET /health - {resp.status_code}")
            else:
                print(f"  ✗ GET /health - {resp.status_code}")
                errors.append(f"Health check failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ GET /health - Error: {e}")
            errors.append(f"Health check error: {e}")

        # Step 2: Get leads list
        print("Step 2: Get leads list...")
        try:
            resp = await client.get(f"{BASE_URL}/leads")
            if resp.status_code == 200:
                print(f"  ✓ GET /leads - {resp.status_code}")
                data = resp.json()
                print(f"    Total leads: {data.get('total', 0)}")
            else:
                print(f"  ✗ GET /leads - {resp.status_code}")
                print(f"    Response: {resp.text[:200]}")
                errors.append(f"Get leads failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ GET /leads - Error: {e}")
            errors.append(f"Get leads error: {e}")

        # Step 3: Create a test lead
        print("Step 3: Create test lead...")
        try:
            lead_data = {
                "company_name": f"Test Company {datetime.now(UTC).isoformat()}",
                "website": f"https://test-{int(datetime.now(UTC).timestamp())}.example.com",
                "city": "Москва",
            }
            resp = await client.post(f"{BASE_URL}/leads", json=lead_data)
            if resp.status_code in (200, 201):
                print(f"  ✓ POST /leads - {resp.status_code}")
                lead = resp.json()
                lead_id = lead.get("id")
                print(f"    Created lead ID: {lead_id}")
            else:
                print(f"  ✗ POST /leads - {resp.status_code}")
                print(f"    Response: {resp.text[:500]}")
                errors.append(f"Create lead failed: {resp.status_code} - {resp.text[:200]}")
                lead_id = None
        except Exception as e:
            print(f"  ✗ POST /leads - Error: {e}")
            errors.append(f"Create lead error: {e}")
            lead_id = None

        # Step 4: Get funnel analytics
        print("Step 4: Get funnel analytics...")
        try:
            resp = await client.get(f"{BASE_URL}/analytics/funnel")
            if resp.status_code == 200:
                print(f"  ✓ GET /analytics/funnel - {resp.status_code}")
                data = resp.json()
                print(f"    Discovered: {data.get('discovered', 0)}")
            else:
                print(f"  ✗ GET /analytics/funnel - {resp.status_code}")
                print(f"    Response: {resp.text[:500]}")
                errors.append(f"Funnel analytics failed: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"  ✗ GET /analytics/funnel - Error: {e}")
            errors.append(f"Funnel analytics error: {e}")

        # Step 5: Get dashboard analytics
        print("Step 5: Get dashboard analytics...")
        try:
            resp = await client.get(f"{BASE_URL}/analytics/dashboard")
            if resp.status_code == 200:
                print(f"  ✓ GET /analytics/dashboard - {resp.status_code}")
            else:
                print(f"  ✗ GET /analytics/dashboard - {resp.status_code}")
                print(f"    Response: {resp.text[:500]}")
                errors.append(f"Dashboard analytics failed: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"  ✗ GET /analytics/dashboard - Error: {e}")
            errors.append(f"Dashboard analytics error: {e}")

        # Step 6: Get email performance
        print("Step 6: Get email performance...")
        try:
            resp = await client.get(f"{BASE_URL}/analytics/email-performance")
            if resp.status_code == 200:
                print(f"  ✓ GET /analytics/email-performance - {resp.status_code}")
            else:
                print(f"  ✗ GET /analytics/email-performance - {resp.status_code}")
                print(f"    Response: {resp.text[:500]}")
                errors.append(f"Email performance failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ GET /analytics/email-performance - Error: {e}")
            errors.append(f"Email performance error: {e}")

        # Step 7: Get campaigns
        print("Step 7: Get campaigns list...")
        try:
            resp = await client.get(f"{BASE_URL}/campaigns")
            if resp.status_code == 200:
                print(f"  ✓ GET /campaigns - {resp.status_code}")
            else:
                print(f"  ✗ GET /campaigns - {resp.status_code}")
                errors.append(f"Get campaigns failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ GET /campaigns - Error: {e}")
            errors.append(f"Get campaigns error: {e}")

        # Step 8: Get handoffs
        print("Step 8: Get handoffs list...")
        try:
            resp = await client.get(f"{BASE_URL}/handoffs")
            if resp.status_code == 200:
                print(f"  ✓ GET /handoffs - {resp.status_code}")
            else:
                print(f"  ✗ GET /handoffs - {resp.status_code}")
                errors.append(f"Get handoffs failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ GET /handoffs - Error: {e}")
            errors.append(f"Get handoffs error: {e}")

        # Step 9: Get lead detail (if we created one)
        if lead_id:
            print(f"Step 9: Get lead detail ({lead_id})...")
            try:
                resp = await client.get(f"{BASE_URL}/leads/{lead_id}")
                if resp.status_code == 200:
                    print(f"  ✓ GET /leads/{lead_id} - {resp.status_code}")
                else:
                    print(f"  ✗ GET /leads/{lead_id} - {resp.status_code}")
                    errors.append(f"Get lead detail failed: {resp.status_code}")
            except Exception as e:
                print(f"  ✗ GET /leads/{lead_id} - Error: {e}")
                errors.append(f"Get lead detail error: {e}")
        else:
            print("Step 9: SKIPPED (no lead created)")

        # Step 10: Get time series
        print("Step 10: Get time series data...")
        try:
            resp = await client.get(f"{BASE_URL}/analytics/time-series/discovered")
            if resp.status_code == 200:
                print(f"  ✓ GET /analytics/time-series/discovered - {resp.status_code}")
            else:
                print(f"  ✗ GET /analytics/time-series/discovered - {resp.status_code}")
                errors.append(f"Time series failed: {resp.status_code}")
        except Exception as e:
            print(f"  ✗ GET /analytics/time-series/discovered - Error: {e}")
            errors.append(f"Time series error: {e}")

        print()
        print("=" * 60)
        print("Test Results")
        print("=" * 60)

        if errors:
            print(f"\n❌ FAILED - {len(errors)} error(s):\n")
            for i, err in enumerate(errors, 1):
                print(f"  {i}. {err}")
            return 1
        else:
            print("\n✅ ALL TESTS PASSED!")
            return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_api())
    sys.exit(exit_code)
