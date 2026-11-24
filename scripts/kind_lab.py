"""Create and verify the isolated kind lab on Linux or Docker Desktop."""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from runtime_secret import ensure

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = "vllm-ops-kit"
CONTEXT = "kind-" + CLUSTER
NAMESPACE = "ai-stack"
KUBECONFIG = ROOT / ".kubeconfig-kind"
BASE = "http://127.0.0.1:18080"
CALICO = "https://raw.githubusercontent.com/projectcalico/calico/v3.30.3/manifests/calico.yaml"
METRICS_SERVER = "https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.8.0/components.yaml"


def run(*args, data=None, capture=False, env=None):
    return subprocess.run(args, cwd=ROOT, check=True, input=data, text=True, env=env,
                          stdout=subprocess.PIPE if capture else None).stdout


def kubectl(*args, **kwargs):
    return run("kubectl", "--kubeconfig", str(KUBECONFIG), "--context", CONTEXT, *args, **kwargs)


def helm(*args):
    return run("helm", "--kubeconfig", str(KUBECONFIG), "--kube-context", CONTEXT, *args)


def apply(resource):
    kubectl("apply", "-f", "-", data=json.dumps(resource))


def ready_deployment(namespace, name):
    kubectl("-n", namespace, "rollout", "status", "deployment/" + name, "--timeout=4m")


def install(skip_import):
    if CLUSTER not in run("kind", "get", "clusters", capture=True).splitlines():
        run("kind", "create", "cluster", "--name", CLUSTER, "--config", "cluster/kind.yaml",
            "--kubeconfig", str(KUBECONFIG))
    elif not KUBECONFIG.exists():
        run("kind", "export", "kubeconfig", "--name", CLUSTER, "--kubeconfig", str(KUBECONFIG))

    kubectl("apply", "-f", CALICO)
    kubectl("wait", "--for=condition=Ready", "nodes", "--all", "--timeout=4m")
    ready_deployment("kube-system", "coredns")

    # The kubelet certificate exception is local to this kind cluster.
    kubectl("apply", "-f", METRICS_SERVER)
    metrics = json.loads(kubectl("-n", "kube-system", "get", "deployment",
                                "metrics-server", "-o", "json", capture=True))
    path = "/spec/template/spec/containers/0/args"
    flag = "--kubelet-insecure-tls"
    if flag not in metrics["spec"]["template"]["spec"]["containers"][0]["args"]:
        kubectl("-n", "kube-system", "patch", "deployment", "metrics-server", "--type=json",
                "-p", json.dumps([{"op": "add", "path": path + "/-", "value": flag}]))
    ready_deployment("kube-system", "metrics-server")

    helm("upgrade", "--install", "traefik", "traefik", "--repo", "https://traefik.github.io/charts",
         "--version", "37.4.0", "-n", "ingress-system", "--create-namespace", "-f",
         "cluster/traefik.yaml", "--wait", "--timeout", "5m")
    helm("upgrade", "--install", "kps", "kube-prometheus-stack", "--repo",
         "https://prometheus-community.github.io/helm-charts", "--version", "79.8.2",
         "-n", "monitoring", "--create-namespace", "-f", "cluster/observability.yaml",
         "--wait", "--timeout", "7m")
    helm("upgrade", "--install", "ops-slo", "monitoring", "-n", "monitoring", "--wait")
    apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {
        "name": NAMESPACE, "labels": {"pod-security.kubernetes.io/enforce": "restricted"},
    }})
    secret = ensure(NAMESPACE, "ai-stack-runtime", kubectl)
    if not skip_import:
        # A single-platform archive avoids missing index manifests on Docker Desktop.
        with tempfile.TemporaryDirectory(prefix="ops-kind-") as directory:
            archive = str(Path(directory) / "images.tar")
            run("docker", "image", "save", "--platform", "linux/amd64", "-o", archive,
                "vllm-ops-fixture:local", "vllm-ops-postgres:local",
                "verstak-agent:local", "verifine-slm:local")
            run("kind", "load", "image-archive", "--name", CLUSTER, archive)

    started = time.monotonic()
    helm("upgrade", "--install", "ops", "charts/ai-stack", "-n", NAMESPACE, "-f",
         "charts/ai-stack/values-ci.yaml", "--wait", "--timeout", "5m")
    deploy_seconds = round(time.monotonic() - started, 2)
    helm("test", "ops", "-n", NAMESPACE, "--timeout", "90s")
    return secret, deploy_seconds


def request(url, body=None, headers=None, raw=False):
    args = dict(headers=headers or {})
    if body is not None:
        if isinstance(body, bytes):
            args["headers"]["Content-Type"] = "application/x-www-form-urlencoded"
            args["data"] = body
        else:
            args["headers"]["Content-Type"] = "application/json"
            args["data"] = json.dumps(body).encode()
    with urlopen(Request(url, **args), timeout=10) as response:
        return response.read() if raw else json.load(response)


