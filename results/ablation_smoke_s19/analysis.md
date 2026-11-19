# Kernel ablations (AIOS docs/ABLATION.md)

Paired by trial index: ablated minus the full kernel, with a 95% t interval. Direction: + the ablation should raise the measure, - lower it, 0 reported.

| switch | condition | measure | full | ablated | difference | n | direction | confirmed |
|---|---|---|---|---|---|---|---|---|
| barrier: off | n6conc | covered late writes per user (primary) | 0.00 | 18.10 | +18.10 [+16.37, +19.83] | 30 | + | True |
| barrier: off | n6conc | stale reads per user | 0.00 | 0.23 | +0.23 [-0.00, +0.47] | 30 | + | False |
| barrier: off | n6conc | timing misses per user | 0.00 | 0.10 | +0.10 [-0.01, +0.21] | 30 | + | False |
| barrier: off | n6conc | memories_missing | 0.87 | 0.77 | -0.10 [-0.25, +0.05] | 30 | 0 | - |
| identity: claim | n6wrong_user | misfiled rows per user (primary) | 0.00 | 4.03 | +4.03 [+3.22, +4.85] | 30 | + | True |
| identity: claim | n6wrong_user | cross-user rows in the blocks | 0.00 | 12.23 | +12.23 [+8.43, +16.04] | 30 | + | True |
| identity: claim | n6wrong_user | memories_missing | 0.87 | 1.53 | +0.67 [+0.49, +0.85] | 30 | + | True |
| forget_scope: writer | n6h0 | carriers left per user (primary) | 0.00 | 0.67 | +0.67 [+0.31, +1.02] | 30 | + | True |
| forget_scope: writer | n6h0 | deletion failed, echo users | 0.10 | 1.00 | +0.90 [+0.67, +1.13] | 10 | + | True |
| forget_scope: writer | n6h0 | deletion failed, other users | 0.00 | 0.00 | +0.00 [+0.00, +0.00] | 20 | 0 | - |
| quota: off | n6flood10 | flood rows in the block per probe (primary) | 1.71 | 6.43 | +4.72 [+4.10, +5.34] | 30 | + | True |
| quota: off | n6flood10 | profile facts in the block (primary) | 1.00 | 0.77 | -0.23 [-0.38, -0.07] | 30 | - | True |
| quota: off | n6flood10 | memories_missing | 0.83 | 1.47 | +0.63 [+0.32, +0.95] | 30 | + | True |
| quota: off | n6flood10 | flood writes accepted | 3.13 | 17.67 | +14.53 [+12.88, +16.19] | 30 | + | True |
| quota: off | n6flood50 | flood rows in the block per probe (primary) | 1.82 | 10.03 | +8.21 [+7.50, +8.92] | 30 | + | True |
| quota: off | n6flood50 | profile facts in the block (primary) | 1.00 | 0.47 | -0.53 [-0.72, -0.34] | 30 | - | True |
| quota: off | n6flood50 | memories_missing | 0.83 | 1.90 | +1.07 [+0.68, +1.46] | 30 | + | True |
| quota: off | n6flood50 | flood writes accepted | 3.27 | 88.33 | +85.07 [+77.09, +93.04] | 30 | + | True |

## Outcomes against the full kernel

| switch | condition | deletion | privacy | recall | recency | contradiction |
|---|---|---|---|---|---|---|
| barrier | n6conc | -2 +0 (p 0.50) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -3 +0 (p 0.25) | -3 +0 (p 0.25) |
| forget_scope | n6h0 | -9 +0 (p 0.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| identity | n6wrong_user | -1 +1 (p 1.00) | -1 +0 (p 1.00) | -5 +0 (p 0.06) | -6 +0 (p 0.03) | -6 +0 (p 0.03) |
| quota | n6flood10 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |
| quota | n6flood50 | -0 +1 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) | -0 +0 (p 1.00) |

## Functional check rules

| switch | rule | held | seen |
|---|---|---|---|
| barrier | a covered late write; the full kernel none | True | 543 ablated, 0 full |
| identity | wrong_user: misfiled rows and a cross-user row; the full kernel neither | True | 121 misfiled and 367 cross-user rows ablated, 0 full |
| forget_scope | echo users keep a carrier and fail deletion; the others pass | True | echo users [0, 4, 8, 9, 13, 17, 18, 22, 26, 27]: carriers [2, 2, 2, 2, 2, 2, 2, 2, 2, 2], deletion failed [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]; others failed [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| quota | n6flood10: no quota rejection, more flood rows in the blocks than the full kernel's | True | 0 rejected; 193.0 vs 51.3 flood rows per probe, summed over users |
| quota | n6flood50: no quota rejection, more flood rows in the blocks than the full kernel's | True | 0 rejected; 300.8 vs 54.5 flood rows per probe, summed over users |

## Cells

Each trial's recorded ablation is its cell's.

| switch | condition | method | trials | succeeded | wrong record | held |
|---|---|---|---|---|---|---|
| full | n6conc | kernel_shared | 30 | 30 | - | True |
| full | n6flood10 | kernel_shared | 30 | 30 | - | True |
| full | n6flood50 | kernel_shared | 30 | 30 | - | True |
| full | n6h0 | kernel_shared | 30 | 30 | - | True |
| full | n6wrong_user | kernel_shared | 30 | 30 | - | True |
| barrier | n6conc | kernel_shared | 30 | 30 | - | True |
| forget_scope | n6h0 | kernel_shared | 30 | 30 | - | True |
| identity | n6wrong_user | kernel_shared | 30 | 30 | - | True |
| quota | n6flood10 | kernel_shared | 30 | 30 | - | True |
| quota | n6flood50 | kernel_shared | 30 | 30 | - | True |
