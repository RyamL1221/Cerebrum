# Direction agreement

## pilot_v1_hetero

k: gpt-5.4 1, claude-sonnet-5.5 1.

| difference | gpt-5.4 mean [95% CI] | claude-sonnet-5.5 mean [95% CI] |
|---|---|---|
| gpt4o inhouse H0 kernel-native integration | -0.10 [-0.30, 0.10] | -0.07 [-0.23, 0.10] |
| gpt4o inhouse H0 kernel-native profile | 0.00 [-0.14, 0.14] | 0.00 [-0.28, 0.28] |
| gpt4o inhouse H0 kernel-native task | 0.00 [0.00, 0.00] | -0.03 [-0.10, 0.03] |
| gpt4o inhouse H0 kernel-replicated integration | -0.07 [-0.23, 0.10] | -0.13 [-0.30, 0.03] |
| gpt4o inhouse H0 kernel-replicated profile | -0.10 [-0.28, 0.08] | -0.03 [-0.24, 0.17] |
| gpt4o inhouse H0 kernel-replicated task | 0.00 [0.00, 0.00] | -0.03 [-0.10, 0.03] |
| gpt4o inhouse H1 kernel-native integration | 1.00 [0.34, 1.66] | 0.80 [0.27, 1.33] |
| gpt4o inhouse H1 kernel-native profile | 1.07 [0.42, 1.72] | 0.70 [0.16, 1.24] |
| gpt4o inhouse H1 kernel-native task | 1.07 [0.39, 1.74] | 1.07 [0.42, 1.72] |
| gpt4o inhouse H1 kernel-replicated integration | 1.13 [0.50, 1.77] | 0.70 [0.15, 1.25] |
| gpt4o inhouse H1 kernel-replicated profile | 1.10 [0.48, 1.72] | 0.73 [0.25, 1.21] |
| gpt4o inhouse H1 kernel-replicated task | 1.07 [0.39, 1.74] | 1.03 [0.38, 1.69] |
| gpt4o inhouse H2 kernel-native integration | 1.00 [0.20, 1.80] | 0.83 [0.20, 1.47] |
| gpt4o inhouse H2 kernel-native profile | 0.97 [0.13, 1.81] | 0.70 [0.09, 1.31] |
| gpt4o inhouse H2 kernel-native task | 1.07 [0.29, 1.84] | 1.00 [0.25, 1.75] |
| gpt4o inhouse H2 kernel-replicated integration | 1.17 [0.54, 1.80] | 1.07 [0.53, 1.60] |
| gpt4o inhouse H2 kernel-replicated profile | 1.17 [0.52, 1.82] | 0.93 [0.46, 1.40] |
| gpt4o inhouse H2 kernel-replicated task | 1.20 [0.50, 1.90] | 1.13 [0.47, 1.80] |
| gpt4o inhouse H2-H0 kernel-native integration | 1.10 [0.25, 1.95] | 0.90 [0.28, 1.52] |
| gpt4o inhouse H2-H0 kernel-native profile | 0.97 [0.08, 1.85] | 0.70 [0.16, 1.24] |
| gpt4o inhouse H2-H0 kernel-native task | 1.07 [0.29, 1.84] | 1.03 [0.27, 1.80] |
| gpt4o inhouse H2-H0 kernel-replicated integration | 1.23 [0.55, 1.92] | 1.20 [0.65, 1.75] |
| gpt4o inhouse H2-H0 kernel-replicated profile | 1.27 [0.59, 1.95] | 0.97 [0.46, 1.47] |
| gpt4o inhouse H2-H0 kernel-replicated task | 1.20 [0.50, 1.90] | 1.17 [0.49, 1.85] |
| gpt4o mem0 H0 kernel-native integration | 0.17 [-0.05, 0.39] | 0.07 [-0.07, 0.20] |
| gpt4o mem0 H0 kernel-native profile | 0.20 [-0.05, 0.45] | 0.23 [0.02, 0.45] |
| gpt4o mem0 H0 kernel-native task | 0.00 [0.00, 0.00] | 0.03 [-0.03, 0.10] |
| gpt4o mem0 H0 kernel-replicated integration | 0.20 [-0.01, 0.41] | 0.03 [-0.12, 0.19] |
| gpt4o mem0 H0 kernel-replicated profile | 0.17 [-0.05, 0.39] | 0.23 [-0.02, 0.49] |
| gpt4o mem0 H0 kernel-replicated task | 0.00 [0.00, 0.00] | 0.03 [-0.03, 0.10] |
| gpt4o mem0 H1 kernel-native integration | 0.83 [0.24, 1.43] | 0.60 [0.18, 1.02] |
| gpt4o mem0 H1 kernel-native profile | 0.80 [0.23, 1.37] | 0.53 [0.12, 0.95] |
| gpt4o mem0 H1 kernel-native task | 0.67 [0.10, 1.23] | 0.77 [0.21, 1.33] |
| gpt4o mem0 H1 kernel-replicated integration | 1.03 [0.45, 1.62] | 0.70 [0.27, 1.13] |
| gpt4o mem0 H1 kernel-replicated profile | 0.97 [0.41, 1.53] | 0.63 [0.20, 1.07] |
| gpt4o mem0 H1 kernel-replicated task | 0.67 [0.10, 1.23] | 0.73 [0.16, 1.30] |
| gpt4o mem0 H2 kernel-native integration | 0.93 [0.23, 1.64] | 0.80 [0.27, 1.33] |
| gpt4o mem0 H2 kernel-native profile | 1.00 [0.32, 1.68] | 0.73 [0.28, 1.18] |
| gpt4o mem0 H2 kernel-native task | 0.87 [0.15, 1.59] | 0.87 [0.14, 1.59] |
| gpt4o mem0 H2 kernel-replicated integration | 1.23 [0.62, 1.84] | 0.87 [0.41, 1.32] |
| gpt4o mem0 H2 kernel-replicated profile | 1.20 [0.58, 1.82] | 0.70 [0.21, 1.19] |
| gpt4o mem0 H2 kernel-replicated task | 1.10 [0.43, 1.77] | 1.13 [0.47, 1.80] |
| gpt4o mem0 H2-H0 kernel-native integration | 0.77 [0.04, 1.49] | 0.73 [0.18, 1.29] |
| gpt4o mem0 H2-H0 kernel-native profile | 0.80 [0.08, 1.52] | 0.50 [0.06, 0.94] |
| gpt4o mem0 H2-H0 kernel-native task | 0.87 [0.15, 1.59] | 0.83 [0.10, 1.57] |
| gpt4o mem0 H2-H0 kernel-replicated integration | 1.03 [0.36, 1.70] | 0.83 [0.37, 1.29] |
| gpt4o mem0 H2-H0 kernel-replicated profile | 1.03 [0.38, 1.69] | 0.47 [0.03, 0.90] |
| gpt4o mem0 H2-H0 kernel-replicated task | 1.10 [0.43, 1.77] | 1.10 [0.43, 1.77] |
| gpt4o pooled H0 kernel-native integration | 0.03 [-0.10, 0.16] | 0.00 [-0.10, 0.10] |
| gpt4o pooled H0 kernel-native profile | 0.10 [-0.02, 0.22] | 0.12 [-0.08, 0.31] |
| gpt4o pooled H0 kernel-native task | 0.00 [0.00, 0.00] | 0.00 [-0.05, 0.05] |
| gpt4o pooled H0 kernel-replicated integration | 0.07 [-0.07, 0.20] | -0.05 [-0.13, 0.03] |
| gpt4o pooled H0 kernel-replicated profile | 0.03 [-0.11, 0.18] | 0.10 [-0.07, 0.27] |
| gpt4o pooled H0 kernel-replicated task | 0.00 [0.00, 0.00] | 0.00 [-0.05, 0.05] |
| gpt4o pooled H1 kernel-native integration | 0.92 [0.35, 1.49] | 0.70 [0.27, 1.13] |
| gpt4o pooled H1 kernel-native profile | 0.93 [0.39, 1.48] | 0.62 [0.20, 1.03] |
| gpt4o pooled H1 kernel-native task | 0.87 [0.29, 1.44] | 0.92 [0.34, 1.49] |
| gpt4o pooled H1 kernel-replicated integration | 1.08 [0.50, 1.67] | 0.70 [0.23, 1.17] |
| gpt4o pooled H1 kernel-replicated profile | 1.03 [0.47, 1.60] | 0.68 [0.26, 1.10] |
| gpt4o pooled H1 kernel-replicated task | 0.87 [0.29, 1.44] | 0.88 [0.30, 1.47] |
| gpt4o pooled H2 kernel-native integration | 0.97 [0.24, 1.69] | 0.82 [0.25, 1.38] |
| gpt4o pooled H2 kernel-native profile | 0.98 [0.26, 1.71] | 0.72 [0.21, 1.23] |
| gpt4o pooled H2 kernel-native task | 0.97 [0.24, 1.70] | 0.93 [0.21, 1.65] |
| gpt4o pooled H2 kernel-replicated integration | 1.20 [0.60, 1.80] | 0.97 [0.48, 1.45] |
| gpt4o pooled H2 kernel-replicated profile | 1.18 [0.58, 1.79] | 0.82 [0.36, 1.27] |
| gpt4o pooled H2 kernel-replicated task | 1.15 [0.48, 1.82] | 1.13 [0.48, 1.79] |
| gpt4o pooled H2-H0 kernel-native integration | 0.93 [0.19, 1.67] | 0.82 [0.26, 1.37] |
| gpt4o pooled H2-H0 kernel-native profile | 0.88 [0.12, 1.64] | 0.60 [0.14, 1.06] |
| gpt4o pooled H2-H0 kernel-native task | 0.97 [0.24, 1.70] | 0.93 [0.20, 1.67] |
| gpt4o pooled H2-H0 kernel-replicated integration | 1.13 [0.49, 1.77] | 1.02 [0.54, 1.49] |
| gpt4o pooled H2-H0 kernel-replicated profile | 1.15 [0.52, 1.78] | 0.72 [0.28, 1.15] |
| gpt4o pooled H2-H0 kernel-replicated task | 1.15 [0.48, 1.82] | 1.13 [0.47, 1.80] |
| qwen inhouse H0 kernel-native integration | -0.17 [-0.58, 0.25] | 0.03 [-0.25, 0.32] |
| qwen inhouse H0 kernel-native profile | -0.17 [-0.58, 0.25] | 0.00 [-0.38, 0.38] |
| qwen inhouse H0 kernel-native task | 0.03 [-0.03, 0.10] | 0.17 [-0.03, 0.36] |
| qwen inhouse H0 kernel-replicated integration | -0.07 [-0.38, 0.24] | 0.10 [-0.05, 0.25] |
| qwen inhouse H0 kernel-replicated profile | -0.17 [-0.51, 0.17] | 0.00 [-0.10, 0.10] |
| qwen inhouse H0 kernel-replicated task | 0.00 [0.00, 0.00] | 0.10 [-0.01, 0.21] |
| qwen inhouse H1 kernel-native integration | 0.80 [0.27, 1.33] | 0.57 [0.18, 0.96] |
| qwen inhouse H1 kernel-native profile | 0.73 [0.17, 1.30] | 0.43 [0.11, 0.75] |
| qwen inhouse H1 kernel-native task | 1.07 [0.39, 1.74] | 1.10 [0.53, 1.67] |
| qwen inhouse H1 kernel-replicated integration | 0.67 [0.11, 1.22] | 0.57 [0.22, 0.92] |
| qwen inhouse H1 kernel-replicated profile | 0.67 [0.08, 1.25] | 0.40 [0.13, 0.67] |
| qwen inhouse H1 kernel-replicated task | 1.03 [0.38, 1.69] | 1.00 [0.40, 1.60] |
| qwen inhouse H2 kernel-native integration | 0.90 [0.29, 1.51] | 0.63 [0.21, 1.05] |
| qwen inhouse H2 kernel-native profile | 0.87 [0.22, 1.52] | 0.57 [0.15, 0.98] |
| qwen inhouse H2 kernel-native task | 1.07 [0.33, 1.81] | 0.90 [0.21, 1.59] |
| qwen inhouse H2 kernel-replicated integration | 1.03 [0.52, 1.55] | 0.73 [0.34, 1.12] |
| qwen inhouse H2 kernel-replicated profile | 1.10 [0.55, 1.65] | 0.47 [0.07, 0.87] |
| qwen inhouse H2 kernel-replicated task | 1.17 [0.49, 1.85] | 1.00 [0.37, 1.63] |
| qwen inhouse H2-H0 kernel-native integration | 1.07 [0.38, 1.75] | 0.60 [0.08, 1.12] |
| qwen inhouse H2-H0 kernel-native profile | 1.03 [0.28, 1.79] | 0.57 [0.09, 1.04] |
| qwen inhouse H2-H0 kernel-native task | 1.03 [0.28, 1.78] | 0.73 [-0.00, 1.47] |
| qwen inhouse H2-H0 kernel-replicated integration | 1.10 [0.50, 1.70] | 0.63 [0.20, 1.07] |
| qwen inhouse H2-H0 kernel-replicated profile | 1.27 [0.66, 1.87] | 0.47 [0.03, 0.90] |
| qwen inhouse H2-H0 kernel-replicated task | 1.17 [0.49, 1.85] | 0.90 [0.26, 1.54] |
| qwen mem0 H0 kernel-native integration | 0.10 [-0.23, 0.43] | 0.10 [-0.20, 0.40] |
| qwen mem0 H0 kernel-native profile | 0.13 [-0.22, 0.48] | -0.13 [-0.44, 0.17] |
| qwen mem0 H0 kernel-native task | 0.00 [0.00, 0.00] | 0.10 [-0.08, 0.28] |
| qwen mem0 H0 kernel-replicated integration | 0.13 [-0.16, 0.42] | 0.10 [-0.15, 0.35] |
| qwen mem0 H0 kernel-replicated profile | 0.07 [-0.29, 0.42] | 0.00 [-0.24, 0.24] |
| qwen mem0 H0 kernel-replicated task | 0.00 [0.00, 0.00] | 0.13 [-0.08, 0.35] |
| qwen mem0 H1 kernel-native integration | 0.50 [0.01, 0.99] | 0.50 [0.19, 0.81] |
| qwen mem0 H1 kernel-native profile | 0.47 [-0.02, 0.95] | 0.10 [-0.22, 0.42] |
| qwen mem0 H1 kernel-native task | 0.67 [0.15, 1.18] | 0.53 [0.04, 1.03] |
| qwen mem0 H1 kernel-replicated integration | 0.70 [0.24, 1.16] | 0.60 [0.25, 0.95] |
| qwen mem0 H1 kernel-replicated profile | 0.80 [0.33, 1.27] | 0.40 [0.10, 0.70] |
| qwen mem0 H1 kernel-replicated task | 0.63 [0.09, 1.17] | 0.57 [0.07, 1.06] |
| qwen mem0 H2 kernel-native integration | 0.47 [-0.12, 1.05] | 0.43 [-0.02, 0.89] |
| qwen mem0 H2 kernel-native profile | 0.30 [-0.31, 0.91] | 0.30 [-0.17, 0.77] |
| qwen mem0 H2 kernel-native task | 0.77 [0.05, 1.48] | 0.73 [0.09, 1.38] |
| qwen mem0 H2 kernel-replicated integration | 0.90 [0.43, 1.37] | 0.73 [0.37, 1.10] |
| qwen mem0 H2 kernel-replicated profile | 0.80 [0.26, 1.34] | 0.67 [0.22, 1.11] |
| qwen mem0 H2 kernel-replicated task | 1.03 [0.38, 1.69] | 0.97 [0.42, 1.52] |
| qwen mem0 H2-H0 kernel-native integration | 0.37 [-0.24, 0.97] | 0.33 [-0.21, 0.87] |
| qwen mem0 H2-H0 kernel-native profile | 0.17 [-0.51, 0.85] | 0.43 [-0.16, 1.03] |
| qwen mem0 H2-H0 kernel-native task | 0.77 [0.05, 1.48] | 0.63 [-0.07, 1.34] |
| qwen mem0 H2-H0 kernel-replicated integration | 0.77 [0.25, 1.28] | 0.63 [0.19, 1.08] |
| qwen mem0 H2-H0 kernel-replicated profile | 0.73 [0.13, 1.34] | 0.67 [0.16, 1.17] |
| qwen mem0 H2-H0 kernel-replicated task | 1.03 [0.38, 1.69] | 0.83 [0.20, 1.47] |
| qwen pooled H0 kernel-native integration | -0.03 [-0.32, 0.26] | 0.07 [-0.15, 0.28] |
| qwen pooled H0 kernel-native profile | -0.02 [-0.32, 0.29] | -0.07 [-0.31, 0.18] |
| qwen pooled H0 kernel-native task | 0.02 [-0.02, 0.05] | 0.13 [-0.00, 0.27] |
| qwen pooled H0 kernel-replicated integration | 0.03 [-0.19, 0.26] | 0.10 [-0.06, 0.26] |
| qwen pooled H0 kernel-replicated profile | -0.05 [-0.29, 0.19] | 0.00 [-0.13, 0.13] |
| qwen pooled H0 kernel-replicated task | 0.00 [0.00, 0.00] | 0.12 [-0.00, 0.23] |
| qwen pooled H1 kernel-native integration | 0.65 [0.21, 1.09] | 0.53 [0.22, 0.85] |
| qwen pooled H1 kernel-native profile | 0.60 [0.14, 1.06] | 0.27 [0.00, 0.53] |
| qwen pooled H1 kernel-native task | 0.87 [0.31, 1.42] | 0.82 [0.31, 1.32] |
| qwen pooled H1 kernel-replicated integration | 0.68 [0.22, 1.15] | 0.58 [0.27, 0.90] |
| qwen pooled H1 kernel-replicated profile | 0.73 [0.29, 1.18] | 0.40 [0.14, 0.66] |
| qwen pooled H1 kernel-replicated task | 0.83 [0.28, 1.39] | 0.78 [0.27, 1.30] |
| qwen pooled H2 kernel-native integration | 0.68 [0.15, 1.22] | 0.53 [0.11, 0.96] |
| qwen pooled H2 kernel-native profile | 0.58 [0.03, 1.14] | 0.43 [0.01, 0.86] |
| qwen pooled H2 kernel-native task | 0.92 [0.21, 1.62] | 0.82 [0.17, 1.46] |
| qwen pooled H2 kernel-replicated integration | 0.97 [0.54, 1.40] | 0.73 [0.39, 1.08] |
| qwen pooled H2 kernel-replicated profile | 0.95 [0.48, 1.42] | 0.57 [0.17, 0.97] |
| qwen pooled H2 kernel-replicated task | 1.10 [0.45, 1.75] | 0.98 [0.42, 1.55] |
| qwen pooled H2-H0 kernel-native integration | 0.72 [0.15, 1.28] | 0.47 [-0.00, 0.93] |
| qwen pooled H2-H0 kernel-native profile | 0.60 [-0.03, 1.23] | 0.50 [0.05, 0.95] |
| qwen pooled H2-H0 kernel-native task | 0.90 [0.19, 1.61] | 0.68 [-0.00, 1.37] |
| qwen pooled H2-H0 kernel-replicated integration | 0.93 [0.47, 1.39] | 0.63 [0.22, 1.04] |
| qwen pooled H2-H0 kernel-replicated profile | 1.00 [0.51, 1.49] | 0.57 [0.15, 0.99] |
| qwen pooled H2-H0 kernel-replicated task | 1.10 [0.45, 1.75] | 0.87 [0.27, 1.47] |

