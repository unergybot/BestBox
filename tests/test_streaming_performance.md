# Streaming Performance Test Checklist

**Date:** 2026-02-13
**Tester:** [Your name]

## Test Environment
- [ ] All services running (Docker, vLLM, Agent API, Frontend)
- [ ] Browser: Chrome/Edge with DevTools open
- [ ] Logs visible: `tail -f ~/BestBox/logs/agent_api.log`

## Test 1: Streaming is Enabled
**Query:** "Hello"
- [ ] Log shows: `stream flag: True`
- [ ] Response appears progressively (not all at once)
- [ ] TTFT < 500ms

## Test 2: Short Response
**Query:** "介绍BestBox"
- [ ] Chunks appear progressively
- [ ] Smooth, continuous flow
- [ ] No long pauses
- [ ] TTFT logged in backend logs

## Test 3: Long Response
**Query:** "请详细介绍BestBox系统的ERP模块功能"
- [ ] Progressive display throughout
- [ ] Maintains configured chunk size
- [ ] Total duration reasonable (<10s)
- [ ] Metrics show tokens/second > 10

## Test 4: Voice Integration
- [ ] Click voice button
- [ ] Say: "查询销售数据"
- [ ] Pause 1.5s (silence detection)
- [ ] Transcript appears in chat
- [ ] Response streams progressively

## Test 5: Error Handling
**Query:** [Any query]
- [ ] If error occurs, check logs
- [ ] Error event sent to client
- [ ] UI does not crash
- [ ] Partial response remains visible

## Test 6: Metrics Validation
Check logs after each query:
- [ ] TTFT logged
- [ ] Duration logged
- [ ] Chunks/tokens counted
- [ ] No errors (unless testing error cases)

## Success Criteria
- [ ] Stream flag: True
- [ ] TTFT: < 500ms
- [ ] Smooth visual streaming
- [ ] No crashes or hangs

## Issues Found
- [ ] None

## Next Steps
- [ ] Document follow-up optimizations if needed
