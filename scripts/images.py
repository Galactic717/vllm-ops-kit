"""Build the local images with source revisions shared by both CI providers."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = {
    "verstak-agent": "f1b598ab894d015c18d608719137d953da8718aa",
    "verifine-slm": "73bbfb9287a26d5514fca248c59464de99bb8018",
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
