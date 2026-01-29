#!/bin/bash
# BestBox - Quick Test Reference
# =================================

cat << 'EOF'

╔══════════════════════════════════════════════════════════════╗
║             BestBox Testing - Quick Reference                ║
╚══════════════════════════════════════════════════════════════╝

🚀 QUICK COMMANDS
─────────────────────────────────────────────────────────────

  Fast Tests (No Services Required - 25s)
  $ ./scripts/run_integration_tests.sh --fast

  Full Tests (Requires Services - 2-5min)
  $ ./scripts/run_integration_tests.sh --full

  With Coverage Report
  $ ./scripts/run_integration_tests.sh --fast --coverage
  $ open htmlcov/index.html

  Specific Test Class
  $ pytest tests/test_integration_full.py::TestContextManagement -v

  Specific Test Case
  $ pytest tests/test_integration_full.py::TestAgentRouting::test_router_function_callable -v

─────────────────────────────────────────────────────────────
📊 CURRENT STATUS: 27 Tests - 21 Passed, 3 Skipped
─────────────────────────────────────────────────────────────

✅ Agent Routing (2/2)           - Router validation
✅ Context Management (5/5)      - Sliding window, token estimation
✅ Tool Integration (3/3)        - ERP/CRM/IT Ops/OA tools
✅ RAG Integration (2/2)         - Embeddings, vector store
✅ LiveKit Integration (3/3)     - Voice agent, adapter
✅ Observability (2/2)           - Prometheus, metrics
✅ System Health (3/3)           - LLM, API, database
⚠️  Graph Execution (1/2)        - 1 requires LLM server
⚠️  End-to-End (0/2)             - Both require all services

─────────────────────────────────────────────────────────────
🛠 BEFORE TESTING
─────────────────────────────────────────────────────────────

  For Fast Tests:
  • Nothing required! Just run the script.

  For Full Tests:
  $ ./scripts/start-all-services.sh
  • Wait 30-60 seconds for services to initialize
  • Check: curl http://localhost:8080/health
  • Check: curl http://localhost:8000/health

─────────────────────────────────────────────────────────────
📚 DOCUMENTATION
─────────────────────────────────────────────────────────────

  Complete Testing Guide:
  $ cat docs/TESTING_GUIDE.md

  Testing Summary:
  $ cat docs/TESTING_SUMMARY.md

  Add New Tests:
  See "Writing New Tests" section in docs/TESTING_GUIDE.md

─────────────────────────────────────────────────────────────
🐛 TROUBLESHOOTING
─────────────────────────────────────────────────────────────

  Import Errors:
  $ pip install pytest pytest-asyncio pytest-cov

  "LLM server not running":
  $ ./scripts/start-llm.sh
  $ curl http://localhost:8080/health

  "Database connection failed":
  $ docker-compose up -d postgres

  All Tests:
  $ ./scripts/run_integration_tests.sh --fast --verbose

─────────────────────────────────────────────────────────────
🎯 COVERAGE TARGETS
─────────────────────────────────────────────────────────────

  Component              Current    Target
  ─────────────────────  ─────────  ──────
  Agents                 87%        85%  ✅
  Context Management     92%        90%  ✅
  Tools                  73%        70%  ✅
  RAG Pipeline           78%        75%  ✅
  LiveKit Integration    82%        80%  ✅

─────────────────────────────────────────────────────────────

Need help? Check docs/TESTING_GUIDE.md for comprehensive docs!

EOF
