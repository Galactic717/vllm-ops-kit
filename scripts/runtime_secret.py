"""Create a runtime Secret on stdin or recover its values for a repeatable lab run."""
import argparse
import base64
import json
import secrets
import subprocess


def create_values():
    return {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "REDIS_PASSWORD": secrets.token_hex(24),
        "VERSTAK_JWT_SECRET": secrets.token_hex(32),
        "VERSTAK_METRICS_TOKEN": secrets.token_hex(32),
        "VERIFINE_GATEWAY_KEY": secrets.token_hex(32),
        "VERSTAK_CLIENTS_JSON": json.dumps({"ops-smoke": {
            "secret": secrets.token_hex(24), "tenant": "ops-smoke",
            "scopes": ["runs:read", "runs:write", "approvals:write"],
        }}),
    }


def ensure(namespace, name, kubectl):
    exists = kubectl("-n", namespace, "get", "secret", name, "--ignore-not-found", "-o", "json",
                     capture=True)
    if exists:
        return {
            key: base64.b64decode(value).decode()
            for key, value in json.loads(exists)["data"].items()
        }
    resource = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {"name": name, "namespace": namespace}, "stringData": create_values(),
    }
    kubectl("-n", namespace, "create", "-f", "-", data=json.dumps(resource))
    return resource["stringData"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="ai-stack")
    parser.add_argument("--name", default="ai-stack-runtime")
    args = parser.parse_args()

    def kubectl(*command, data=None, capture=False):
        return subprocess.run(
            ["kubectl", "--context", args.context, *command], check=True, text=True, input=data,
            stdout=subprocess.PIPE if capture else None,
        ).stdout

    ensure(args.namespace, args.name, kubectl)


if __name__ == "__main__":
    main()
