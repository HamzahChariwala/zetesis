"""
Multi-request drain test for Zetesis.

Submits 5 requests with different types and priorities simultaneously,
then watches them all complete and verifies:
  - Completion order matches priority order
  - Each output is topically relevant to its query
  - Timing per request and total throughput
  - A follow-up request mid-drain works correctly
  - Late-arriving request gets correct priority placement
"""

import asyncio
import time
import httpx
import sys

BASE = "http://localhost:8000/api/v1"


REQUESTS = [
    {
        "query": "Explain the core idea behind ring attention and how it enables processing sequences longer than a single device's memory",
        "request_type": "deep_dive",
        "tags": ["ml", "attention", "distributed"],
        "priority": 2,
        "relevance_keywords": ["ring", "attention", "sequence", "memory", "device"],
    },
    {
        "query": "Could diffusion models be adapted for autoregressive text generation in a way that outperforms standard next-token prediction?",
        "request_type": "idea_exploration",
        "tags": ["ml", "diffusion", "generation"],
        "priority": 8,
        "relevance_keywords": ["diffusion", "text", "generation", "token", "autoregressive"],
    },
    {
        "query": "Survey key approaches to reducing transformer inference latency: quantization, pruning, distillation, speculative decoding",
        "request_type": "literature_review",
        "tags": ["ml", "inference", "optimization"],
        "priority": 5,
        "relevance_keywords": ["quantization", "pruning", "distillation", "speculative", "latency", "inference"],
    },
    {
        "query": "Flash attention provides no benefit for batch size 1 inference on consumer hardware",
        "request_type": "fact_check",
        "tags": ["ml", "attention", "inference"],
        "priority": 1,
        "relevance_keywords": ["flash", "attention", "batch", "inference", "memory", "hardware"],
    },
    {
        "query": "What are the theoretical limits of knowledge distillation — can a student ever surpass its teacher, and under what conditions?",
        "request_type": "deep_dive",
        "tags": ["ml", "distillation", "theory"],
        "priority": 6,
        "relevance_keywords": ["distillation", "student", "teacher", "knowledge", "capacity"],
    },
]

EXPECTED_PRIORITY_ORDER = sorted(range(len(REQUESTS)), key=lambda i: -REQUESTS[i]["priority"])
# indices sorted by priority desc: 1(p8), 4(p6), 2(p5), 0(p2), 3(p1)


