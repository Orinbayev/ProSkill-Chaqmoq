#!/usr/bin/env python3
import argparse
import json
import os
import re
import statistics
import time
import tracemalloc
from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import Center  # noqa: E402
from billing.models import SubscriptionRequest  # noqa: E402
from chaqmoq.models import Ledger  # noqa: E402
from core.models import Notification  # noqa: E402
from education.models import Attendance, Enrollment, Group, Payment  # noqa: E402


def normalize_sql(sql: str) -> str:
    sql = sql or ""
    sql = sql.lower()
    sql = re.sub(r"'[^']*'", "?", sql)
    sql = re.sub(r'"[^"]*"', '"?"', sql)
    sql = re.sub(r"\b\d+\b", "?", sql)
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql[:300]


def setup_users_and_clients():
    User = get_user_model()

    center = (
        Center.objects.filter(is_deleted=False, status="ACTIVE")
        .order_by("-id")
        .first()
    )
    if not center:
        raise RuntimeError("No active center found for benchmark")

    tenant_user = (
        User.objects.filter(center=center, role="director", is_deleted=False)
        .order_by("id")
        .first()
    )
    if not tenant_user:
        tenant_user = (
            User.objects.filter(center=center, role="manager", is_deleted=False)
            .order_by("id")
            .first()
        )
    if not tenant_user:
        tenant_user = (
            User.objects.filter(center=center, is_superuser=True, is_deleted=False)
            .order_by("id")
            .first()
        )

    superuser = User.objects.filter(is_superuser=True, is_deleted=False).order_by("id").first()

    if not tenant_user:
        raise RuntimeError("No tenant user (director/manager/superuser) found for benchmark")
    if not superuser:
        raise RuntimeError("No superuser found for benchmark")

    tenant_client = Client()
    tenant_client.force_login(tenant_user)
    tenant_session = tenant_client.session
    tenant_session["active_center_id"] = int(center.id)
    tenant_session.save()

    super_client = Client()
    super_client.force_login(superuser)
    super_session = super_client.session
    super_session["active_center_id"] = int(center.id)
    super_session.save()

    return center, tenant_user, superuser, tenant_client, super_client


def build_endpoints(center):
    User = get_user_model()
    slug = center.slug

    group = (
        Group.objects.filter(center=center, is_archived=False, is_deleted=False)
        .order_by("id")
        .first()
    )
    student = (
        User.objects.filter(center=center, role="student", is_archived=False, is_deleted=False)
        .order_by("id")
        .first()
    )
    sub_req = SubscriptionRequest.objects.filter(center=center).order_by("-id").first()

    if not group:
        group = Group.objects.filter(center=center).order_by("id").first()
    if not student:
        student = User.objects.filter(role="student", is_deleted=False).order_by("id").first()
    if not sub_req:
        sub_req = SubscriptionRequest.objects.order_by("-id").first()

    year = timezone.localdate().year
    req_id = sub_req.id if sub_req else 1
    group_id = group.id if group else 1
    student_id = student.id if student else 1

    tenant_endpoints = [
        ("dashboard_home", "GET", f"/{slug}/"),
        ("students_list", "GET", f"/{slug}/stat/students/"),
        ("groups_list", "GET", f"/{slug}/talim/groups/"),
        ("attendance_groups", "GET", f"/{slug}/talim/attendance/groups/"),
        ("group_month_attendance", "GET", f"/{slug}/talim/attendance/groups/{group_id}/"),
        ("payments_list", "GET", f"/{slug}/talim/tolovlar/"),
        ("debtors_list", "GET", f"/{slug}/talim/qarzdorlar/"),
        ("notifications", "GET", f"/{slug}/notifications/"),
        ("chaqmoq_leaderboard", "GET", f"/{slug}/chaqmoq/reyting/"),
        ("chaqmoq_student_history", "GET", f"/{slug}/chaqmoq/student/{student_id}/"),
        ("billing_plans", "GET", f"/{slug}/hisob/billing/plans/"),
        (
            "billing_payment_status_api",
            "GET",
            f"/{slug}/hisob/billing/api/payment-status/?ids={req_id}",
        ),
    ]

    super_endpoints = [
        ("superadmin_dashboard", "GET", "/platform/"),
        ("superadmin_centers", "GET", "/platform/centers/"),
        ("superadmin_center_stats", "GET", f"/platform/centers/{center.id}/stats/"),
    ]

    return tenant_endpoints, super_endpoints


def run_request(client: Client, method: str, path: str):
    if method == "GET":
        return client.get(path, follow=False)
    if method == "POST":
        return client.post(path, data={}, follow=False)
    raise ValueError(f"Unsupported method: {method}")


