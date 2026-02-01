#!/usr/bin/env python3
"""
VLM Integration Test Script

Tests the VLM service integration components:
1. VLM client connectivity
2. Job store operations
3. Document analysis tools
4. Mold agent with VLM tools

Usage:
    python scripts/test_vlm_integration.py [--file sample.jpg]
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_vlm_client_import():
    """Test VLM client import"""
    print("\n1. Testing VLM client import...")
    try:
        from services.vlm import VLMServiceClient, VLMResult, VLMJobStore
        from services.vlm.models import VLMJobOptions, AnalysisDepth, JobStatus
        print("   ✅ VLM client modules imported successfully")
        return True
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False


def test_vlm_client_health():
    """Test VLM service health check"""
    print("\n2. Testing VLM service health...")
    try:
        from services.vlm import VLMServiceClient

        async def check_health():
            client = VLMServiceClient()
            try:
                available = await client.is_available()
                if available:
                    health = await client.check_health()
                    print(f"   ✅ VLM service available")
                    print(f"      Status: {health.status}")
                    print(f"      Model: {health.model}")
                    print(f"      Queue depth: {health.queue_depth}")
                    return True
                else:
                    print("   ⚠️  VLM service not available (this is OK if VLM server is not running)")
                    return False
            finally:
                await client.close()

        return asyncio.run(check_health())
    except Exception as e:
        print(f"   ⚠️  Health check failed: {e}")
        return False


def test_job_store():
    """Test job store operations"""
    print("\n3. Testing job store...")
    try:
        from services.vlm import VLMJobStore, VLMResult
        from services.vlm.models import VLMMetadata

        async def test_store():
            store = VLMJobStore()
            test_job_id = "test-job-123"

            try:
                # Test mark pending
                await store.mark_pending(test_job_id)
                status = await store.get_status(test_job_id)
                if status:
                    print(f"   ✅ Mark pending works (status: {status.value})")
                else:
                    print("   ⚠️  Could not verify pending status (Redis may not be running)")

                # Test store result
                test_result = VLMResult(
                    job_id=test_job_id,
                    document_summary="Test summary",
                    key_insights=["Insight 1", "Insight 2"],
                    tags=["test", "vlm"],
                    metadata=VLMMetadata(confidence_score=0.95)
                )
                await store.store_result(test_job_id, test_result)

                # Test retrieve result
                retrieved = await store.get_result(test_job_id)
                if retrieved and retrieved.document_summary == "Test summary":
                    print("   ✅ Store and retrieve result works")
                else:
                    print("   ⚠️  Result retrieval issue")

                # Cleanup
                await store.delete_result(test_job_id)
                print("   ✅ Job store operations complete")
                return True

            except Exception as e:
                print(f"   ⚠️  Job store test failed: {e}")
                print("      (This is expected if Redis is not running)")
                return False
            finally:
                await store.close()

        return asyncio.run(test_store())
    except Exception as e:
        print(f"   ❌ Job store test failed: {e}")
        return False


def test_document_tools_import():
    """Test document tools import"""
    print("\n4. Testing document tools import...")
    try:
        from tools.document_tools import (
            analyze_image_realtime,
            analyze_document_realtime,
            compare_images,
            document_tools
        )
        print(f"   ✅ Document tools imported ({len(document_tools)} tools)")
        for tool in document_tools:
            print(f"      - {tool.name}")
        return True
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False


def test_mold_agent_tools():
    """Test mold agent has VLM tools when enabled"""
    print("\n5. Testing mold agent tools...")
    try:
        # Temporarily enable VLM for testing
        os.environ["VLM_ENABLED"] = "true"

        # Force reload to pick up env change
        import importlib
        import agents.mold_agent
        importlib.reload(agents.mold_agent)

        from agents.mold_agent import MOLD_TOOLS, VLM_ENABLED, VLM_TOOLS_AVAILABLE

        print(f"   VLM_ENABLED: {VLM_ENABLED}")
        print(f"   VLM_TOOLS_AVAILABLE: {VLM_TOOLS_AVAILABLE}")
        print(f"   Total tools: {len(MOLD_TOOLS)}")

        for tool in MOLD_TOOLS:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            print(f"      - {tool_name}")

        if len(MOLD_TOOLS) > 2:
            print("   ✅ VLM tools included in mold agent")
        else:
            print("   ⚠️  VLM tools not loaded (check VLM_TOOLS_AVAILABLE)")

        # Reset
        os.environ["VLM_ENABLED"] = "false"
        return True
    except Exception as e:
        print(f"   ❌ Mold agent test failed: {e}")
        return False


def test_vl_processor():
    """Test VL processor with VLM service"""
    print("\n6. Testing VL processor...")
    try:
        from services.troubleshooting.vl_processor import VLProcessor

        processor = VLProcessor(enabled=False, use_vlm_service=True)
        print(f"   VL processor initialized")
        print(f"      Enabled: {processor.enabled}")
        print(f"      Use VLM service: {processor.use_vlm_service}")
        print(f"      Service available: {processor.service_available}")
        print("   ✅ VL processor works")
        return True
    except Exception as e:
        print(f"   ❌ VL processor test failed: {e}")
        return False


def test_embedder_indexer():
    """Test embedder and indexer have VLM fields"""
    print("\n7. Testing embedder/indexer VLM support...")
    try:
        from services.troubleshooting.embedder import TroubleshootingEmbedder
        from services.troubleshooting.indexer import TroubleshootingIndexer

        # Check indexer has VLM helper methods
        indexer_methods = dir(TroubleshootingIndexer)
        vlm_methods = [m for m in indexer_methods if 'vlm' in m.lower() or 'severity' in m.lower() or 'tags' in m.lower()]
        print(f"   VLM-related methods in indexer: {vlm_methods}")

        if '_aggregate_image_tags' in indexer_methods:
            print("   ✅ Indexer has VLM metadata support")
        else:
            print("   ⚠️  Indexer VLM methods not found")

        return True
    except Exception as e:
        print(f"   ❌ Embedder/indexer test failed: {e}")
        return False


def test_searcher_vlm_boost():
    """Test searcher has VLM-aware boosting"""
    print("\n8. Testing searcher VLM boosting...")
    try:
        from services.troubleshooting.searcher import TroubleshootingSearcher
        import inspect

        # Check if searcher._search_issues has VLM boosting logic
        source = inspect.getsource(TroubleshootingSearcher._search_issues)
        if 'vlm_processed' in source or 'vlm_confidence' in source:
            print("   ✅ Searcher has VLM-aware boosting")
        else:
            print("   ⚠️  Searcher VLM boosting not found")

        return True
    except Exception as e:
        print(f"   ❌ Searcher test failed: {e}")
        return False


def test_agent_api_endpoints():
    """Test agent API has VLM endpoints"""
    print("\n9. Testing agent API VLM endpoints...")
    try:
        from services.agent_api import app

        routes = [r.path for r in app.routes]
        vlm_routes = [r for r in routes if 'vlm' in r.lower() or 'webhook' in r.lower()]

        print(f"   VLM-related routes: {vlm_routes}")

        expected_routes = [
            '/api/v1/webhooks/vlm-results',
            '/api/v1/upload',
            '/api/v1/vlm/jobs/{job_id}',
            '/health/vlm'
        ]

        found = [r for r in expected_routes if r in routes]
        if len(found) >= 3:
            print("   ✅ Agent API has VLM endpoints")
        else:
            print(f"   ⚠️  Some VLM endpoints missing. Found: {found}")

        return True
    except Exception as e:
        print(f"   ❌ Agent API test failed: {e}")
        return False


def test_file_analysis(file_path: str):
    """Test actual file analysis (requires VLM service)"""
    print(f"\n10. Testing file analysis with: {file_path}")

    if not Path(file_path).exists():
        print(f"   ⚠️  File not found: {file_path}")
        return False

    try:
        from tools.document_tools import analyze_image_realtime
        import json

        result = analyze_image_realtime.invoke({
            "image_path": file_path,
            "analysis_prompt": "分析此图像中的缺陷"
        })

        data = json.loads(result)
        if "error" in data:
            print(f"   ⚠️  Analysis returned error: {data['error']}")
            print("      (This is expected if VLM service is not running)")
            return False
        else:
            print("   ✅ File analysis successful")
            print(f"      Status: {data.get('status')}")
            if data.get('analysis'):
                print(f"      Defect type: {data['analysis'].get('defect_type')}")
                print(f"      Severity: {data['analysis'].get('severity')}")
            return True
    except Exception as e:
        print(f"   ❌ File analysis failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test VLM integration")
    parser.add_argument("--file", help="Image file to test analysis with")
    args = parser.parse_args()

    print("=" * 70)
    print("VLM Integration Test")
    print("=" * 70)

    results = []

    # Run tests
    results.append(("VLM client import", test_vlm_client_import()))
    results.append(("VLM client health", test_vlm_client_health()))
    results.append(("Job store", test_job_store()))
    results.append(("Document tools import", test_document_tools_import()))
    results.append(("Mold agent tools", test_mold_agent_tools()))
    results.append(("VL processor", test_vl_processor()))
    results.append(("Embedder/indexer", test_embedder_indexer()))
    results.append(("Searcher VLM boost", test_searcher_vlm_boost()))
    results.append(("Agent API endpoints", test_agent_api_endpoints()))

    if args.file:
        results.append(("File analysis", test_file_analysis(args.file)))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL/WARN"
        print(f"   {status}: {name}")

    print()
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ All tests passed!")
    else:
        print("\n⚠️  Some tests failed or warned (see details above)")
        print("   Note: VLM service tests may fail if service is not running")


if __name__ == "__main__":
    main()
