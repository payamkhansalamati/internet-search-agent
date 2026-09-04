import pytest
from pydantic import ValidationError

from ai_platform.models import Workload
from ai_platform.planner import plan_workload


def workload(**overrides: object) -> Workload:
    data: dict[str, object] = {
        "name": "distributed-tune",
        "kind": "fine-tune",
        "cloud": "aws",
        "region": "eu-central-1",
        "image": "training:sha-123",
        "model": "open-weight/model",
        "dataset": "s3://bucket/dataset/v1",
        "distribution": "deepspeed",
        "resources": {"nodes": 2, "gpus_per_node": 8, "gpu_memory_gib": 80},
        "use_spot": True,
        "checkpoint_uri": "s3://bucket/checkpoints/run-1",
    }
    data.update(overrides)
    return Workload.model_validate(data)


def test_plans_distributed_aws_workload() -> None:
    plan = plan_workload(workload())
    assert plan.cluster == "eks-ai-eu-central-1"
    assert plan.accelerator_class == "p5"
    assert plan.launcher.endswith("+deepspeed")
    assert "efa" in plan.required_capabilities


def test_plans_distributed_azure_workload() -> None:
    plan = plan_workload(workload(cloud="azure", region="westeurope", use_spot=False))
    assert plan.cluster == "aks-ai-westeurope"
    assert plan.accelerator_class == "nd-h100-v5"
    assert "infiniband" in plan.required_capabilities


def test_rejects_unsafe_spot_training() -> None:
    with pytest.raises(ValidationError, match="checkpoint_uri"):
        workload(checkpoint_uri=None)


def test_rejects_single_process_multi_node_job() -> None:
    with pytest.raises(ValidationError, match="multi-node"):
        workload(distribution="single")