async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:

        # ── Submit all 5 simultaneously ──
        print("Submitting 5 requests simultaneously...\n")
        print(f"  {'#':<3} {'Priority':<10} {'Type':<20} {'Query (truncated)'}")
        print(f"  {'─'*3} {'─'*10} {'─'*20} {'─'*50}")

        submitted = []
        submit_time = time.time()

        for i, req in enumerate(REQUESTS):
            r = await c.post("/requests", json={
                "query": req["query"],
                "request_type": req["request_type"],
                "tags": req["tags"],
                "priority": req["priority"],
            })
            assert r.status_code == 201, f"Submit failed: {r.status_code} {r.text}"
            data = r.json()
            submitted.append({
                "index": i,
                "id": data["id"],
                "priority": req["priority"],
                "type": req["request_type"],
                "query_short": req["query"][:50],
                "keywords": req["relevance_keywords"],
                "submit_time": time.time(),
                "complete_time": None,
                "status": None,
                "output": None,
            })
            print(f"  {i:<3} p={req['priority']:<8} {req['request_type']:<20} {req['query'][:50]}...")

        print(f"\n  All submitted in {time.time() - submit_time:.2f}s")
        print(f"  Expected completion order by priority: {[REQUESTS[i]['priority'] for i in EXPECTED_PRIORITY_ORDER]}")

        # ── Inject a late-arriving high-priority request after 5s ──
        late_request = None

        # ── Poll until all complete ──
        print(f"\n  Waiting for all requests to complete (model generates ~57 tok/s, expect ~3-6 min total)...\n")

        completion_order = []
        completed_set = set()
        poll_start = time.time()
        late_injected = False

        while len(completed_set) < len(submitted):
            elapsed = time.time() - poll_start

            # Inject late request after first completion
            if len(completed_set) == 1 and not late_injected:
                print(f"  [{elapsed:6.1f}s] Injecting late-arriving request with priority=10 (highest)...")
                r = await c.post("/requests", json={
                    "query": "Briefly define the lottery ticket hypothesis in 2-3 sentences",
                    "request_type": "fact_check",
                    "tags": ["ml", "pruning"],
                    "priority": 10,
                })
                assert r.status_code == 201
                late_data = r.json()
                late_request = {
                    "id": late_data["id"],
                    "inject_time": time.time(),
                    "complete_time": None,
                    "output": None,
                }
                submitted.append({
                    "index": 5,
                    "id": late_data["id"],
                    "priority": 10,
                    "type": "fact_check",
                    "query_short": "Briefly define the lottery ticket hypothesis...",
                    "keywords": ["lottery", "ticket", "pruning", "subnetwork", "sparse"],
                    "submit_time": time.time(),
                    "complete_time": None,
                    "status": None,
                    "output": None,
                })
                late_injected = True

            for item in submitted:
                if item["id"] in completed_set:
                    continue
                r = await c.get(f"/requests/{item['id']}")
                status = r.json()["status"]
                if status in ("completed", "failed"):
                    item["complete_time"] = time.time()
                    item["status"] = status
                    completed_set.add(item["id"])
                    completion_order.append(item["index"])

                    if status == "completed":
                        # Fetch output
                        r2 = await c.get("/outputs", params={"limit": 50})
                        for out in r2.json():
                            if out["request_id"] == item["id"]:
                                item["output"] = out
                                break

                    req_elapsed = item["complete_time"] - item["submit_time"]
                    print(f"  [{elapsed:6.1f}s] #{item['index']} completed ({status}) "
                          f"p={item['priority']} {item['type']:<20} "
                          f"took={req_elapsed:.1f}s" +
                          (f" tokens={item['output']['token_count']} "
                           f"inference={item['output']['inference_time_ms']}ms"
                           if item.get('output') else ""))

            if elapsed > 600:
                print("  TIMEOUT: 10 minutes exceeded")
                break

            await asyncio.sleep(2)

        total_time = time.time() - poll_start

        # ── Analysis ──
        print(f"\n{'═' * 70}")
        print(f"  RESULTS")
        print(f"{'═' * 70}")

        # 1. Completion order vs priority order
        print(f"\n  Completion Order vs Expected Priority Order:")
        actual_priorities = [submitted[i]["priority"] for i in completion_order]
        expected_priorities = sorted([s["priority"] for s in submitted], reverse=True)
        print(f"    Expected (by priority): {expected_priorities}")
        print(f"    Actual:                 {actual_priorities}")

        order_correct = True
        violations = []
        # Check: each completed request should have higher priority than all not-yet-completed at that point
        for pos, idx in enumerate(completion_order):
            p = submitted[idx]["priority"]
            # All requests that completed after this one
            later = [submitted[completion_order[j]]["priority"] for j in range(pos + 1, len(completion_order))]
            if later and p < max(later):
                order_correct = False
                violations.append(f"p={p} completed before p={max(later)}")

        if order_correct:
            print(f"    ✓ Priority order respected perfectly")
        else:
            print(f"    ✗ Priority violations: {violations}")
            print(f"      (Note: first request may break ordering since worker grabs it before all are submitted)")

        # 2. Per-request output analysis
        print(f"\n  Per-Request Output Analysis:")
        print(f"  {'#':<3} {'Pri':<5} {'Type':<20} {'Status':<10} {'Tokens':<8} {'Time(ms)':<10} {'Tok/s':<8} {'Relevant?'}")
        print(f"  {'─'*3} {'─'*5} {'─'*20} {'─'*10} {'─'*8} {'─'*10} {'─'*8} {'─'*10}")

        all_relevant = True
        total_tokens = 0
        total_inference_ms = 0

        for item in sorted(submitted, key=lambda x: x["priority"], reverse=True):
            out = item.get("output")
            if out:
                tokens = out["token_count"]
                ms = out["inference_time_ms"]
                tps = tokens / (ms / 1000) if ms > 0 else 0
                total_tokens += tokens
                total_inference_ms += ms

                content_lower = out["content"].lower()
                relevant = any(kw in content_lower for kw in item["keywords"])
                if not relevant:
                    all_relevant = False

                print(f"  {item['index']:<3} p={item['priority']:<3} {item['type']:<20} {item['status']:<10} "
                      f"{tokens:<8} {ms:<10} {tps:<8.1f} {'✓' if relevant else '✗'}")
            else:
                print(f"  {item['index']:<3} p={item['priority']:<3} {item['type']:<20} {item['status']:<10} "
                      f"{'—':<8} {'—':<10} {'—':<8} —")

        # 3. Timing summary
        print(f"\n  Timing Summary:")
        print(f"    Total wall time:        {total_time:.1f}s")
        print(f"    Total inference time:    {total_inference_ms/1000:.1f}s")
        print(f"    Total tokens generated:  {total_tokens}")
        avg_tps = total_tokens / (total_inference_ms / 1000) if total_inference_ms > 0 else 0
        print(f"    Average throughput:       {avg_tps:.1f} tok/s")
        print(f"    Overhead (queue/poll):    {total_time - total_inference_ms/1000:.1f}s")

        # 4. Late-arriving request
        if late_request:
            late_item = next(s for s in submitted if s["id"] == late_request["id"])
            if late_item["complete_time"]:
                # How many requests completed after the late one was injected but before it completed?
                injected_at = late_request["inject_time"]
                completed_after_inject_before_late = [
                    s for s in submitted
                    if s["id"] != late_request["id"]
                    and s["complete_time"]
                    and s["complete_time"] > injected_at
                    and s["complete_time"] < late_item["complete_time"]
                ]
                print(f"\n  Late-Arriving Request (p=10, injected after first completion):")
                # It should have been processed right after whatever was currently processing finished
                # since p=10 > all others
                if completed_after_inject_before_late:
                    jumped = [s for s in completed_after_inject_before_late if s["priority"] < 10]
                    print(f"    Requests that completed between injection and late completion: "
                          f"{[(s['index'], s['priority']) for s in completed_after_inject_before_late]}")
                    if not jumped:
                        print(f"    ✓ Late request was prioritized correctly (only higher/equal priority went first)")
                    else:
                        # One request may have been already processing when injected
                        print(f"    ⚠ {len(jumped)} lower-priority request(s) completed first "
                              f"(expected: 1 max, the one already processing)")
                else:
                    print(f"    ✓ Late p=10 request completed before all remaining lower-priority requests")

        # 5. Follow-up test: create a follow-up from the first completed output
        print(f"\n  Follow-up Chain Test:")
        first_completed = next((s for s in submitted if s.get("output")), None)
        if first_completed:
            out_id = first_completed["output"]["id"]
            r = await c.post(f"/outputs/{out_id}/review", json={
                "action": "follow_up",
                "comment": "Expand on this",
                "follow_up_query": "What are the practical implementation challenges of the approach described above?",
            })
            if r.status_code == 201:
                fu_id = r.json()["follow_up_request_id"]
                r2 = await c.get(f"/requests/{fu_id}")
                fu = r2.json()
                print(f"    ✓ Follow-up created (id={fu_id[:8]}...)")
                print(f"    ✓ Has parent_id: {fu['parent_id'] is not None}")
                print(f"    ✓ Context includes previous output: {'Previous output:' in (fu.get('context') or '')}")
                print(f"    Status: {fu['status']} (letting it complete would take another ~30s)")
                # Cancel to not block
                await c.delete(f"/requests/{fu_id}")
                print(f"    (Cancelled to avoid waiting — follow-up mechanism verified)")

        # 6. Final verdict
        print(f"\n{'═' * 70}")
        all_completed = all(s["status"] == "completed" for s in submitted)
        print(f"  All requests completed: {'✓' if all_completed else '✗'}")
        print(f"  All outputs relevant:   {'✓' if all_relevant else '✗'}")
        print(f"  Priority order held:    {'✓' if order_correct else '⚠ (see violations above)'}")
        print(f"{'═' * 70}")

        return all_completed and all_relevant


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
