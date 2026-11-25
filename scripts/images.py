"""Build the local images with source revisions shared by both CI providers."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = {
    "verstak-agent": "e667e7ce1b1beb7bcc795778e302ac5c901bbab5",
    "verifine-slm": "07ceb3203e4040b5a5f990d2b7178899dd2d56c9",
}


def run(*command):
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=ROOT.parent)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    sources = ROOT / ".upstream" if args.fetch else args.sources.resolve()
    if args.fetch:
        sources.mkdir(parents=True, exist_ok=True)
    for name, revision in UPSTREAM.items():
        checkout = sources / name
        if args.fetch:
            if not checkout.exists():
                run("git", "init", str(checkout))
            run("git", "-C", str(checkout), "fetch", "--depth=1",
                f"https://github.com/Galactic717/{name}.git", revision)
            run("git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD")
        run("docker", "build", "-t", f"{name}:local", str(checkout))
    run("docker", "build", "-t", "vllm-ops-fixture:local", str(ROOT / "fixture"))
    run("docker", "build", "-t", "vllm-ops-postgres:local", str(ROOT / "postgres"))


if __name__ == "__main__":
    main()
