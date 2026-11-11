---
title: One OTel Java Agent Variable Puts Per-Statement Postgres Metrics in Splunk
description: One environment variable took db.client.operation.duration from 0 series
  to 14 per Postgres statement in Splunk on EKS, on the same jar and image, with no
  code changes.
date: '2026-11-11'
author: Abhimanyu Bajaj
tags:
- opentelemetry
- splunk
- postgresql
- kubernetes
lab_url: https://github.com/Abhimanyu9988/showmerit/tree/main/labs/one-otel-java-agent-variable-puts-per-statement-postgres
evidence_url: https://github.com/Abhimanyu9988/showmerit/tree/main/labs/one-otel-java-agent-variable-puts-per-statement-postgres/evidence
region: eu-central-1
keep_share_image: true
laptop_check: false
linkedin: 'Postgres time per statement usually starts with someone adding a timer.

  Mine came from one environment variable and no code changes.


  The OpenTelemetry Java agent records db.client.operation.duration once you opt in.


  → OTEL_SEMCONV_STABILITY_OPT_IN=database on each service

  → Splunk Observability Cloud stores the metric per statement

  → Each statement gets its own count, sum and buckets


  What I measured on real EKS, on the same jar and image:

  0 series before, 14 per statement after

  6,971 lookups counted, 0.8% from what the load sent

  Mean time within 3.3% of pg_stat_statements on a test statement


  The post also shows how to count the dimensions on your series, so you know how
  much room you have before adding attributes.


  I built and tested it in a throwaway AWS account, and the post has every step:

  https://showmerit.com/abhimanyu/articles/one-otel-java-agent-variable-puts-per-statement-postgres/


  Which Postgres statement would you chart first?'
---

You open Splunk to see how long your Java services spend in Postgres, and you want it per statement. The metric for that is `db.client.operation.duration`, and the OpenTelemetry Java agent records it once you opt in.

One setting did it. **`OTEL_SEMCONV_STABILITY_OPT_IN=database` took the metric from 0 series to 14 per statement in Splunk Observability Cloud, on the same jar and image, with no code changes.** Each statement gets its own count, sum, minimum, maximum and histogram buckets.

![Dashboard charted from real Splunk series for the lab run: orders and inventory on Spring Boot calling Postgres 16.4, 0 to 14 series per statement, a 3.3% mean gap against pg_stat_statements, and graphs of requests, inventory latency and JVM memory](/abhimanyu/articles/one-otel-java-agent-variable-puts-per-statement-postgres/cover.png)

> **TL;DR**
> - One environment variable gives you Postgres metrics per statement, with no code changes.
> - Splunk counted 6,971 lookups against about 6,917 sent, a 0.8% gap.
> - The mean per statement came within 3.3% of `pg_stat_statements` on a test statement.
> - On EKS the bucket series carries 36 dimensions, so count yours before you add attributes.
> - Allow about 7 minutes for the cluster and 20 for the scripts, on two `t3.large` nodes.

## Why the chart starts empty, by design

