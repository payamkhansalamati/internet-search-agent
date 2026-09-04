from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Cloud(StrEnum):
    AWS = "aws"
    AZURE = "azure"


class WorkloadKind(StrEnum):
    TRAIN = "train"
    FINE_TUNE = "fine-tune"
    EVALUATE = "evaluate"
    INFERENCE = "inference"


class Distribution(StrEnum):
    SINGLE = "single"
    DDP = "ddp"
    DEEPSPEED = "deepspeed"


class Resources(BaseModel):
    nodes: int = Field(1, ge=1, le=128)
    gpus_per_node: int = Field(1, ge=1, le=8)
    gpu_memory_gib: int = Field(24, ge=16)
    cpu_per_node: int = Field(8, ge=1)
    memory_gib_per_node: int = Field(64, ge=16)


class QualityGate(BaseModel):
    metric: str = Field(min_length=1)
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def exactly_one_bound(self) -> "QualityGate":
        if (self.minimum is None) == (self.maximum is None):
            raise ValueError("quality gate requires exactly one of minimum or maximum")
        return self


class Workload(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")
    kind: WorkloadKind
    cloud: Cloud
    region: str = Field(min_length=2)
    image: str = Field(min_length=1)
    model: str = Field(min_length=1)
    dataset: str | None = None
    distribution: Distribution = Distribution.SINGLE
    resources: Resources
    use_spot: bool = False
    checkpoint_uri: str | None = None
    quality_gates: list[QualityGate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_training_contract(self) -> "Workload":
        if self.kind in {WorkloadKind.TRAIN, WorkloadKind.FINE_TUNE} and not self.dataset:
            raise ValueError("training and fine-tuning workloads require a dataset")
        if self.resources.nodes > 1 and self.distribution == Distribution.SINGLE:
            raise ValueError("multi-node workloads require ddp or deepspeed")
        if self.use_spot and not self.checkpoint_uri and self.kind in {WorkloadKind.TRAIN, WorkloadKind.FINE_TUNE}:
            raise ValueError("spot training requires a durable checkpoint_uri")
        return self
