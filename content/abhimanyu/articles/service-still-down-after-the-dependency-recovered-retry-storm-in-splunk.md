---
title: Service Still Down After the Dependency Recovered? See the Retry Storm in Splunk
description: 'A 20-second slowdown on EKS: with instant retries, orders stayed at 0% for the next 70 s in 3 of 3
  runs while inventory worked for callers already gone. Backoff with jitter and a retry budget recovered in 19 to
  28 s.'
date: '2026-11-16'
author: Abhimanyu Bajaj
tags:
- kubernetes
- opentelemetry
- splunk
- aws
lab_url: https://github.com/Abhimanyu9988/showmerit/tree/main/labs/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk
evidence_url: https://github.com/Abhimanyu9988/showmerit/tree/main/labs/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk/evidence
region: eu-central-1
keep_share_image: true
laptop_check: false
linkedin: 'A 20-second slowdown. Then the dependency was healthy again.

  With instant retries, my service still didn''t come back.


  Two Python services on EKS, zero-code OpenTelemetry, 40 orders a second:

  → inventory slows to 2 s a request for 20 s, then it''s fine

  → orders retries failed calls at once, up to 3 more times


  What I measured, 3 runs each:

  Instant retries: 0% success for the next 70 s, 4.00 calls per order, 100% of inventory''s work for callers already
  gone

  Backoff + full jitter + a retry budget: 3 of 3 back to 95% in 19 to 28 s, 1.03 to 1.04 calls per order


  Splunk showed it from the OpenTelemetry metrics alone: 4.29 calls per order in one run, 1.05 in the other.


  If a service stays down after its dependency recovers, check how it retries before anything else.


  I built and tested it in a throwaway AWS account, and the post has every step:

  https://showmerit.com/abhimanyu/articles/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk/


  How do your services retry today?


  #Kubernetes #OpenTelemetry #Splunk #AWS'
---

A dependency slows down for 20 seconds, then it's healthy again. You'd expect your service to come back with it. In my lab on EKS, with instant retries, it didn't: **none of 3 runs got back above 0% success in the 70 seconds after the slowdown ended**, while the dependency stayed busy at full speed on requests whose callers had already given up.

With **exponential backoff, full jitter and a retry budget**, orders was back to 95% success **19 to 28 seconds** after the same slowdown ended, in all 3 of 3 runs. Same code, same load; only the retry policy changed.

Splunk Observability Cloud showed it the same way, straight from the OpenTelemetry metrics: 4.29 calls to inventory per order and every orders request a 503 in the instant-retry run, against 1.05 calls per order and the 503s stopping in the backoff run.

> **TL;DR**
> - Instant retries: 4.00 inventory calls per order after the slowdown, and 100% of inventory's work started after the caller's 500 ms timeout had already passed. Orders failed 2800 of 2800 in the 70-second window.
> - Backoff + full jitter + a 10% retry budget, credited here as one fix: 1.03 to 1.04 calls per order, 46 to 55% late work, back to 95% success in 19 to 28 s.
> - No call was refused or reset; every failed call was a timeout. The retries cost CPU too: orders averaged 0.80 to 0.83 cores with instant retries against 0.22 to 0.27 with the fix.
> - The cost of the fix: 777 to 1086 retries skipped by the budget in the window, and p99 of successful orders at 268 to 321 ms while the backlog drained, against 57 to 61 ms before the slowdown.

## Why this, this week

