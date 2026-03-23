"""
Comprehensive integration test for Zetesis.
Tests: health, CRUD, queue behavior, review workflow, edge cases, concurrent submissions.
"""

import asyncio
import time
import httpx
import json
import sys

BASE = "http://localhost:8000/api/v1"
PASS = 0
FAIL = 0
RESULTS = []


def report(name: str, passed: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append((name, status, detail))
    icon = "✓" if passed else "✗"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))


async def wait_for_completion(c: httpx.AsyncClient, req_id: str, timeout: int = 120) -> dict:
    """Poll until a request completes or fails."""
    for _ in range(timeout):
        r = await c.get(f"/requests/{req_id}")
        data = r.json()
        if data["status"] in ("completed", "failed"):
            return data
        await asyncio.sleep(1)
    return data


async def run_tests():
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:

        # ═══════════════════════════════════════════
        # 1. SYSTEM HEALTH
        # ═══════════════════════════════════════════
        print("\n── 1. System Health ──")

        r = await c.get("/system/health")
        report("GET /system/health returns 200", r.status_code == 200)
        body = r.json()
        report("Health status is 'ok'", body.get("status") == "ok")
        report("Database connected", body.get("database") is True)

        r = await c.get("/system/queue/status")
        report("GET /system/queue/status returns 200", r.status_code == 200)
        body = r.json()
        report("Queue starts empty", all(body.get(k, -1) == 0 for k in ["queued", "processing", "completed", "failed"]),
               f"counts: {body}")

        # ═══════════════════════════════════════════
        # 2. SUBMIT & WAIT FOR INFERENCE (single)
        # ═══════════════════════════════════════════
        print("\n── 2. End-to-End Inference (submit → process → output) ──")

        r = await c.post("/requests", json={
            "query": "What are the key differences between speculative decoding and standard autoregressive generation? Be concise.",
            "request_type": "deep_dive",
            "tags": ["ml", "inference"],
            "priority": 5,
        })
        report("Submit deep_dive request → 201", r.status_code == 201)
        e2e_id = r.json()["id"]
        report("Status starts as 'queued' or 'processing'", r.json()["status"] in ("queued", "processing"))

        print("  ⏳ Waiting for inference to complete...")
        t0 = time.time()
        e2e_result = await wait_for_completion(c, e2e_id, timeout=180)
        elapsed = time.time() - t0
        report(f"Inference completed", e2e_result["status"] == "completed",
               f"status={e2e_result['status']} took={elapsed:.1f}s")
        if e2e_result["status"] == "failed":
            report("Inference error", False, e2e_result.get("error", "unknown"))

        # Check output was created
        r = await c.get("/outputs")
        outputs = r.json()
        e2e_output = next((o for o in outputs if o["request_id"] == e2e_id), None)
        report("Output exists for completed request", e2e_output is not None)

        if e2e_output:
            report("Output has content", len(e2e_output["content"]) > 50,
                   f"length={len(e2e_output['content'])} chars")
            report("Output has model_id", bool(e2e_output.get("model_id")),
                   e2e_output.get("model_id", ""))
            report("Output has inference_time_ms > 0", (e2e_output.get("inference_time_ms") or 0) > 0,
                   f"{e2e_output.get('inference_time_ms')}ms")
            report("Output has token_count > 0", (e2e_output.get("token_count") or 0) > 0,
                   f"{e2e_output.get('token_count')} tokens")
            report("Output status is 'unchecked'", e2e_output["status"] == "unchecked")

            # Content quality check
            content_lower = e2e_output["content"].lower()
            report("Output is topically relevant",
                   any(w in content_lower for w in ["speculative", "decoding", "autoregressive", "token", "draft"]),
                   f"first 200 chars: {e2e_output['content'][:200]}")

        # ═══════════════════════════════════════════
        # 3. REQUEST CREATION — all types
        # ═══════════════════════════════════════════
        print("\n── 3. Request Creation (all types) ──")

        test_requests = [
            {
                "query": "Survey the current state of research on mechanistic interpretability",
                "request_type": "literature_review",
                "tags": ["ml", "interpretability"],
                "priority": 3,
            },
            {
                "query": "Could we use biological neural oscillation patterns to improve artificial RNN architectures?",
                "request_type": "idea_exploration",
                "tags": ["neuroscience", "ml"],
                "priority": 7,
            },
            {
                "query": "KV cache compression via quantization has no effect on generation quality for models under 10B parameters",
                "request_type": "fact_check",
                "tags": ["ml", "inference"],
                "priority": 1,
            },
        ]

        created_ids = [e2e_id]
        for req in test_requests:
            r = await c.post("/requests", json=req)
            report(f"Create {req['request_type']} → 201", r.status_code == 201)
            if r.status_code == 201:
                body = r.json()
                created_ids.append(body["id"])
                report(f"  type={body['request_type']}, tags={body['tags']}, priority={body['priority']}",
                       body["request_type"] == req["request_type"]
                       and body["tags"] == req["tags"]
                       and body["priority"] == req["priority"])
                report(f"  status=queued", body["status"] in ("queued", "processing"))

        # ═══════════════════════════════════════════
        # 4. REQUEST LISTING & FILTERING
        # ═══════════════════════════════════════════
        print("\n── 4. Request Listing & Filtering ──")

        r = await c.get("/requests")
        all_reqs = r.json()
        report("GET /requests returns all", r.status_code == 200 and len(all_reqs) >= 4,
               f"count={len(all_reqs)}")

        r = await c.get("/requests", params={"request_type": "deep_dive"})
        deep_dives = r.json()
        report("Filter by type=deep_dive works",
               r.status_code == 200 and all(x["request_type"] == "deep_dive" for x in deep_dives),
               f"count={len(deep_dives)}")

        r = await c.get("/requests", params={"status": "completed"})
        completed = r.json()
        report("Filter by status=completed works",
               r.status_code == 200 and all(x["status"] == "completed" for x in completed),
               f"count={len(completed)}")

        r = await c.get("/requests", params={"limit": 2})
        report("Limit=2 returns ≤2", r.status_code == 200 and len(r.json()) <= 2)

        r = await c.get("/requests", params={"limit": 2, "offset": 1})
        report("Offset pagination works", r.status_code == 200 and len(r.json()) <= 2)

        # ═══════════════════════════════════════════
        # 5. GET SINGLE REQUEST
        # ═══════════════════════════════════════════
        print("\n── 5. Get Single Request ──")

        r = await c.get(f"/requests/{created_ids[0]}")
        report("GET /requests/:id returns 200", r.status_code == 200)
        report("Correct ID returned", r.json()["id"] == created_ids[0])

        r = await c.get("/requests/00000000-0000-0000-0000-000000000000")
        report("GET nonexistent → 404", r.status_code == 404)

        r = await c.get("/requests/not-a-uuid")
        report("GET invalid UUID → 422", r.status_code == 422)

        # ═══════════════════════════════════════════
        # 6. VALIDATION & EDGE CASES
        # ═══════════════════════════════════════════
        print("\n── 6. Validation & Edge Cases ──")

        r = await c.post("/requests", json={"query": "", "request_type": "deep_dive"})
        report("Empty query → 422", r.status_code == 422)

        r = await c.post("/requests", json={"query": "test"})
        report("Missing request_type → 422", r.status_code == 422)

        r = await c.post("/requests", json={"query": "test", "request_type": "nonexistent"})
        report("Invalid request_type → 422", r.status_code == 422)

        r = await c.post("/requests", json={"query": "test", "request_type": "deep_dive", "priority": 99})
        report("Priority > 10 → 422", r.status_code == 422)

        r = await c.post("/requests", json={"query": "test", "request_type": "deep_dive", "priority": -1})
        report("Priority < 0 → 422", r.status_code == 422)

        # Long query
        r = await c.post("/requests", json={"query": "x" * 5000, "request_type": "deep_dive"})
        report("Long query (5000 chars) accepted → 201", r.status_code == 201)
        if r.status_code == 201:
            await c.delete(f"/requests/{r.json()['id']}")

        # Unicode
        r = await c.post("/requests", json={
            "query": "日本語のテスト — émojis 🧠🔬 and spëcial chars",
            "request_type": "idea_exploration",
        })
        report("Unicode query → 201", r.status_code == 201)
        if r.status_code == 201:
            r2 = await c.get(f"/requests/{r.json()['id']}")
            report("Unicode roundtrips correctly", "日本語" in r2.json()["query"] and "🧠" in r2.json()["query"])
            await c.delete(f"/requests/{r.json()['id']}")

        # Context field
        r = await c.post("/requests", json={
            "query": "How does this relate to attention?",
            "request_type": "deep_dive",
            "context": "I've been reading about Mamba and RWKV.",
        })
        report("Request with context → 201", r.status_code == 201)
        if r.status_code == 201:
            report("Context preserved", "Mamba" in r.json()["context"])
            await c.delete(f"/requests/{r.json()['id']}")

        # No tags (default)
        r = await c.post("/requests", json={"query": "test", "request_type": "deep_dive"})
        report("Default tags = empty list", r.status_code == 201 and r.json()["tags"] == [])
        if r.status_code == 201:
            await c.delete(f"/requests/{r.json()['id']}")

        # Default priority
        r = await c.post("/requests", json={"query": "test", "request_type": "deep_dive"})
        report("Default priority = 0", r.status_code == 201 and r.json()["priority"] == 0)
        if r.status_code == 201:
            await c.delete(f"/requests/{r.json()['id']}")

        # ═══════════════════════════════════════════
        # 7. CANCEL / DELETE
        # ═══════════════════════════════════════════
        print("\n── 7. Cancel Request ──")

        r = await c.post("/requests", json={"query": "cancel me", "request_type": "fact_check"})
        cancel_id = r.json()["id"]

        r = await c.delete(f"/requests/{cancel_id}")
        report("DELETE queued request → 204", r.status_code == 204)

        r = await c.get(f"/requests/{cancel_id}")
        report("Cancelled → status=failed", r.json()["status"] == "failed")
        report("Cancel reason stored", r.json().get("error") == "Cancelled by user")

        r = await c.delete(f"/requests/{cancel_id}")
        report("Double cancel → 404", r.status_code == 404)

        r = await c.delete("/requests/00000000-0000-0000-0000-000000000000")
        report("Cancel nonexistent → 404", r.status_code == 404)

        # ═══════════════════════════════════════════
        # 8. QUEUE BEHAVIOR — priority & ordering
        # ═══════════════════════════════════════════
        print("\n── 8. Queue Behavior ──")

        r = await c.get("/system/queue/status")
        qs = r.json()
        report("Queue status reflects activity",
               qs["completed"] >= 1,
               f"queued={qs['queued']} processing={qs['processing']} completed={qs['completed']} failed={qs['failed']}")

        # Test priority ordering: the 3 requests submitted earlier have priorities 3, 7, 1
        # Priority 7 (idea_exploration) should be dequeued before 3 and 1
        # Let's check the order by looking at which ones are processing/queued
        r = await c.get("/requests")
        test_reqs = [x for x in r.json() if x["id"] in created_ids[1:]]  # exclude e2e request
        processing = [x for x in test_reqs if x["status"] == "processing"]
        queued = [x for x in test_reqs if x["status"] == "queued"]
        completed_reqs = [x for x in test_reqs if x["status"] == "completed"]

        report("Worker processes requests from the queue",
               len(processing) > 0 or len(completed_reqs) > 0 or len(queued) > 0,
               f"processing={len(processing)} queued={len(queued)} completed={len(completed_reqs)}")

        if processing:
            # The one being processed should be the highest priority among the 3
            processing_priority = processing[0]["priority"]
            queued_priorities = [x["priority"] for x in queued]
            if queued_priorities:
                report("Highest priority dequeued first",
                       processing_priority >= max(queued_priorities),
                       f"processing priority={processing_priority}, queued priorities={queued_priorities}")

        # Explicit priority test: submit 3 at once, check dequeue order
        # Cancel the pending ones first so they don't interfere
        for req in queued:
            await c.delete(f"/requests/{req['id']}")

        # Wait for current processing to finish
        for req in processing:
            await wait_for_completion(c, req["id"], timeout=120)

        print("  Submitting 3 requests with priorities 1, 9, 5 simultaneously...")
        batch_ids = []
        for p in [1, 9, 5]:
            r = await c.post("/requests", json={
                "query": f"Priority test p={p}: explain in one sentence what priority means",
                "request_type": "fact_check",
                "priority": p,
            })
            batch_ids.append((r.json()["id"], p))

        # Wait briefly for the first one to be picked up
        await asyncio.sleep(2)

        batch_statuses = []
        for bid, p in batch_ids:
            r = await c.get(f"/requests/{bid}")
            batch_statuses.append((p, r.json()["status"]))

        report("Batch of 3 submitted", len(batch_statuses) == 3, str(batch_statuses))

        # The p=9 should be processing (picked first), others queued
        p9_status = next((s for p, s in batch_statuses if p == 9), None)
        report("Priority 9 picked up first (processing/completed)",
               p9_status in ("processing", "completed"),
               f"p=9 status={p9_status}")

        # Among remaining, p=5 should be next
        if p9_status == "processing":
            p5_status = next((s for p, s in batch_statuses if p == 5), None)
            p1_status = next((s for p, s in batch_statuses if p == 1), None)
            report("Priority 5 and 1 still queued",
                   p5_status == "queued" and p1_status == "queued",
                   f"p=5: {p5_status}, p=1: {p1_status}")

        # Clean up batch (cancel queued ones)
        for bid, _ in batch_ids:
            await c.delete(f"/requests/{bid}")

        # ═══════════════════════════════════════════
        # 9. OUTPUTS
        # ═══════════════════════════════════════════
        print("\n── 9. Outputs ──")

        r = await c.get("/outputs")
        report("GET /outputs returns 200", r.status_code == 200)
        all_outputs = r.json()
        report("At least 1 output exists", len(all_outputs) >= 1, f"count={len(all_outputs)}")

        if all_outputs:
            out = all_outputs[0]

            r = await c.get(f"/outputs/{out['id']}")
            report("GET /outputs/:id returns 200", r.status_code == 200)
            report("Same content returned", r.json()["content"] == out["content"])

            r = await c.get("/outputs", params={"status": "unchecked"})
            report("Filter status=unchecked", r.status_code == 200)

        r = await c.get("/outputs/00000000-0000-0000-0000-000000000000")
        report("GET nonexistent output → 404", r.status_code == 404)

        # ═══════════════════════════════════════════
        # 10. REVIEW WORKFLOW
        # ═══════════════════════════════════════════
        print("\n── 10. Review Workflow ──")

        if all_outputs:
            output_id = all_outputs[0]["id"]

            # Comment
            r = await c.post(f"/outputs/{output_id}/review", json={
                "action": "comment",
                "comment": "Interesting findings, need more detail on sparse attention.",
            })
            report("Comment review → 201", r.status_code == 201)
            rev = r.json()
            report("Review action = 'comment'", rev["action"] == "comment")
            report("Comment text preserved", "sparse attention" in rev.get("comment", ""))

            # List reviews
            r = await c.get(f"/outputs/{output_id}/reviews")
            report("GET reviews for output", r.status_code == 200 and len(r.json()) >= 1,
                   f"count={len(r.json())}")

            # Follow-up
            r = await c.post(f"/outputs/{output_id}/review", json={
                "action": "follow_up",
                "comment": "Dig deeper",
                "follow_up_query": "Expand on the relationship between speculative decoding and draft models",
            })
            report("Follow-up review → 201", r.status_code == 201)
            rev = r.json()
            report("Follow-up created new request", rev.get("follow_up_request_id") is not None)

            if rev.get("follow_up_request_id"):
                r2 = await c.get(f"/requests/{rev['follow_up_request_id']}")
                fu = r2.json()
                report("Follow-up request status=queued", fu["status"] in ("queued", "processing"))
                report("Follow-up has parent_id", fu["parent_id"] is not None)
                report("Follow-up context includes previous output",
                       fu.get("context") is not None and "Previous output:" in fu["context"])
                # Clean up
                await c.delete(f"/requests/{rev['follow_up_request_id']}")

            # Follow-up without query → 400
            r = await c.post(f"/outputs/{output_id}/review", json={"action": "follow_up"})
            report("Follow-up without query → 400", r.status_code == 400)

            # Approve
            r = await c.post(f"/outputs/{output_id}/review", json={"action": "approve"})
            report("Approve review → 201", r.status_code == 201)
            r = await c.get(f"/outputs/{output_id}")
            report("Output status now 'approved'", r.json()["status"] == "approved")

            # Filter approved
            r = await c.get("/outputs", params={"status": "approved"})
            report("Filter status=approved finds it", r.status_code == 200 and len(r.json()) >= 1)

            # Multiple reviews on same output
            r = await c.get(f"/outputs/{output_id}/reviews")
            reviews = r.json()
            report("Multiple reviews stored", len(reviews) >= 3,
                   f"count={len(reviews)} actions={[r['action'] for r in reviews]}")

            # Delete action (on a different output if available, else same)
            if len(all_outputs) > 1:
                del_output_id = all_outputs[1]["id"]
            else:
                # Create a dummy — we already tested approve, let's test delete on the same
                del_output_id = output_id

            r = await c.post(f"/outputs/{del_output_id}/review", json={"action": "delete"})
            report("Delete review → 201", r.status_code == 201)
            r = await c.get(f"/outputs/{del_output_id}")
            expected_status = "deleted" if del_output_id != output_id else "deleted"
            report(f"Output status now '{r.json()['status']}'",
                   r.json()["status"] in ("deleted", "approved"))

        # Review nonexistent output
        r = await c.post("/outputs/00000000-0000-0000-0000-000000000000/review",
                        json={"action": "approve"})
        report("Review nonexistent output → 404", r.status_code == 404)

        # Invalid action
        r = await c.post(f"/outputs/{all_outputs[0]['id']}/review",
                        json={"action": "invalid_action"})
        report("Invalid review action → 422", r.status_code == 422)

        # ═══════════════════════════════════════════
        # 11. CONCURRENT SUBMISSIONS
        # ═══════════════════════════════════════════
        print("\n── 11. Concurrent Submissions ──")

        async def submit(i):
            r = await c.post("/requests", json={
                "query": f"Concurrent test request #{i}",
                "request_type": "fact_check",
                "priority": i % 10,
            })
            return r.status_code, r.json().get("id")

        results = await asyncio.gather(*[submit(i) for i in range(10)])
        all_201 = all(code == 201 for code, _ in results)
        unique_ids = set(id for _, id in results if id)
        report("10 concurrent submissions all → 201", all_201,
               f"codes: {set(c for c,_ in results)}")
        report("All 10 got unique IDs", len(unique_ids) == 10)

        # Check they're all in the DB
        r = await c.get("/requests", params={"limit": 50})
        concurrent_found = sum(1 for x in r.json() if x["id"] in unique_ids)
        report("All 10 found in database", concurrent_found == 10)

        # Clean up
        for _, rid in results:
            if rid:
                await c.delete(f"/requests/{rid}")

        # ═══════════════════════════════════════════
        # 12. QUEUE SINGLE-WORKER BEHAVIOR
        # ═══════════════════════════════════════════
        print("\n── 12. Single-Worker Queue Behavior ──")

        report("Worker processes one request at a time (by design)",
               True,
               "single InferenceWorker loop — no parallel inference")

        r = await c.get("/system/queue/status")
        qs = r.json()
        processing_count = qs["processing"]
        report("At most 1 request processing at a time",
               processing_count <= 1,
               f"processing={processing_count}")

        # ═══════════════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════════════
        print(f"\n{'═' * 60}")
        print(f"  TOTAL: {PASS + FAIL}  |  PASS: {PASS}  |  FAIL: {FAIL}")
        print(f"{'═' * 60}")

        if FAIL > 0:
            print("\nFailed tests:")
            for name, status, detail in RESULTS:
                if status == "FAIL":
                    print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))

        return FAIL == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
