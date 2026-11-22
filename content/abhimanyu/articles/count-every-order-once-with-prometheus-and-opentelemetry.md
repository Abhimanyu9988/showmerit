---
title: '200 Orders, 400 in Splunk: How a DaemonSet Doubled My Prometheus Metrics'
description: 'I sent 200 orders and Splunk''s Prometheus counter showed 400: both Splunk OTel Collector DaemonSet agents scraped
  both pods. A node field selector or autodetect.prometheus brought it back to 200, matching OpenTelemetry.'
date: '2026-11-22'
linkedin_date: '2026-11-23'
author: Abhimanyu Bajaj
tags:
- opentelemetry
- splunk
- kubernetes
- prometheus
lab_url: https://github.com/Abhimanyu9988/showmerit/tree/main/labs/count-every-order-once-with-prometheus-and-opentelemetry
evidence_url: https://github.com/Abhimanyu9988/showmerit/tree/main/labs/count-every-order-once-with-prometheus-and-opentelemetry/evidence
region: eu-central-1
keep_share_image: true
laptop_check: false
linkedin: 'I sent 200 orders to an application running on EKS.


  All 200 succeeded. The application counted 200.


  Then I checked Splunk. The Prometheus counter showed 400.


  My first thought was that something was wrong with the metric. But OpenTelemetry''s independently collected count of successful
  POST requests was still 200.


  So I checked who was scraping the pods.


  I''d deployed the Splunk OTel Collector as a DaemonSet across two nodes. My Prometheus scrape job used cluster-wide Kubernetes
  pod discovery.


  Both agents were scraping both pods.


  Same business counter, collected twice. Four time series in Splunk instead of two.


  I tested two fixes: a node field selector and the chart''s autodetect.prometheus: true.


  Both worked across four runs.


  200 orders. 200 in Splunk. One scraper per pod.


  The application never needed changing.


  This matters because duplicated metrics can quietly inflate business dashboards and trigger alerts against numbers that
  don''t represent actual application activity.


  I published the configurations, all six runs and raw evidence:


  https://showmerit.com/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/


  Have you checked how many Collector agents are scraping each of your Prometheus targets?


  I work at Splunk, part of Cisco. Views are my own.


  #OpenTelemetry #Prometheus #Kubernetes #Observability'
---

I sent 200 orders to my application. All 200 succeeded.

Then I opened Splunk and saw 400 in the Prometheus counter.

That didn't make sense. The application itself had counted 200 orders, and OpenTelemetry was reporting 200 successful POST requests. But the Prometheus metric in Splunk was exactly double.

I wanted to understand where the extra 200 came from.