def bearer(token):
    return {"Authorization": "Bearer " + token}


def eventually(check, title, timeout=90):
    stop = time.monotonic() + timeout
    last = None
    while time.monotonic() < stop:
        try:
            last = check()
            if last:
                return last
        except (URLError, ConnectionError, subprocess.CalledProcessError) as exc:
            last = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {title}. Last result: {last!r}")


def verify_ingress(secret):
    eventually(lambda: request(BASE + "/healthz").get("status") == "ok", "Ingress readiness")
    for url, status in [("/v1/models", 401), ("/metrics", 404), ("/ops/pool-metrics", 404)]:
        try:
            request(BASE + url)
        except HTTPError as exc:
            if exc.code == status:
                continue
            raise
        raise RuntimeError(f"Ingress {url} unexpectedly allowed access")

    gateway_headers = bearer(secret["VERIFINE_GATEWAY_KEY"])
    models = request(BASE + "/v1/models", headers=gateway_headers)
    assert models["data"][0]["id"] == "ops-fixture"
    chat = {"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 8}
    answer = request(BASE + "/v1/chat/completions", chat, gateway_headers)
    assert answer["choices"][0]["message"]["content"] == "ops fixture"
    chat["stream"] = True
    sse = request(BASE + "/v1/chat/completions", chat, gateway_headers, raw=True)
    assert b"data: [DONE]" in sse
    extracted = request(BASE + "/v1/extract", {
        "task": "invoice", "document": "Fixture invoice OPS-1, total USD 5.",
    }, gateway_headers)
    assert extracted["result"]["invoice_id"] == "OPS-1", extracted

    client = json.loads(secret["VERSTAK_CLIENTS_JSON"])["ops-smoke"]
    credentials = urlencode({"grant_type": "client_credentials", "client_id": "ops-smoke",
                             "client_secret": client["secret"]}).encode()
    token = request(BASE + "/oauth/token", credentials)["access_token"]
    run_headers = bearer(token) | {"Idempotency-Key": str(uuid4())}
    receipt = request(BASE + "/workflows/triage/runs", {"text": "Please review the office hours."},
                      run_headers)
    url = BASE + "/runs/" + receipt["id"]

    def completed():
        status = request(url, headers=bearer(token))["status"]
        if status in {"succeeded", "waiting_approval"}:
            return status
        if status in {"failed", "rejected"}:
            raise RuntimeError(f"Celery workflow ended with {status}")
        return None

    return token, eventually(completed, "Celery workflow", 75)


def verify_policy():
    pods = json.loads(kubectl("-n", NAMESPACE, "get", "pods", "-l",
                             "app.kubernetes.io/instance=ops", "-o", "json", capture=True))
    assert pods["items"]
    for pod in pods["items"]:
        spec = pod["spec"]
        assert spec["automountServiceAccountToken"] is False
        assert spec["securityContext"]["runAsNonRoot"] is True
        for c in spec["containers"] + spec.get("initContainers", []):
            assert c["securityContext"]["readOnlyRootFilesystem"] is True, c["name"]
            assert c["securityContext"]["allowPrivilegeEscalation"] is False, c["name"]
            assert c["resources"]["limits"]["memory"] and c["resources"]["limits"]["cpu"], c["name"]

    # An unrelated pod must resolve the Service yet be unable to connect to it.
    name = "ops-policy-probe"
    script = """import socket
host = "ops-api"
socket.getaddrinfo(host, 8000)
try:
    socket.create_connection((host, 8000), timeout=3).close()
except TimeoutError:
    print("NetworkPolicy denied access")
else:
    raise SystemExit("Unrelated pod reached the API")
"""
    kubectl("-n", NAMESPACE, "delete", "pod", name, "--ignore-not-found")
    apply({"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": NAMESPACE},
           "spec": {"restartPolicy": "Never", "automountServiceAccountToken": False,
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 1000,
                                        "seccompProfile": {"type": "RuntimeDefault"}},
                    "containers": [{"name": "probe", "image": "verifine-slm:local",
                                    "imagePullPolicy": "IfNotPresent",
                                    "securityContext": {"readOnlyRootFilesystem": True,
                                                        "allowPrivilegeEscalation": False,
                                                        "capabilities": {"drop": ["ALL"]}},
                                    "resources": {"limits": {"cpu": "100m", "memory": "64Mi"}},
                                    "command": ["python", "-c", script]}]}})
    try:
        kubectl("-n", NAMESPACE, "wait", "--for=jsonpath={.status.phase}=Succeeded",
                "pod/" + name, "--timeout=45s")
        kubectl("-n", NAMESPACE, "logs", name)
    finally:
        kubectl("-n", NAMESPACE, "delete", "pod", name, "--ignore-not-found")