gpt-5.4 vs claude-sonnet-5.5: 126 of 144 differences in the same direction; 104 of 104 where either judge's 95% interval excludes 0.
- gpt4o inhouse H0 kernel-native task: 0.00 vs -0.03
- gpt4o inhouse H0 kernel-replicated task: 0.00 vs -0.03
- gpt4o mem0 H0 kernel-native task: 0.00 vs 0.03
- gpt4o mem0 H0 kernel-replicated task: 0.00 vs 0.03
- gpt4o pooled H0 kernel-native integration: 0.03 vs 0.00
- gpt4o pooled H0 kernel-replicated integration: 0.07 vs -0.05
- qwen inhouse H0 kernel-native integration: -0.17 vs 0.03
- qwen inhouse H0 kernel-native profile: -0.17 vs 0.00
- qwen inhouse H0 kernel-replicated integration: -0.07 vs 0.10
- qwen inhouse H0 kernel-replicated profile: -0.17 vs 0.00
- qwen inhouse H0 kernel-replicated task: 0.00 vs 0.10
- qwen mem0 H0 kernel-native profile: 0.13 vs -0.13
- qwen mem0 H0 kernel-native task: 0.00 vs 0.10
- qwen mem0 H0 kernel-replicated profile: 0.07 vs 0.00
- qwen mem0 H0 kernel-replicated task: 0.00 vs 0.13
- qwen pooled H0 kernel-native integration: -0.03 vs 0.07
- qwen pooled H0 kernel-replicated profile: -0.05 vs 0.00
- qwen pooled H0 kernel-replicated task: 0.00 vs 0.12