def measure_endpoint(client, endpoint_name, method, path, runs, query_stats):
    # Warmup
    try:
        run_request(client, method, path)
    except Exception:
        pass

    measurements = []
    statuses = []
    redirects = []

    for _ in range(runs):
        reset_queries()
        connection.force_debug_cursor = True

        mem_before_current, mem_before_peak = tracemalloc.get_traced_memory()

        t0 = time.perf_counter()
        response = run_request(client, method, path)
        t1 = time.perf_counter()

        mem_after_current, mem_after_peak = tracemalloc.get_traced_memory()

        queries = list(connection.queries)
        query_count = len(queries)
        query_ms = 0.0

        for q in queries:
            try:
                q_ms = float(q.get("time", 0.0)) * 1000.0
            except Exception:
                q_ms = 0.0
            query_ms += q_ms

            signature = normalize_sql(q.get("sql", ""))
            key = (endpoint_name, signature)
            query_stats[key]["count"] += 1
            query_stats[key]["total_ms"] += q_ms
            query_stats[key]["max_ms"] = max(query_stats[key]["max_ms"], q_ms)

        response_ms = (t1 - t0) * 1000.0
        size_kb = len(getattr(response, "content", b"")) / 1024.0
        mem_peak_kb = max(0.0, (mem_after_peak - mem_before_peak) / 1024.0)
        mem_current_delta_kb = (mem_after_current - mem_before_current) / 1024.0

        measurements.append(
            {
                "response_ms": response_ms,
                "query_count": query_count,
                "query_ms": query_ms,
                "size_kb": size_kb,
                "mem_peak_kb": mem_peak_kb,
                "mem_current_delta_kb": mem_current_delta_kb,
            }
        )
        statuses.append(response.status_code)

        if response.status_code in (301, 302, 307, 308):
            redirects.append(response.headers.get("Location", ""))

    def avg(key):
        return statistics.fmean(m[key] for m in measurements) if measurements else 0.0

    response_values = [m["response_ms"] for m in measurements] or [0.0]

    return {
        "name": endpoint_name,
        "method": method,
        "path": path,
        "runs": runs,
        "status_codes": statuses,
        "redirects": redirects,
        "avg_response_ms": round(avg("response_ms"), 2),
        "p95_response_ms": round(statistics.quantiles(response_values, n=20)[18], 2)
        if len(response_values) >= 2
        else round(response_values[0], 2),
        "avg_query_count": round(avg("query_count"), 2),
        "avg_query_ms": round(avg("query_ms"), 2),
        "avg_size_kb": round(avg("size_kb"), 2),
        "avg_mem_peak_kb": round(avg("mem_peak_kb"), 2),
        "avg_mem_delta_kb": round(avg("mem_current_delta_kb"), 2),
    }


def dataset_counts(center):
    User = get_user_model()
    return {
        "users_total": User.objects.count(),
        "users_center": User.objects.filter(center=center).count(),
        "groups_center": Group.objects.filter(center=center).count(),
        "enrollments_center": Enrollment.objects.filter(center=center).count(),
        "payments_center": Payment.objects.filter(center=center).count(),
        "attendance_center": Attendance.objects.filter(center=center).count(),
        "ledger_total": Ledger.objects.count(),
        "notifications_total": Notification.objects.count(),
        "subscription_requests_center": SubscriptionRequest.objects.filter(center=center).count(),
    }


def main():
    parser = argparse.ArgumentParser(description="Endpoint performance benchmark")
    parser.add_argument("--runs", type=int, default=5, help="Number of measured runs per endpoint")
    parser.add_argument(
        "--output",
        type=str,
        default="scripts/perf/baseline_metrics.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    tracemalloc.start()

    center, tenant_user, superuser, tenant_client, super_client = setup_users_and_clients()
    tenant_endpoints, super_endpoints = build_endpoints(center)

    query_stats = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0})

    endpoint_results = []

    for name, method, path in tenant_endpoints:
        endpoint_results.append(
            measure_endpoint(tenant_client, name, method, path, args.runs, query_stats)
        )

    for name, method, path in super_endpoints:
        endpoint_results.append(
            measure_endpoint(super_client, name, method, path, args.runs, query_stats)
        )

    sorted_by_latency = sorted(endpoint_results, key=lambda x: x["avg_response_ms"], reverse=True)
    sorted_by_queries = sorted(endpoint_results, key=lambda x: x["avg_query_count"], reverse=True)

    heavy_queries = []
    for (endpoint_name, signature), data in query_stats.items():
        heavy_queries.append(
            {
                "endpoint": endpoint_name,
                "signature": signature,
                "count": data["count"],
                "total_ms": round(data["total_ms"], 3),
                "max_ms": round(data["max_ms"], 3),
            }
        )
    heavy_queries.sort(key=lambda x: x["total_ms"], reverse=True)

    payload = {
        "generated_at": datetime.now(dt_timezone.utc).isoformat(),
        "settings_debug": bool(settings.DEBUG),
        "db_vendor": connection.vendor,
        "db_name": str(connection.settings_dict.get("NAME")),
        "center": {
            "id": center.id,
            "name": center.name,
            "slug": center.slug,
        },
        "tenant_user": {
            "id": tenant_user.id,
            "email": tenant_user.email,
            "role": getattr(tenant_user, "role", ""),
            "is_superuser": tenant_user.is_superuser,
        },
        "superuser": {
            "id": superuser.id,
            "email": superuser.email,
        },
        "runs_per_endpoint": args.runs,
        "dataset": dataset_counts(center),
        "endpoints": endpoint_results,
        "top_slowest_endpoints": sorted_by_latency[:10],
        "top_query_heavy_endpoints": sorted_by_queries[:10],
        "top_heavy_queries": heavy_queries[:30],
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "output": args.output,
        "endpoints": len(endpoint_results),
        "slowest": [
            {"name": e["name"], "avg_response_ms": e["avg_response_ms"]}
            for e in sorted_by_latency[:5]
        ],
        "query_heavy": [
            {"name": e["name"], "avg_query_count": e["avg_query_count"]}
            for e in sorted_by_queries[:5]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