![Splunk Observability Cloud chart and data table: the Prometheus counter at 400 for the everywhere runs while OpenTelemetry's POST count is 200](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/cover.png)

The application was running on EKS, with two orders pods spread across two nodes. I had installed the Splunk OTel Collector as a DaemonSet, with one agent on each node.

Nothing unusual about that setup. The mistake was in the Prometheus scrape job I'd added.

## Finding where the extra metrics came from

My first configuration used Kubernetes pod discovery without a node filter.

Each Collector agent discovered both orders pods. Since the Collector ran as a DaemonSet, both agents scraped both pods.

The pods hadn't processed any extra orders. I was collecting the same business counter twice, once through each agent.

The lab confirmed it:

```text
HERO_MEASURE: pod_scrapers[everywhere-1]=4
HERO_MEASURE: splunk_prometheus_orders[everywhere-1]=400
HERO_MEASURE: splunk_series_per_pod_max[everywhere-1]=2
HERO_MEASURE: splunk_otel_orders[everywhere-1]=200
```

There were four scraper-pod pairs: two agents scraping two pods.

Splunk held four Prometheus series, with two series per pod.

![Splunk data table for everywhere-1: four series of orders_created_total summing to 400, two per pod, told apart by host.id, host.name and availability zone](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/step-1.png)

I checked which dimensions separated those series.

For each pod, the two copies differed in `host.name`, `host.id`, `cloud.availability_zone` and `AWSUniqueId`.

Those dimensions identified the node running each Collector agent. The chart's resource detection was doing its job.

The problem was that my scrape configuration let both agents discover the same target. When I summed those series in Splunk, I counted each pod's counter once per agent.

This behavior has also been discussed in [Collector discussion 9998](https://github.com/open-telemetry/opentelemetry-collector/discussions/9998) and [collector-contrib issue 48546](https://github.com/open-telemetry/opentelemetry-collector-contrib/issues/48546).

## Why OpenTelemetry still showed 200

I had two different measurements.

`orders_created_total` was a Prometheus business counter, incremented by the application's POST handler.

The OpenTelemetry measurement came from zero-code HTTP instrumentation. I counted successful POST requests using `http.server.request.duration_count`, filtered to `http.request.method` POST and `http.response.status_code` 200.

In this lab, the handler incremented the business counter on every successful POST and nothing else. That is why both measurements should match.

They aren't universally interchangeable. Failed orders, retries or different routes could make the numbers diverge in another application.

Here, OpenTelemetry's successful POST count stayed at 200 across all six runs. That gave me an independent measurement to compare against the scraped business counter.

## Fixing the scrape scope

I didn't need to change the application. I needed each agent to scrape only the pods running on its own node.

I tested two configurations.

![Before and after: with a cluster-wide scrape job both agents scrape both orders pods and Splunk shows 400 over 4 series; scoped to the agent's node, each pod has one scraper and Splunk shows 200 over 2 series; OpenTelemetry shows 200 in both](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/diagram.png)

### Option 1: Keep the scrape job, add a node selector

The chart already exposes `K8S_NODE_NAME` from the agent pod's `spec.nodeName`.

I added one field selector to Kubernetes pod discovery:

```yaml
kubernetes_sd_configs:
  - role: pod
    namespaces:
      names: [demo]
    selectors:
      - role: pod
        field: spec.nodeName=${env:K8S_NODE_NAME}
```

Each agent now discovered only pods scheduled on its own node.

### Option 2: Use Prometheus autodetection

I also tested the chart's built-in autodetection:

```yaml
autodetect:
  prometheus: true
```

With this setting, the chart's `receiver_creator` watches the node-scoped `k8s_observer`, configured with `node: ${K8S_NODE_NAME}`.

Pods annotated with `prometheus.io/scrape: "true"` are scraped by their local agent.

No custom scrape job was needed.

## What changed in Splunk

After adding the field selector, the next run showed:

```text
HERO_MEASURE: pod_scrapers[node-1]=2
HERO_MEASURE: splunk_prometheus_orders[node-1]=200
HERO_MEASURE: splunk_series_per_pod_max[node-1]=1
```

One scraper per pod. One Prometheus series per pod.

I then switched to autodetection:

```text
HERO_MEASURE: splunk_prometheus_orders[autodetect-1]=200
```

The result held across both runs of each configuration.

| Run | Scraper-pod pairs | Prometheus counter in Splunk | Series (most per pod) | OpenTelemetry count |
| --- | --- | --- | --- | --- |
| everywhere-1 | 4 | 400 | 4 (2) | 200 |
| everywhere-2 | 4 | 400 | 4 (2) | 200 |
| node-1 | 2 | 200 | 2 (1) | 200 |
| node-2 | 2 | 200 | 2 (1) | 200 |
| autodetect-1 | 2 | 200 | 2 (1) | 200 |
| autodetect-2 | 2 | 200 | 2 (1) | 200 |

Every run sent 200 orders. All 200 succeeded, and the pods counted 200 themselves.

Before each configuration switch, I stopped the previous run's pods so they couldn't be scraped under two configurations.

![Splunk data table: the autodetect runs at 200 for both the Prometheus counter and OpenTelemetry's POST count](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/step-2.png)

The complete raw output, including scraper IPs, series dimensions and per-run checks, is in the lab's [evidence folder](https://github.com/Abhimanyu9988/showmerit/tree/main/labs/count-every-order-once-with-prometheus-and-opentelemetry/evidence).

## Run it yourself

I used EKS 1.34 on two t3.large nodes. The application was a Flask service using prometheus-client 0.26.0 and zero-code OpenTelemetry 0.66b2, deployed as `orders-a` and `orders-b`.

### Step 1: Create the cluster (EKS took 7m8s in my run, on two t3.large nodes)

```bash
git clone https://github.com/Abhimanyu9988/showmerit.git
cd showmerit/labs/count-every-order-once-with-prometheus-and-opentelemetry
export AWS_REGION=eu-central-1 LAB_NAME=prom-lab TF_VAR_lab_name=prom-lab
export SPLUNK_REALM=us1 SPLUNK_ACCESS_TOKEN=your-ingest-token SPLUNK_API_TOKEN=your-api-token
terraform init && terraform apply -auto-approve
```

### Step 2: The cluster-wide scrape job (333 s in my run)

Run `./reproduce.sh`. It installs the Splunk OTel Collector chart 0.163.1 with `values-everywhere.yaml`, deploys both pods, runs everywhere-1 and everywhere-2 (20 s at 10 orders a second each) and reads everywhere-1 back from Splunk.

### Step 3: The two node-scoped configs (601 s in my run)

Run `./fix.sh`. It switches the agents to `values-node.yaml`, then `values-autodetect.yaml`, two runs each, and reads all six runs back from Splunk. Before each switch it stops the last run's pods, so no run is scraped under two configs.

## What I'd check in a real deployment

The first thing I'd inspect is the number of Prometheus series per pod.

In this lab, two series for the same pod meant two agents were scraping it. The dimensions told me where those agents were running.

On a larger cluster, the potential multiplier grows with the number of agents scraping each pod. A cluster-wide job running in every DaemonSet agent could turn one application counter into many collected copies.

That can distort dashboards, business KPIs and alert thresholds even when the application processes each order only once. I didn't measure those production consequences here.

If you already maintain a custom Prometheus job, the node field selector is a small change. If annotations suit your deployment, autodetection is another option, but first check which pods carry `prometheus.io/scrape: "true"`.

You can also instrument a business counter directly with OpenTelemetry and push it over OTLP, avoiding scraping for that metric.

Splunk helped me see the duplicated series and identify the dimensions separating them. The configuration was the issue, not Splunk or OpenTelemetry.

I started with 200 successful orders and 400 in a dashboard. I finished with the same 200 orders, one scraper per pod and a Prometheus count that agreed with the application's counter.

The thing I'll check earlier next time is who is scraping each target.

## Clean up (the cluster costs money while it runs)

```bash
./cleanup.sh
terraform destroy -auto-approve
```

## What I didn't test

- **Cluster-level endpoints** such as kube-state-metrics, which live on one node and suit a single scraper or the Target Allocator.
- **Nodes without an agent:** node-scoped discovery doesn't scrape a pod there.
- **Scale:** one app, two nodes, one load level and a 10 s scrape interval.

## Sources

- [collector-contrib issue 48546: Prometheus receiver and leader election on a DaemonSet](https://github.com/open-telemetry/opentelemetry-collector-contrib/issues/48546)
- [Collector discussion 9998: multiple Collector pods give duplicate metrics](https://github.com/open-telemetry/opentelemetry-collector/discussions/9998)
- [Kubernetes Cluster Observability blueprint (OpenTelemetry)](https://opentelemetry.io/docs/guidance/blueprints/k8s-observability-blueprint/)
- [Kubernetes Prometheus Node source (Bindplane)](https://docs.bindplane.com/integrations/sources/kubernetes-prometheus-node)
- [Splunk OTel Collector chart values, autodetect.prometheus](https://github.com/signalfx/splunk-otel-collector-chart/blob/main/helm-charts/splunk-otel-collector/values.yaml)

Disclosure: I work at Splunk, part of Cisco. This is my personal blog; the post isn't sponsored or reviewed by my employer.

---
_I built this in a disposable AWS lab. The lab code and raw output are in the repo. Drafted with AI assistance and reviewed by me._
