# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import requests
except ImportError:
    print("❌ 缺少 requests 库，无法进行诊断")
    sys.exit(1)

def main():
    base = os.getenv("LOKI_URL", "http://localhost:3100").rstrip("/")
    tenant = os.getenv("LOKI_TENANT_ID")
    username = os.getenv("LOKI_USERNAME")
    password = os.getenv("LOKI_PASSWORD")
    auth = (username, password) if username and password else None

    headers = {"Content-Type": "application/json"}
    if tenant:
        headers["X-Scope-OrgID"] = tenant

    print("== Loki 连接诊断 ==")
    print(f"LOKI_URL: {base}")
    print(f"LOKI_TENANT_ID: {tenant or '-'}")
    print(f"认证: {'basic' if auth else 'none'}")

    endpoints = [
        ("/-/ready", f"{base}/-/ready"),
        ("/loki/api/v1/status/build", f"{base}/loki/api/v1/status/build"),
        ("/loki/api/v1/labels", f"{base}/loki/api/v1/labels"),
    ]

    for name, url in endpoints:
        try:
            r = requests.get(url, headers=headers, auth=auth, timeout=5)
            print(f"{name}: {r.status_code}")
        except Exception as e:
            print(f"{name}: 失败 - {e}")

    payload = {
        "streams": [
            {
                "stream": {"app": "diagnose", "job": "diagnose"},
                "values": [[str(0), json.dumps({"message": "test"}, ensure_ascii=False)]],
            }
        ]
    }

    try:
        r = requests.post(
            f"{base}/loki/api/v1/push", json=payload, headers=headers, auth=auth, timeout=5
        )
        print(f"push: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"push: 失败 - {e}")

if __name__ == "__main__":
    main()

