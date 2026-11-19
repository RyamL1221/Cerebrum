# Kernel ablations (AIOS docs/ABLATION.md)

Paired by trial index: ablated minus the full kernel, with a 95% t interval. Direction: + the ablation should raise the measure, - lower it, 0 reported.

| switch | condition | measure | full | ablated | difference | n | direction | confirmed |
|---|---|---|---|---|---|---|---|---|
| barrier: off | n6conc | covered late writes per user (primary) | 0.00 | 17.00 | +17.00 [+11.05, +22.95] | 5 | + | True |
| barrier: off | n6conc | stale reads per user | 0.00 | 0.00 | +0.00 [+0.00, +0.00] | 5 | + | False |
| barrier: off | n6conc | timing misses per user | 0.00 | 0.00 | +0.00 [+0.00, +0.00] | 5 | + | False |
| barrier: off | n6conc | memories_missing | 0.60 | 0.60 | +0.00 [+0.00, +0.00] | 5 | 0 | - |
| identity: claim | n6wrong_user | misfiled rows per user (primary) | 0.00 | 5.40 | +5.40 [+2.05, +8.75] | 5 | + | True |
| identity: claim | n6wrong_user | cross-user rows in the blocks | 0.00 | 17.60 | +17.60 [-1.43, +36.63] | 5 | + | False |
| identity: claim | n6wrong_user | memories_missing | 0.60 | 1.40 | +0.80 [+0.24, +1.36] | 5 | + | True |
| identity: claim | n6v2 | profile facts in the block (primary) | 1.00 | 0.03 | -0.97 [-1.06, -0.87] | 5 | - | True |
| identity: claim | n6v2 | memories_missing | 0.60 | 1.40 | +0.80 [+0.24, +1.36] | 5 | + | True |
| visibility: off | n6v3 | privacy probe failed (primary) | 0.00 | 1.00 | +1.00 [+1.00, +1.00] | 5 | + | True |
| visibility: off | n6v3 | private rows from others | 0.00 | 0.80 | +0.80 [+0.24, +1.36] | 5 | + | True |
| supersession: off | n6h0 | stale value in the recency and contradiction blocks (primary) | 0.00 | 2.00 | +2.00 [+2.00, +2.00] | 5 | + | True |
| supersession: off | n6h0 | recency failed | 0.00 | 1.00 | +1.00 [+1.00, +1.00] | 5 | + | True |
| supersession: off | n6h0 | contradiction failed | 0.00 | 0.40 | +0.40 [-0.28, +1.08] | 5 | + | False |
| forget_scope: writer | n6h0 | carriers left per user (primary) | 0.00 | 0.80 | +0.80 [-0.56, +2.16] | 5 | + | False |
| forget_scope: writer | n6h0 | deletion failed, echo users | 0.50 | 1.00 | +0.50 [-5.85, +6.85] | 2 | + | False |
| forget_scope: writer | n6h0 | deletion failed, other users | 0.00 | 0.00 | +0.00 [+0.00, +0.00] | 3 | 0 | - |
| quota: off | n6flood10 | flood rows in the block per probe (primary) | 1.30 | 6.50 | +5.20 [+3.23, +7.17] | 5 | + | True |
| quota: off | n6flood10 | profile facts in the block (primary) | 1.00 | 1.00 | +0.00 [+0.00, +0.00] | 5 | - | False |
| quota: off | n6flood10 | memories_missing | 0.80 | 1.60 | +0.80 [-0.56, +2.16] | 5 | + | False |
| quota: off | n6flood10 | flood writes accepted | 1.80 | 18.00 | +16.20 [+9.67, +22.73] | 5 | + | True |
| quota: off | n6flood50 | flood rows in the block per probe (primary) | 1.30 | 9.83 | +8.53 [+5.92, +11.15] | 5 | + | True |
| quota: off | n6flood50 | profile facts in the block (primary) | 1.00 | 0.63 | -0.37 [-0.99, +0.26] | 5 | - | False |
| quota: off | n6flood50 | memories_missing | 0.80 | 1.80 | +1.00 [-0.24, +2.24] | 5 | + | False |
| quota: off | n6flood50 | flood writes accepted | 1.80 | 90.00 | +88.20 [+59.57, +116.83] | 5 | + | True |
| block_format: legacy | n6h0 | block tokens per probe (primary) | 259.37 | 262.80 | +3.43 [-21.34, +28.21] | 5 | 0 | - |
| block_order: similarity | n6h0 | block tokens per probe (primary) | 259.37 | 259.37 | +0.00 [+0.00, +0.00] | 5 | 0 | - |
| budget: off | n6h0 | block tokens per probe (primary) | 259.37 | 332.20 | +72.83 [+19.20, +126.46] | 5 | + | True |
| budget: off | n6h0 | probes the budget bound | 4.80 | 0.00 | -4.80 [-8.13, -1.47] | 5 | - | True |
| threshold: 0.3 | n6h0 | candidates after the threshold per probe (primary) | 13.60 | 13.33 | -0.27 [-0.38, -0.15] | 5 | - | True |
| threshold: 0.3 | n6h0 | block tokens per probe | 259.37 | 258.90 | -0.47 [-1.76, +0.83] | 5 | - | False |
| consumer_config: honor | n6v4 | candidates after the threshold per probe (primary) | 13.60 | 1.23 | -12.37 [-14.65, -10.08] | 5 | - | True |
| consumer_config: honor | n6v4 | rows after the cap per probe | 13.60 | 1.23 | -12.37 [-14.65, -10.08] | 5 | - | True |
| consumer_config: honor | n6v4 | block tokens per probe | 259.37 | 27.40 | -231.97 [-245.66, -218.27] | 5 | - | True |
| consumer_config: honor | n6v4 | profile facts in the block | 1.00 | 0.00 | -1.00 [-1.00, -1.00] | 5 | - | True |
| consumer_config: honor | n6v4 | memories_missing | 0.60 | 4.20 | +3.60 [+2.92, +4.28] | 5 | + | True |

