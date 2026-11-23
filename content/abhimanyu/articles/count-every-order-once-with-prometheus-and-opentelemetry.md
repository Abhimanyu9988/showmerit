---
title: I Sold 200 Orders. My Dashboard Said 400.
description: Two monitoring agents counted the same 200 orders, so Splunk showed 400. Letting each Splunk OTel Collector agent
  read only its own Kubernetes node brought it back to 200, matching OpenTelemetry.
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
linkedin: 'I sold 200 orders. My dashboard said 400.


  Nobody bought twice. Two helpers were counting the same orders.


  I''d put a monitoring agent on each of my two Kubernetes servers. Both agents counted every order, and Splunk added them
  up.


  One small setting fixed it: each agent counts only what runs on its own server. Back to 200.


  If a number drives your decisions, check who''s counting it.


  https://showmerit.com/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/


  I work at Splunk, part of Cisco. Views are my own.


  #Observability #Kubernetes #OpenTelemetry'
---

Picture a small café with two cashiers. A customer buys one coffee, and both cashiers ring it up. At closing time the till says two coffees were sold. The coffee machine knows better.

That happened in my lab. The café was a small online store, and the till was my monitoring dashboard.

![Splunk Observability Cloud chart and data table: the Prometheus counter at 400 for the everywhere runs while OpenTelemetry's POST count is 200](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/cover.png)

## 200 orders, 400 on the dashboard

My little ordering app ran on Kubernetes across two servers, which Kubernetes calls nodes. Each copy of the app kept a tally of orders in Prometheus format, a common open way for apps to publish numbers. A Splunk OpenTelemetry Collector agent on each server read those tallies and sent them to Splunk for charts and alerts.

I sent 200 orders. All 200 succeeded. Splunk said 400.

![Splunk data table for everywhere-1: four series of orders_created_total summing to 400, two per pod, told apart by host.id, host.name and availability zone](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/step-1.png)

The app also reported its successful orders through OpenTelemetry, and that said 200. Here the two numbers match by design, because the tally goes up once per successful order. In other apps they can differ.

Splunk held two lines of data for each copy of the app, one per server. Both agents were reading both copies. Two cashiers, one coffee.

## Why it matters

Nothing was broken. Every customer got one order. But the dashboard showed double the sales, and an alert on that number would fire at the wrong time. Splunk and OpenTelemetry did what I asked. My instruction, "every agent, read every app", was the problem.

## The fix

![Before and after: with a cluster-wide scrape job both agents scrape both orders pods and Splunk shows 400 over 4 series; scoped to the agent's node, each pod has one scraper and Splunk shows 200 over 2 series; OpenTelemetry shows 200 in both](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/diagram.png)

Each copy of an app lives on one server, so I told each agent to read only the apps on its own server. Two ways worked: one extra rule in my own scrape job (a node field selector), or the agent's built-in Prometheus autodetection, which already stays on its own server.

Back to 200 in every fixed run, six runs in all:

| Run | Agent-app pairs | Prometheus counter in Splunk | Lines of data (most per app) | OpenTelemetry count |
| --- | --- | --- | --- | --- |
| everywhere-1 | 4 | 400 | 4 (2) | 200 |
| everywhere-2 | 4 | 400 | 4 (2) | 200 |
| node-1 | 2 | 200 | 2 (1) | 200 |
| node-2 | 2 | 200 | 2 (1) | 200 |
| autodetect-1 | 2 | 200 | 2 (1) | 200 |
| autodetect-2 | 2 | 200 | 2 (1) | 200 |

![Splunk data table: the autodetect runs at 200 for both the Prometheus counter and OpenTelemetry's POST count](/abhimanyu/articles/count-every-order-once-with-prometheus-and-opentelemetry/step-2.png)

Next time a number drives a decision, I'll ask first: who is counting this, and how many of them are there?

## Try it yourself

You need an AWS account and a Splunk Observability Cloud account. The lab code and the raw output of all six runs are in the [evidence folder](https://github.com/Abhimanyu9988/showmerit/tree/main/labs/count-every-order-once-with-prometheus-and-opentelemetry/evidence).

The two fixes, as chart values. The node field selector on your own scrape job (the chart sets `K8S_NODE_NAME` on every agent):

```yaml
kubernetes_sd_configs:
  - role: pod
    namespaces:
      names: [demo]
    selectors:
      - role: pod
        field: spec.nodeName=${env:K8S_NODE_NAME}
```

Or autodetection, which scrapes pods annotated `prometheus.io/scrape: "true"` from their own node:

```yaml
autodetect:
  prometheus: true
```

### Step 1: Create the cluster (EKS took 7m8s in my run, on two t3.large nodes)

```bash
git clone https://github.com/Abhimanyu9988/showmerit.git
cd showmerit/labs/count-every-order-once-with-prometheus-and-opentelemetry
export AWS_REGION=eu-central-1 LAB_NAME=prom-lab TF_VAR_lab_name=prom-lab
export SPLUNK_REALM=us1 SPLUNK_ACCESS_TOKEN=your-ingest-token SPLUNK_API_TOKEN=your-api-token
terraform init && terraform apply -auto-approve
```

You get EKS 1.34 with two t3.large nodes. The app is one Flask service with prometheus-client 0.26.0 and zero-code OpenTelemetry 0.66b2, as `orders-a` on one node and `orders-b` on the other.

### Step 2: The cluster-wide scrape job (333 s in my run)

Run `./reproduce.sh`. It installs the Splunk OTel Collector chart 0.163.1 with `values-everywhere.yaml`, deploys both pods, runs everywhere-1 and everywhere-2 (20 s at 10 orders a second each) and reads everywhere-1 back from Splunk.

### Step 3: The two node-scoped configs (601 s in my run)

Run `./fix.sh`. It switches the agents to `values-node.yaml`, then `values-autodetect.yaml`, two runs each, and reads all six runs back from Splunk. Before each switch it stops the last run's pods, so no run is scraped under two configs.

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
