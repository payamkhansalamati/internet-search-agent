# Architecture decisions

## Separate control plane from workload execution

The control plane validates intent, applies policy, selects infrastructure capabilities, and records lineage. Training and serving run as Kubernetes workloads. This keeps cloud credentials out of model code and makes the same workload contract portable between EKS and AKS.

## Portability has boundaries

The API is provider-neutral, but performance features are intentionally provider-specific. Distributed AWS jobs can request EFA and FSx for Lustre; Azure jobs can request InfiniBand and Azure Managed Lustre. Pretending these are identical would hide the tuning work the project is intended to demonstrate.

## Model lifecycle

Every run should capture the immutable image digest, base-model revision, dataset version, code revision, hyperparameters, topology, metrics, artifacts, and cost. A candidate is promoted only after its declared quality gates pass. Production deployment uses a canary and retains the previous model for rollback.

## Security and operations

- Workload identity instead of static cloud keys
- Private clusters/endpoints and restricted egress for training data
- Signed images, admission policy, secret-manager CSI integration, and encrypted storage
- Queue-based scheduling with quotas and priorities rather than direct pod creation
- Metrics for GPU utilization, memory, interconnect throughput, tokens/second, queue time, failures, latency, and cost
- Checkpoint-aware retries for preemptible jobs and disruption budgets for serving

## Relationship to the parent agent

The sustainability agent remains an application. Its retrieval and ingestion tests become part of the evaluation suite, while its LLM endpoint becomes configurable so it can consume a model served by this platform. This separation makes the platform reusable for other AI applications.