## pilot_v1_amem

k: gpt-5.4 1, claude-sonnet-5.5 1.

| difference | gpt-5.4 mean [95% CI] | claude-sonnet-5.5 mean [95% CI] |
|---|---|---|
| qwen amem H0 kernel-native integration | 0.07 [-0.43, 0.57] | -0.10 [-0.35, 0.15] |
| qwen amem H0 kernel-native profile | 0.00 [-0.54, 0.54] | -0.17 [-0.48, 0.14] |
| qwen amem H0 kernel-native task | 0.03 [-0.09, 0.15] | 0.13 [-0.03, 0.30] |
| qwen amem H0 kernel-replicated integration | 0.10 [-0.24, 0.44] | -0.03 [-0.22, 0.15] |
| qwen amem H0 kernel-replicated profile | 0.00 [-0.39, 0.39] | -0.03 [-0.15, 0.09] |
| qwen amem H0 kernel-replicated task | -0.03 [-0.10, 0.03] | 0.07 [-0.03, 0.16] |
| qwen amem H2 kernel-native integration | 0.73 [0.19, 1.28] | 0.57 [0.17, 0.97] |
| qwen amem H2 kernel-native profile | 0.60 [0.02, 1.18] | 0.47 [0.02, 0.91] |
| qwen amem H2 kernel-native task | 0.77 [0.08, 1.45] | 0.77 [0.18, 1.35] |
| qwen amem H2 kernel-replicated integration | 0.97 [0.45, 1.48] | 0.77 [0.38, 1.16] |
| qwen amem H2 kernel-replicated profile | 0.90 [0.30, 1.50] | 0.53 [0.12, 0.95] |
| qwen amem H2 kernel-replicated task | 1.17 [0.49, 1.85] | 1.00 [0.37, 1.63] |
| qwen amem H2-H0 kernel-native integration | 0.67 [-0.12, 1.45] | 0.67 [0.24, 1.10] |
| qwen amem H2-H0 kernel-native profile | 0.60 [-0.25, 1.45] | 0.63 [0.08, 1.18] |
| qwen amem H2-H0 kernel-native task | 0.73 [0.03, 1.43] | 0.63 [0.01, 1.26] |
| qwen amem H2-H0 kernel-replicated integration | 0.87 [0.17, 1.57] | 0.80 [0.37, 1.23] |
| qwen amem H2-H0 kernel-replicated profile | 0.90 [0.14, 1.66] | 0.57 [0.13, 1.00] |
| qwen amem H2-H0 kernel-replicated task | 1.20 [0.50, 1.90] | 0.93 [0.31, 1.56] |

