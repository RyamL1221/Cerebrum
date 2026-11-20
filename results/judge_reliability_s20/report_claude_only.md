# Judge reliability (200 answers, 10 repeats per judge)

## claude-sonnet-5.5

k by the rule: **1**

| dimension | units | exact | within 1 | alpha (repeats) [95% CI] | ordinal | median of 1: alpha [95% CI], exact | median of 3: alpha [95% CI], exact | median of 5: alpha [95% CI], exact |
|---|---|---|---|---|---|---|---|---|
| profile | 200 | 0.939 | 1.000 | 0.966 [0.951, 0.977] | 0.959 | 0.966 [0.951, 0.977], 0.939 | 0.978 [0.966, 0.988], 0.961 | 0.985 [0.975, 0.993], 0.973 |
| task | 200 | 0.955 | 1.000 | 0.985 [0.977, 0.991] | 0.969 | 0.985 [0.977, 0.991], 0.955 | 0.991 [0.984, 0.996], 0.973 | 0.993 [0.986, 0.998], 0.979 |
| integration | 200 | 0.939 | 1.000 | 0.963 [0.947, 0.975] | 0.958 | 0.963 [0.947, 0.975], 0.939 | 0.977 [0.964, 0.988], 0.963 | 0.982 [0.968, 0.992], 0.970 |

Judgments 2000, calls 2002, tokens 3421511 in / 829921 out (1711 / 415 per judgment).
