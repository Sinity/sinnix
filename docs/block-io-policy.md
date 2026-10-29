# Block I/O controller ownership

The desktop workstation initializer enables IOCost on physical block devices. Existing system, desktop, agent and backup `IOWeight` values distribute relative shares at their respective hierarchy levels. Idle shares remain available to other work; weights are not a hard latency guarantee.

IOLatency targets must not overlap this ownership, even when different paths name the same physical device. The kernel controllers use incompatible modes of the same block-cgroup delay state: IOCost uses `blkcg_set_delay`, while IOLatency uses `blkcg_use_delay`. The kernel's helper contract explicitly prohibits mixing these modes. The dedicated rendered exclusion law checks declared system and user slices and services while the all-device IOCost initializer is enabled. This validates the evaluated policy; it is not a runtime guard over custom units created outside that configuration.

`ctrl=auto` chooses and adapts kernel profiles and virtual rates. Matching cost-model coefficients on different SSDs do not prove independent device calibration.

The rendered controller-exclusion law and desktop accounting/weight laws validate the declared policy. They do not establish an interactive tail-latency bound or explain every historical host stall. Kernel reproduction and comparative latency/backup-progress validation use separately authorized isolated synthetic guests. Live activation requires review of the rendered delta and actual controller readback afterward; a removed source property alone does not prove a live target cleared.

Primary contract: [Linux block-cgroup delay helpers](https://raw.githubusercontent.com/gregkh/linux/v6.18.50/block/blk-cgroup.h#L373-L425).
