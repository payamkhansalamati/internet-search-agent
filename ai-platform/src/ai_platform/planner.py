from dataclasses import asdict, dataclass

from ai_platform.models import Cloud, Distribution, Workload


@dataclass(frozen=True)
class DeploymentPlan:
    workload: str
    cluster: str
    node_pool: str
    accelerator_class: str
    replicas: int
    launcher: str
    preemptible: bool
    required_capabilities: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def plan_workload(workload: Workload) -> DeploymentPlan:
    memory = workload.resources.gpu_memory_gib
    if workload.cloud == Cloud.AWS:
        accelerator = "p5" if memory >= 80 else "g5"
        cluster = f"eks-ai-{workload.region}"
        capabilities = ["eks", "s3", "cloudwatch", "nvidia-device-plugin"]
        if workload.resources.nodes > 1:
            capabilities.extend(["efa", "fsx-for-lustre"])
    else:
        accelerator = "nd-h100-v5" if memory >= 80 else "nc-a100-v4"
        cluster = f"aks-ai-{workload.region}"
        capabilities = ["aks", "blob-storage", "azure-monitor", "nvidia-device-plugin"]
        if workload.resources.nodes > 1:
            capabilities.extend(["infiniband", "azure-managed-lustre"])

    launcher = {
        Distribution.SINGLE: "kubernetes-job",
        Distribution.DDP: "kubeflow-pytorchjob",
        Distribution.DEEPSPEED: "kubeflow-pytorchjob+deepspeed",
    }[workload.distribution]
    return DeploymentPlan(
        workload=workload.name,
        cluster=cluster,
        node_pool=f"gpu-{accelerator}",
        accelerator_class=accelerator,
        replicas=workload.resources.nodes,
        launcher=launcher,
        preemptible=workload.use_spot,
        required_capabilities=tuple(capabilities),
    )