@contextmanager
def forward(service, port):
    command = ["kubectl", "--kubeconfig", str(KUBECONFIG), "-n", "monitoring", "port-forward",
               "svc/" + service, f":{port}", "--address", "127.0.0.1", "--pod-running-timeout=60s"]
    with subprocess.Popen(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as process:
        try:
            line = process.stdout.readline()
            match = re.search(r"127\.0\.0\.1:(\d+)", line)
            if not match:
                raise RuntimeError(f"Failed to start port-forward: {line}")
            yield "http://127.0.0.1:" + match[1]
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


def verify_monitoring():
    with forward("kps-kube-prometheus-stack-prometheus", 9090) as url:
        metrics = (
            "verifine_requests_total", "ops_fixture_requests_total", "verstak_http_requests_total",
            "verstak_db_pool_size", "ops_postgres_up == 1", "ops_redis_up == 1",
        )
        for metric in metrics:
            query = urlencode({"query": metric})
            eventually(lambda: request(url + "/api/v1/query?" + query)["data"]["result"], metric)
        rules = request(url + "/api/v1/rules")["data"]["groups"]
        names = {rule["name"] for group in rules for rule in group["rules"]}
        expected = {"HighTTFT", "KVCacheSaturation", "High5xxBurnRate", "CeleryBacklog",
                    "PostgresPoolExhaustion", "DependencyUnavailable"}
        assert expected <= names, names

    with forward("kps-kube-prometheus-stack-alertmanager", 9093) as url:
        eventually(lambda: request(url + "/api/v2/status")["versionInfo"]["version"], "Alertmanager")
    with forward("kps-grafana", 80) as url:
        eventually(lambda: request(url + "/api/health").get("database") == "ok", "Grafana")
        config = json.loads(kubectl("-n", "monitoring", "get", "secret", "kps-grafana",
                                   "-o", "json", capture=True))["data"]
        user = base64.b64decode(config["admin-user"])
        password = base64.b64decode(config["admin-password"])
        authorization = "Basic " + base64.b64encode(user + b":" + password).decode()
        for uid in ("ops-inference", "ops-dependencies"):
            eventually(lambda: request(url + "/api/dashboards/uid/" + uid,
                                       headers={"Authorization": authorization})["dashboard"]["uid"],
                       f"Grafana dashboard {uid}")


def hpa_snapshot():
    hpa = json.loads(kubectl("-n", NAMESPACE, "get", "hpa", "ops-api", "-o", "json", capture=True))
    status = hpa.get("status", {})
    metric = next((m["resource"]["current"] for m in status.get("currentMetrics", [])
                   if m.get("resource", {}).get("name") == "cpu"), {})
    if "averageUtilization" not in metric:
        return None
    return {"current": status["currentReplicas"], "desired": status["desiredReplicas"],
            "cpu_percent_of_request": metric["averageUtilization"]}


def loadtest(secret, token, output, profiles, base_rate):
    results = {}
    for profile in profiles:
        env = os.environ | {"PROFILE": profile, "BASE_URL": BASE,
                            "BASE_RATE": str(base_rate), "VERSTAK_TOKEN": token,
                            "GATEWAY_KEY": secret["VERIFINE_GATEWAY_KEY"]}
        summary = output / f"{profile}.json"
        with subprocess.Popen(["k6", "run", "--summary-export", str(summary),
                               "loadtest/k6_smoke_and_spike.js"], cwd=ROOT, env=env) as process:
            samples = []
            while process.poll() is None:
                sample = hpa_snapshot()
                if sample:
                    samples.append(sample)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise RuntimeError(f"k6 {profile} exited with {process.returncode}")
        results[profile] = samples
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--skip-import", action="store_true", help="Use images already in kind")
    parser.add_argument("--profiles", nargs="+", choices=["smoke", "spike", "soak"],
                        default=["smoke", "spike"])
    parser.add_argument("--base-rate", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "loadtest/results/latest")
    args = parser.parse_args()
    if args.base_rate < 1:
        parser.error("--base-rate must be positive")

    if args.verify_only:
        secret, deploy_seconds = ensure(NAMESPACE, "ai-stack-runtime", kubectl), None
        helm("test", "ops", "-n", NAMESPACE, "--timeout", "90s")
    else:
        secret, deploy_seconds = install(args.skip_import)
    token, workflow = verify_ingress(secret)
    verify_policy()
    verify_monitoring()
    eventually(hpa_snapshot, "HPA CPU metrics")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    hpa = loadtest(secret, token, output, args.profiles, args.base_rate)
    evidence = {
        "time_utc": datetime.now(timezone.utc).isoformat(), "backend": "CPU fixture",
        "kubernetes": "kind v1.34.0", "helm_wait_seconds": deploy_seconds, "celery_status": workflow,
        "ingress": True, "stream": True, "structured_extraction": True,
        "network_policy": True, "restricted_pods": True,
        "prometheus": True, "grafana": True, "alertmanager": True, "hpa_samples": hpa,
    }
    (output / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Live verification passed. Evidence is in {output}.")


if __name__ == "__main__":
    main()