The agent lets a team choose when it moves to the stable database conventions. The [agent's docs](https://github.com/open-telemetry/opentelemetry-java-instrumentation/blob/v2.33.1/docs/supported-libraries.md) list database client metrics for those who opt in, and [this discussion](https://github.com/open-telemetry/opentelemetry-java-instrumentation/discussions/16419) shows an engineer looking for this exact metric.

With agent 2.33.1 attached and no opt-in, pool metrics arrived from the load and this metric wasn't there yet:

```text
time series for db.client.operation.duration with no opt-in: 0
connection pool metric series for the same load: 1
```

## One environment variable, on the same jar

```bash
kubectl -n demo set env deployment/orders OTEL_SEMCONV_STABILITY_OPT_IN=database
kubectl -n demo set env deployment/inventory OTEL_SEMCONV_STABILITY_OPT_IN=database
```

The system property `otel.semconv-stability.opt-in=database` works too, and the lab ran both.

The setting also moves span attributes and pool metrics to stable names, so check any dashboards on the old ones. Splunk held 19 metric names under `db.client.connection`, and `database/dup` emitted both sets of span attributes during a move.

## Build it yourself in 3 steps

### Step 1: Create the cluster (about 7 minutes)

```bash
git clone https://github.com/Abhimanyu9988/showmerit.git
cd showmerit/labs/one-otel-java-agent-variable-puts-per-statement-postgres
export AWS_REGION=eu-central-1 LAB_NAME=pg-metrics TF_VAR_lab_name=pg-metrics
export SPLUNK_REALM=us1 SPLUNK_ACCESS_TOKEN=your-ingest-token SPLUNK_API_TOKEN=your-api-token
terraform init && terraform apply -auto-approve
```

### Step 2: Measure before, then the setting alone (about 9 minutes)

Run `./reproduce.sh`. It installs the Splunk OTel Collector with chart 0.163.1, builds one jar, and starts `orders`, `inventory` and Postgres with the agent and no opt-in. After a load and a read of Splunk, it sets the opt-in and reads again. It allows about two minutes for that read, and the series was already there at the first look:

```text
opt-in alone in Splunk after a read of 1s: control series 4, audit statement bucket series 10, dimensions on them 36
```

The control is `db.client.connection.count`, which exists only with the opt-in.

### Step 3: Run the main load and read it back (about 11 minutes)

Run `./fix.sh`. It aims for one request every 50 ms for nine minutes, and reads the metric back through the SignalFlow stream.

## What Splunk held: 14 series per statement

The app runs an audit count in `orders`, and an update, a lookup and a known-latency statement in `inventory`. That last one is `select pg_sleep(0.03), qty from reserved where id = ?`, on every fourth request.

![Line charts of requests and inventory latency across the three load stretches of the run](/abhimanyu/articles/one-otel-java-agent-variable-puts-per-statement-postgres/step-2.png)

| What | Result | Read or computed |
| --- | --- | --- |
| Series before the setting | 0 | read from Splunk |
| Series per statement after | 14: 10 `_bucket`, one per stored `le`, plus `_count`, `_sum`, `_min`, `_max` | read from Splunk |
| Lookups counted over 6 minutes | 6,971 against about 6,917 sent, 0.8% apart | computed |
| Load reached | 19.1 requests a second | computed |

By the load's own per-minute counts, export timing allows 6,863 to 6,971, and Splunk's count sits at the top of that range.

## Know your room: 36 dimensions per series

Splunk holds [36 dimensions per series](https://help.splunk.com/en/splunk-observability-cloud/administer/org-reference-info/per-product-system-limits-in-splunk-observability-cloud/infrastructure-system-limits), and on EKS with chart defaults this metric's bucket series carried 36:

![Bars showing the metric's bucket series at 36 dimensions, its count series at 35, and test points at 30 and 36 held while 37 and 40 were not](/abhimanyu/articles/one-otel-java-agent-variable-puts-per-statement-postgres/step-3.png)

My test points at 30 and 36 dimensions were held, and those at 37 and 40 weren't. The count includes 20 resource attributes from the agent and 8 cloud and host attributes from the Collector, so plan any extra resource attribute with that in mind. If you also want HTTP histograms on the same services, count their dimensions the same way first.

## Use the mean for accuracy

`_sum` divided by `_count` gives a mean per statement. For the test statement it read 31.88 ms, against 30.85 ms from `pg_stat_statements`, a gap of 3.3%. Postgres times the server only, and its figure also covers the warm-up, so the two aren't the same clock.

The app ran on a burstable `t3.large` node, which was low on CPU credits during the load (19.21% steal), so read every latency figure here as context. Counts and dimensions don't depend on that.

## Read a p95 with its bucket in mind

Stored buckets decide what a percentile can tell you. The `le` edges around this statement are 0.01 and 0.05, so 10 and 50 ms, and nearly every call lands in that one bucket. A straight-line estimate inside it gives 10 + 0.95 × 40 = 48, which is what the program read.

This is the program as it ran, with your environment name in it:

```text
data('db.client.operation.duration_bucket', filter=filter('deployment.environment', 'YOUR_ENV') and filter('db.query.summary', 'select reserved'), rollup='delta').sum(by=['le']).histogram_percentile(pct=95, bucket_name='le').scale(1000).publish('p95_ms')
```

```text
histogram_percentile() p95: median 47.99, min 47.97, max 48.52
timer p95: median 36.33, min 32.55, max 42.17
```

![Per-minute lines of the SignalFlow p95 near 48 ms and the timer p95 falling from 42 to 33 ms, both between the stored edges at 10 and 50 ms](/abhimanyu/articles/one-otel-java-agent-variable-puts-per-statement-postgres/step-4.png)

Both readings sit inside the same 10 to 50 ms bucket, so quote the bucket alongside the number. The timer is test scaffolding around that one JDBC call in `inventory`, so "no code changes" stands for your services.

## Use it for your own services

- **Count before you add attributes.** The `/v2/metrictimeseries` reply lists each series' dimensions. Leave out `sf_metric`, which isn't one.
- **Keep room when you need it.** `otel.java.disabled.resource.providers` can leave out the agent's process attributes. That took the agent's resource attributes from 20 to 14 in one short run.

## Clean up (the cluster costs money while it runs)

```bash
./cleanup.sh
terraform destroy -auto-approve
```

## What I didn't test

- **Latency on a steady node.** Use a non-burstable node to measure your own.
- **A p95 in a narrower bucket.** One statement in one wide bucket can't test the estimate.
- **The trim under load.** I counted attributes with it on, and didn't run the main load with it.
- **Other databases, connection pools or agent versions.**

## Sources

- [Supported libraries, agent 2.33.1](https://github.com/open-telemetry/opentelemetry-java-instrumentation/blob/v2.33.1/docs/supported-libraries.md)
- [Unable to collect db.client.operation.duration](https://github.com/open-telemetry/opentelemetry-java-instrumentation/discussions/16419)
- [Infrastructure system limits (Splunk)](https://help.splunk.com/en/splunk-observability-cloud/administer/org-reference-info/per-product-system-limits-in-splunk-observability-cloud/infrastructure-system-limits)
- [Get histogram data in (Splunk)](https://help.splunk.com/en/splunk-observability-cloud/manage-data/metrics-metadata-and-events/metrics-events-and-metadata/get-histogram-data-in)
- [histogram_percentile() (Splunk)](https://dev.splunk.com/observability/docs/signalflow/functions/histogram_percentile_function)

Disclosure: I work at Splunk, part of Cisco. This is my personal writing; the post isn't sponsored or reviewed by my employer.

---
_I built this in a disposable AWS lab. The [lab code and raw output](https://github.com/Abhimanyu9988/showmerit/tree/main/labs/one-otel-java-agent-variable-puts-per-statement-postgres) are public. Drafted with AI assistance and reviewed by me._
