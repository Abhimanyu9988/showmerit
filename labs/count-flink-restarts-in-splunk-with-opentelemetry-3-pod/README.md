# Flink job restarts in Splunk Observability Cloud, with the OpenTelemetry Flink receiver

A Flink 1.20 streaming job (the StateMachine example, checkpoints every 5 s) runs on EKS with a fixed-delay restart
strategy, so a lost TaskManager brings it back to RUNNING by itself. The Splunk OTel Collector chart runs on the cluster.

- `reproduce.sh`: Flink, a watcher that reads Flink's REST API once a second, and two TaskManager pod deletions. It
  records, per deletion, how long the job was not RUNNING and how long it said RUNNING before every task ran and a new
  checkpoint completed, the restarts Flink counted, and what the Collector's Kubernetes metrics in Splunk show for the
  TaskManager over the same window (container restarts, available replicas, pod series).
- `fix.sh`: the upstream OpenTelemetry Collector (contrib 0.165.0) with the Flink metrics receiver, sending OTLP to the
  Splunk agent on its node. Three more deletions. It reads Splunk's restart counter and Flink's REST API at the same two
  instants and compares them, polls Splunk every 3 s for arrival lag and reports point lag too, the checkpoint counters, the flink.*
  metric names, and the JVM GC series for the JobManager and the TaskManager.
- `analyze.sh`: turns the watcher's lines into counts (code only). `check.sh`: the free check, the same Flink settings,
  job, watcher and receiver config in Docker. `lib.sh`: shared steps and the Splunk reads (every SignalFlow program is printed).

Deleting the TaskManager pod stands in for a node drain, an eviction or an out-of-memory kill. One job, one TaskManager,
one restart strategy; the receiver reads every 10 s.

## Settings as run (copied from the files in this folder)

- `reproduce.sh` submits the job with `flink run -d -p 2 /opt/flink/examples/streaming/StateMachineExample.jar` (parallelism 2).
- `k8s/10-app.yaml`: one JobManager and one TaskManager, `taskmanager.numberOfTaskSlots: 2`,
  `restart-strategy.type: fixed-delay`, `restart-strategy.fixed-delay.attempts: 1000`,
  `restart-strategy.fixed-delay.delay: 5 s`, `execution.checkpointing.interval: 5 s`.
- `k8s/30-collector.yaml`: image `otel/opentelemetry-collector-contrib:0.165.0`; `HOST_IP` is set from the pod's
  `status.hostIP`. Its config (`LAB_ENV` becomes the lab name):

```yaml
receivers:
  flink_metrics:
    endpoint: http://flink-jobmanager:8081
    collection_interval: 10s
processors:
  resource:
    attributes:
      - {key: deployment.environment, value: LAB_ENV, action: upsert}
  batch:
    timeout: 5s
exporters:
  otlphttp:
    endpoint: http://${env:HOST_IP}:4318
service:
  pipelines:
    metrics:
      receivers: [flink_metrics]
      processors: [resource, batch]
      exporters: [otlphttp]
```

## Context from outside the lab (with sources)

- Code owner: upstream `.github/CODEOWNERS` lists
  `receiver/flinkmetricsreceiver/ @open-telemetry/collector-contrib-approvers @Abhimanyu9988`, and the receiver's
  `metadata.yaml` has `codeowners: active: [Abhimanyu9988]`
  (https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/.github/CODEOWNERS).
- Flink 1.20 metrics page (https://nightlies.apache.org/flink/flink-docs-release-1.20/docs/ops/metrics/), job status
  metrics: "Whether these metrics are reported depends on the metrics.job.status.enable setting." `<jobStatus>TimeTotal`
  returns "how much time (in milliseconds) the job has spent in that state in total."
- The author works at Splunk, part of Cisco; the lab and article are personal work, not sponsored or reviewed by the employer.