gpt-5.4 vs claude-sonnet-5.5: 13 of 18 differences in the same direction; 12 of 12 where either judge's 95% interval excludes 0.
- qwen amem H0 kernel-native integration: 0.07 vs -0.10
- qwen amem H0 kernel-native profile: 0.00 vs -0.17
- qwen amem H0 kernel-replicated integration: 0.10 vs -0.03
- qwen amem H0 kernel-replicated profile: 0.00 vs -0.03
- qwen amem H0 kernel-replicated task: -0.03 vs 0.07

## bench_v2_smoke_amem

k: gpt-5.4 1, claude-sonnet-5.5 1.

| difference | gpt-5.4 mean [95% CI] | claude-sonnet-5.5 mean [95% CI] |
|---|---|---|
| qwen amem H0 kernel-native integration | 0.00 [-0.44, 0.44] | -0.10 [-0.44, 0.24] |
| qwen amem H0 kernel-replicated integration | 0.17 [-0.31, 0.65] | -0.23 [-0.60, 0.13] |

gpt-5.4 vs claude-sonnet-5.5: 0 of 2 differences in the same direction; 0 of 0 where either judge's 95% interval excludes 0.
- qwen amem H0 kernel-native integration: 0.00 vs -0.10
- qwen amem H0 kernel-replicated integration: 0.17 vs -0.23
