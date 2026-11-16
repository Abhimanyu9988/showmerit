#!/usr/bin/env bash
# BUILD: RETRY_MODE=budget, the combination this post credits as one fix: exponential backoff with full jitter (base 100 ms,
# cap 2 s) and a retry budget (each order adds 0.1 of a retry, so retries stay near 10% of calls). Same code, image, load
# and slowdown. Runs budget-2, naive-3 and budget-3 (reproduce.sh ran naive-1, budget-1, naive-2), then reads the naive-2 and budget-2 windows
# back from Splunk APM and compares them with the lab's own logs.
set -uo pipefail
cd "$(dirname "$0")"
. ./lib.sh
. ./splunk.sh

start_clock 830 not_fixed

aws eks update-kubeconfig --name "$(terraform output -raw cluster_name)" --region "$AWS_REGION" >/dev/null || fail "could not write kubeconfig"
for v in SPLUNK_REALM SPLUNK_ACCESS_TOKEN SPLUNK_API_TOKEN; do [ -n "${!v:-}" ] || fail "$v is not set"; done
LOAD_NODE=$(cat load-node.txt) || fail "no load node recorded"

echo "== 1. The before-check: the cluster's own data reaches Splunk"
wait_cluster "$(cap 90 700)"
echo "cluster metric time series in Splunk: ${cluster:-0}"
[ "${cluster:-0}" -gt 0 ] || fail "no cluster data reached Splunk, so a zero here would prove nothing"

n=2
for run in budget-2 naive-3 budget-3; do
  echo "== $n. Run $run"
  start_run "$run" 100
  load_run "$run" "$(cap 200 120)"
  report "$run"
  n=$(( n + 1 ))
done

echo "== $n. The naive-2 and budget-2 windows in Splunk Observability Cloud, next to the lab's own counts"
for run in naive-2 budget-2; do
  read a0 a1 sent handled _ ofin ocalls _ < "window-$run.txt" || fail "no window recorded for $run"
  stable_count orders all "$a0" "$a1"; total=$count
  stable_count orders true "$a0" "$a1"; errors=$count
  stable_count inventory all "$a0" "$a1"; inv=$count
  stable_count orders client "$a0" "$a1"; calls=$count
  echo "$run, seconds $a0 to $a1: Splunk orders requests $total (errors $errors), orders finished by its own log $ofin (load sent $sent); Splunk inventory requests $inv, lab inventory finished $handled; Splunk calls to inventory $calls, orders log $ocalls"
  pct=$(awk -v e="$errors" -v t="$total" 'BEGIN { if (t > 0) printf "%.1f", 100 * e / t; else print "null" }')
  # The check: Splunk's orders count against the requests orders itself logged as finished in the same window (both count a
  # request when the server finishes it). The load's sent count is printed too: when orders falls behind, it finishes fewer.
  diff=$(awk -v a="$total" -v b="$ofin" 'function ab(x) { return x < 0 ? -x : x } BEGIN { if (b > 0) printf "%.1f", 100 * ab(a - b) / b; else print "null" }')
  idiff=$(awk -v a="$inv" -v b="$handled" 'function ab(x) { return x < 0 ? -x : x } BEGIN { if (b > 0) printf "%.1f", 100 * ab(a - b) / b; else print "null" }')
  echo "$run: Splunk's orders count differs from orders' own log by $diff%; inventory's by $idiff%"
  echo "HERO_MEASURE: splunk_orders_error_pct_after[$run]=$pct"
  echo "HERO_MEASURE: splunk_log_diff_pct[$run]=$diff"
  echo "HERO_MEASURE: splunk_inventory_diff_pct[$run]=$idiff"
  # The retry storm as Splunk sees it: calls orders made to inventory (its HTTP client metric) per order request
  cpo=$(awk -v c="$calls" -v t="$total" 'BEGIN { if (t > 0) printf "%.2f", c / t; else print "null" }')
  echo "$run: in Splunk, orders made $calls calls to inventory for $total order requests ($cpo per order); orders' log: $ocalls for $ofin"
  echo "HERO_MEASURE: splunk_inventory_calls_per_order[$run]=$cpo"
  [ "$run" = budget-2 ] && splunk_total=$total
done
echo "-- the service map in Splunk APM for this environment"
show_map <<<"$(topology)"

# The gate: every budget run started healthy (report checks that) and recovered inside its window, and Splunk returned
# the budget-2 window. Whether a naive run recovers is a result, not a gate.
all=1
for run in budget-1 budget-2 budget-3; do
  r=$(sed -n "s/^HERO_MEASURE: recovery_after_slowdown\[$run\/recovered\]=//p" "report-$run.txt" 2>/dev/null)
  echo "$run recovered within the window: ${r:-unknown}"
  [ "${r:-0}" = 1 ] || all=0
done
if [ "$all" = 1 ] && [ "${splunk_total:-0}" -gt 0 ]; then
  emit fixed
else
  emit not_fixed
fi
