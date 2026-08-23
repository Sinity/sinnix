# Runtime modes

Use AgentCTL for every registered workspace and unattended agent job. Its common job ID is the only handle for logs, results, waiting, reconciliation, and cancellation.

```bash
agentctl workspace create <project> <lane> --branch feature/<lane>
agentctl agent --project <project> --checkout <checkout-id> \
  --prompt-file <prompt-file> --backend <backend> --model <model> --effort high
agentctl job logs <job-id>
agentctl job wait <job-id>
agentctl job result <job-id>
agentctl job cancel <job-id>
```

For a fixed-scope review fanout, make each prompt own explicit files and give each worker its own AgentCTL workspace and job. Submit a bounded number of jobs deliberately, then report their AgentCTL IDs and results. Do not produce batch manifests, PID files, local retry records, or terminal status tables.

For a visible operator session, use `sinnix-kitty-control` through the `desktop-control-plane` skill to open and inspect the terminal without taking focus. Terminal control never changes AgentCTL lifecycle authority.

`probe_agent_runtime.sh --agent <backend> --probe-model` is appropriate when vendor or quota availability needs direct evidence before dispatch. The native `run_agent_prompt.sh` backend adapter is called only by Sinnixd.
