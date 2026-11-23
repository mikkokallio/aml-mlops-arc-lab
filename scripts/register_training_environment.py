"""Register an AML training environment from the shared dependency manifest."""

import argparse
import json
from pathlib import Path

from azure.ai.ml import MLClient, load_environment
from azure.ai.ml.entities import Environment
from azure.identity import AzureCliCredential


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument(
        "--environment", type=Path, default=Path("config/training-environment.yml")
    )
    parser.add_argument("--requirements", type=Path, default=Path("requirements.txt"))
    args = parser.parse_args()
    requirements = [
        line.strip()
        for line in args.requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not requirements:
        raise ValueError("The training dependency manifest must not be empty.")
    manifest = load_environment(source=args.environment)
    environment = Environment(
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        image=manifest.image,
        conda_file={
            "name": "campaign-training",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.12.3", "pip", {"pip": requirements}],
        },
    )
    client = MLClient(
        AzureCliCredential(process_timeout=60),
        args.subscription,
        args.resource_group,
        args.workspace,
    )
    registered = client.environments.create_or_update(environment)
    print(
        json.dumps(
            {
                "id": registered.id,
                "name": registered.name,
                "version": registered.version,
                "image": registered.image,
            }
        )
    )


if __name__ == "__main__":
    main()