## Outcomes against the full kernel

| switch | condition | deletion | privacy | recall | recency | contradiction |
|---|---|---|---|---|---|---|
| barrier | n6conc | -1 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| block_format | n6h0 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| block_order | n6h0 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| budget | n6h0 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| consumer_config | n6v4 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| forget_scope | n6h0 | -1 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| identity | n6v2 | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -2 +0 (p 0.50) | -1 +0 (p 1.00) | -1 +0 (p 1.00) |
| identity | n6wrong_user | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -1 +0 (p 1.00) |
| quota | n6flood10 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| quota | n6flood50 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| supersession | n6h0 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -5 +0 (p 0.06) | -2 +0 (p 0.50) |
| threshold | n6h0 | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| visibility | n6v3 | -0 +1 (p 1.00) | -5 +0 (p 0.06) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |

## Functional check rules

| switch | rule | held | seen |
|---|---|---|---|
| barrier | a covered late write; the full kernel none | True | 85 ablated, 0 full |
| identity | wrong_user: misfiled rows and a cross-user row; the full kernel neither | True | 27 misfiled and 88 cross-user rows ablated, 0 full |
| identity | V2: profile facts in the block 0 for every user | False | [0.0, 0.0, 0.16666666666666666, 0.0, 0.0] |
| visibility | a privacy probe fails with its value in the block; the full kernel's never | True | 5 of 5 ablated, 0 full |
| supersession | an earlier statement in every recency and contradiction block | True | 10 of 10 blocks |
| forget_scope | echo users keep a carrier and fail deletion; the others pass | True | echo users [0, 4]: carriers [2, 2], deletion failed [1, 1]; others failed [0, 0, 0] |
| quota | n6flood10: no quota rejection, more flood rows in the blocks than the full kernel's | True | 0 rejected; 32.5 vs 6.5 flood rows per probe, summed over users |
| quota | n6flood50: no quota rejection, more flood rows in the blocks than the full kernel's | True | 0 rejected; 49.2 vs 6.5 flood rows per probe, summed over users |
| block_format | the blocks differ from the full kernel's | True | 30 of 30 probes differ |
| block_order | the blocks differ from the full kernel's | True | 30 of 30 probes differ |
| budget | the budget binds in no probe | True | 0 probes bound |
| threshold | after_threshold never above the full kernel's, probe by probe | True | probes above: [] |
| consumer_config | the kernel's V4 block equals the replicated V4 block in every probe | True | 30 of 30 probes equal |
| consumer_config | on the full kernel the V4 consumer's block equals the H = 0 block | True | 30 of 30 probes equal |

## Cells

Each trial's recorded ablation is its cell's.

| switch | condition | method | trials | succeeded | wrong record | held |
|---|---|---|---|---|---|---|
| full | n6conc | kernel_shared | 5 | 5 | - | True |
| full | n6flood10 | kernel_shared | 5 | 5 | - | True |
| full | n6flood50 | kernel_shared | 5 | 5 | - | True |
| full | n6h0 | kernel_shared | 5 | 5 | - | True |
| full | n6v2 | kernel_shared | 5 | 5 | - | True |
| full | n6v3 | kernel_shared | 5 | 5 | - | True |
| full | n6v4 | kernel_shared | 5 | 5 | - | True |
| full | n6wrong_user | kernel_shared | 5 | 5 | - | True |
| barrier | n6conc | kernel_shared | 5 | 5 | - | True |
| block_format | n6h0 | kernel_shared | 5 | 5 | - | True |
| block_order | n6h0 | kernel_shared | 5 | 5 | - | True |
| budget | n6h0 | kernel_shared | 5 | 5 | - | True |
| consumer_config | n6v4 | kernel_shared | 5 | 5 | - | True |
| forget_scope | n6h0 | kernel_shared | 5 | 5 | - | True |
| identity | n6v2 | kernel_shared | 5 | 5 | - | True |
| identity | n6wrong_user | kernel_shared | 5 | 5 | - | True |
| quota | n6flood10 | kernel_shared | 5 | 5 | - | True |
| quota | n6flood50 | kernel_shared | 5 | 5 | - | True |
| replicated | n6v4 | replicated_inhouse | 5 | 5 | - | True |
| supersession | n6h0 | kernel_shared | 5 | 5 | - | True |
| threshold | n6h0 | kernel_shared | 5 | 5 | - | True |
| visibility | n6v3 | kernel_shared | 5 | 5 | - | True |
