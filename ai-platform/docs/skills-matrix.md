# Job requirements to project evidence

| Job capability | Project evidence | Planned proof |
|---|---|---|
| GPU/HPC clusters | EKS/AKS placement and provider capabilities | Terraform deployment plus GPU health/runbook |
| Training and fine-tuning | Versioned workload contract and QLoRA example | Reproducible LoRA/QLoRA run with artifacts |
| Distributed training | DDP/DeepSpeed validation and launcher selection | Multi-node scaling benchmark |
| Evaluation and alignment | Per-workload quality gates | Regression, safety, and preference evaluation pipeline |
| Production inference | Parent research-agent integration | vLLM canary with autoscaling and rollback |
| Performance and efficiency | Explicit topology and accelerator choice | Tokens/sec, utilization, latency, and cost dashboard |
| Production operations | Kubernetes-first design and policy boundaries | SLOs, alerts, failure drills, and incident runbooks |
| Multi-cloud infrastructure | AWS/Azure-specific capability plans | Equivalent EKS and AKS reference environments |

The strongest portfolio story is not “used many tools.” It is a measured progression: establish a baseline, expose a bottleneck or quality problem, change one part of the system, and show the resulting reliability, quality, throughput, or cost improvement.