Recovery under load is the part of an incident that's easy to get wrong. I wanted to see, with numbers on Kubernetes, how retries alone can keep a service down after its dependency is healthy again, and what that looks like in Splunk. For background on timeouts, retries, backoff and cascading failures, see the [AWS Builders' Library](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) and the [Google SRE book](https://sre.google/sre-book/addressing-cascading-failures/).

## The setup

Two Python services on EKS, both started with zero-code OpenTelemetry (`opentelemetry-instrument`), no tracing in the code:

- `orders` takes an order and calls `inventory` with a 500 ms timeout.
- `inventory` has 4 worker threads and takes 40 ms a request, so it can finish about 100 a second.

A load pod sends 40 orders a second for 110 seconds, whatever happens, the way real users keep arriving. At second 20 it asks inventory for a 20-second slowdown: every request takes 2 seconds. Then inventory is healthy again. Each run gets fresh pods and its own order numbers, and the policies alternate, three runs each. (In naive-1, orders' log had no lines from before the slowdown, so its before-latency is missing; every other count for it is there.)

| Policy | What `orders` does when a call fails |
| --- | --- |
| Instant retries | retries at once, up to 3 more times |
| Backoff + jitter + budget | retries up to 3 more times after a random wait of up to 100 ms × 2ⁿ (capped at 2 s), and only while the retry budget allows: each order adds 0.1 of a retry |

Orders also send their deadline (`X-Caller-Deadline`) with each call, so inventory can log whether anyone is still waiting when it starts on a request.

## What happened after the slowdown ended

Orders succeeding, per 10 seconds, in the 70 seconds after the slowdown ended:

| Run | 0-10 s | 10-20 s | 20-30 s | 30-40 s | 40-50 s | 50-60 s | 60-70 s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| naive-1 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 |
| naive-2 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 |
| naive-3 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 | 0/400 |
| budget-1 | 0/400 | 0/400 | 376/400 | 400/400 | 400/400 | 400/400 | 400/400 |
| budget-2 | 0/400 | 42/400 | 400/400 | 400/400 | 400/400 | 400/400 | 400/400 |
| budget-3 | 0/400 | 0/400 | 119/400 | 400/400 | 400/400 | 400/400 | 400/400 |

![Orders succeeding per 10 seconds after the slowdown, three instant-retry runs flat at 0% and three backoff runs back at 100% by the third bucket](/abhimanyu/articles/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk/cover.png)

## Why instant retries kept it down

During the slowdown, every call times out after 500 ms, and every order makes up to 4 calls. Those requests don't vanish when orders gives up on them: they wait in inventory's queue, and inventory works through them one by one. The queue peaked at 894 requests in the instant-retry runs.

When the slowdown ends, inventory goes back to 40 ms a request, but it's now working through requests from callers that left long ago, while each new order adds 4 more calls:

![Inventory calls per order and the share of inventory's work that started after the caller's timeout, per run](/abhimanyu/articles/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk/step-1.png)

- **Instant retries:** inventory finished 81 to 83 requests a second, flat out, and 100% of them started after the caller's 500 ms had passed. Nobody was waiting for any of that work. Orders made 4.00 calls each, the maximum.
- **Backoff + jitter + budget:** 1.03 to 1.04 calls per order, because the budget skipped 777 to 1086 retries in the window. Inventory still had a backlog to clear (46 to 55% of its work was late), but new orders stopped refilling it, so it drained.

Was inventory short of CPU? No: it used 0.51 to 0.53 cores on average in the instant-retry runs, so the limit was its 4 threads and the queue in front of them, and no calls were refused or reset in any run. The caller paid instead: orders averaged 0.80 to 0.83 cores making those retries, against 0.22 to 0.27 with the fix, and the node's busiest second reached 85 to 87% against 52 to 81%.

## What Splunk shows

Both services send traces and their stable OpenTelemetry HTTP metrics to the Splunk OTel Collector. The Splunk APM service map draws `orders` calling `inventory`. The storm itself shows up in two metrics you already have with zero-code instrumentation: `http.client.request.duration_count` on orders, filtered to `server.address=inventory`, counts every call orders made, timeouts included; `http.server.request.duration_count` on the orders route counts the orders. Divide one by the other. Splunk counts every call made in the window, including calls for orders that were still retrying when it ended, while orders' log counts the calls of the orders it finished, so the instant-retry number comes out a little above the maximum of 4:

| Run | Calls to inventory per order, in Splunk | Same window, orders' own log |
| --- | --- | --- |
| naive-2 | 4.29 | 4.00 |
| budget-2 | 1.05 | 1.03 |

And the orders requests and 503s per 10 seconds, read back from Splunk:

![Orders requests and 503s per 10 seconds in Splunk for naive-2 and budget-2](/abhimanyu/articles/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk/step-2.png)

| Run | Orders requests in Splunk | Finished, by orders' own log | Load sent | 503s in Splunk |
| --- | --- | --- | --- | --- |
| naive-2 | 1513 | 1515 | 2400 | 1513 (100.0%) |
| budget-2 | 2422 | 2400 | 2400 | 1142 (47.2%) |

Splunk's orders counts were within 0.9% of what orders itself logged as finished. In the instant-retry run, orders finished fewer requests than the load sent: it was busy too, at 0.80 to 0.83 cores on average, so the retries cost the caller as well as the dependency. Inventory's per-10-second counts in Splunk came out 12-20% lower than inventory's own log for the same windows; I haven't tracked down where that gap comes from, so inventory's numbers here come from its log.

What to look for in Splunk if this happens to you: calls per request from the caller to the dependency stuck near its retry maximum, the dependency's request rate at its ceiling and the caller's error rate at 100%, after whatever slowed it down is gone. A chart of client calls divided by server requests is worth keeping on the caller's dashboard.

## Run it in your own account

```bash
git clone https://github.com/Abhimanyu9988/showmerit.git
cd showmerit/labs/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk
export AWS_REGION=eu-central-1 TF_VAR_region=eu-central-1 LAB_NAME=retry-storm TF_VAR_lab_name=retry-storm
export SPLUNK_REALM=us1 SPLUNK_ACCESS_TOKEN=your-ingest-token SPLUNK_API_TOKEN=your-api-token
terraform init && terraform apply -auto-approve
./reproduce.sh   # cluster setup, then naive-1, budget-1, naive-2 (about 10 minutes)
./fix.sh         # budget-2, naive-3, budget-3 and the Splunk reads (about 10 minutes)
./cleanup.sh && terraform destroy -auto-approve
```

To try the retry policy in your own service, the part that matters is small. In `orders`, before each retry:

```python
if not may_retry():          # each order adds 0.1 token; a retry spends 1
    return False             # fail now instead of adding load
time.sleep(random.uniform(0, min(2.0, 0.1 * 2 ** attempt)))   # full jitter
```

## What to plan for

- **Some orders fail without a retry** while the budget is spent: 777 to 1086 skipped retries per run here. That's the point, but it's a visible cost.
- **Latency while the backlog drains:** p50 of successful orders stayed at 44 ms, but p99 rose to 268 to 321 ms, against 57 to 61 ms before the slowdown.
- **The backlog itself:** inventory still worked on abandoned requests for a while. Server-side load shedding (dropping requests whose deadline has passed) might help with that; I didn't test it here.
- **The fix is a combination:** I didn't measure backoff, jitter and the budget separately, so this shows the three together, not which one did the work.

## What I didn't test

- One load level (40 a second), one timeout (500 ms), one dependency and a simulated slowdown.
- Other languages and HTTP clients, and service meshes that retry on their own.
- Server-side load shedding or deadlines in inventory.

## Sources

- [Timeouts, retries, and backoff with jitter (AWS Builders' Library)](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Addressing Cascading Failures (Google SRE book)](https://sre.google/sre-book/addressing-cascading-failures/)

Disclosure: I work at Splunk, part of Cisco, and contribute to OpenTelemetry. This is my personal writing; the post isn't sponsored or reviewed by my employer.

---
_I built this in a disposable AWS lab (run 43816885975). The [lab code and raw output](https://github.com/Abhimanyu9988/showmerit/tree/main/labs/service-still-down-after-the-dependency-recovered-retry-storm-in-splunk) are public. Drafted with AI assistance and reviewed by me._
