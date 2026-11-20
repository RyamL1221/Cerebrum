# Human rating of judged answers

People score a sample of the benchmark's answers with the judge's own
rubric. Two things are measured: whether people agree with each other
on that rubric, and whether each judge's LLM score agrees with them.
The judges and their statistics are AIOS `docs/METRICS.md`, "Judged
measures"; this protocol reuses them.

Written 2026-11-20, before any rating, and revised the same day after
a review. The kit: `benchmarks/shared_memory/human_rating.py`
(`sample`, `analyze`), `benchmarks/shared_memory/human_rating.html`
(the rating page) and `tests/agents/test_human_rating.py`. **The unit
tests are written but not run**: no test of that file has been
executed. What was exercised instead is in "What was checked".

## What it measures

**Two questions.** First, can people apply the judge prompt's rubric
consistently: Krippendorff's alpha across raters, per dimension.
Second, does each judge agree with the people: the raters' median
against each judge's LLM score, by the statistics METRICS.md uses
between the two judges (alpha, Spearman's ρ, the mean offset). The
keyword score (judge-free) is compared with the raters the same way,
and the two judges with each other on the same sample.

**What it does not measure.** The judges' direction agreement on the
paper's paired differences (kernel − other, H2 − H0). The draw spreads
the people over the whole sample, not over pairs of cells, so the
sample holds almost no paired difference: in the seed's draw, 4
kernel − other and 1 H2 − H0 pairs of one person's answers, too few to
measure a direction. Nor whether the rubric is the right definition of
a personalized answer: the raters use the judge's rubric, by design,
so that a person and a judge score the same thing.

## What a rater sees

**The four things a judge sees.** The user's profile, the task
context, the query and the answer (METRICS.md, "What the judge sees"),
in the judge prompt's words. The page shows the prompt's first line
("Evaluate the following AI assistant response."), each part under the
prompt's title for it (USER PROFILE, TASK CONTEXT, FOLLOW-UP QUERY,
ASSISTANT RESPONSE), each profile and task line as the prompt prints it
(`Preferred Tools: a, b`: a list joined with ", ", as
`judge.build_messages` joins it), and the query and the answer
unedited. The sampler takes the titles and labels from the judge's
template (`judge.USER_PROMPT_TEMPLATE`), not from a copy. A v2 answer
is its integration probe's, against the user's final profile and task
context, as the judge saw it (METRICS.md, "v1 and v2").

**The same inputs, several answers.** A person here is a profile, a
task context and a query: everything a judge sees but the answer. The
141 items come from 30 people, 4 or 5 answers each, and one person's
answers share everything but the answer (a v2 user's profile, task
context and query are its v1 user's). So a rater reads several answers
to the same inputs, which a judge never does: each judge call holds
one answer (`judge.build_messages`; `rejudge.rejudge_trial` judges one
trial per call). Seeing several answers to one question invites
comparing them, an effect the judges cannot have. The page's shuffle
scatters a person's answers through each rater's order; it does not
keep them apart.

**What is hidden.** The locus, the backend, the model, H, the
condition, the run, the dataset version, the user's id, the memory
block, every judge's score, the keyword and hybrid scores, and every
other rater's score. The raters' file holds no field that names any of
them: `blind_problems` refuses a file with a key the kit does not
define, at any depth, and refuses the 53 names in `FORBIDDEN_FIELDS`
wherever they occur. It reads keys, not text: an answer's own words
are screened when the sample is drawn, which takes no answer that
names a model, its maker or a memory system that its inputs do not
name ("Excluded, and why"). Item ids carry no meaning: `p01` to `p06`
for the warm-up, `h001` to `h135` for the rest, numbered after a
seeded shuffle of the sample. The order carries none: the page shows
the warm-up first, then the other items in an order shuffled for each
rater, seeded by the sample's id and the rater's code (FNV-1a and
mulberry32, in the page). Each rater gets a different order, and the
same one after a reload.

**What the answers say themselves.** The answers are shown as the
judge saw them, unedited. Of the 141 answers the seed draws from the
three runs, none names a model, its maker or a memory system (the
names of `HIDDEN_NAMES`) and none contains "kernel"; 23 contain
"memory" or "memories" and 7 "remember" (a scratch count, 2026-11-20;
what the words refer to was not read). A rater sees these words as the
judge did.

**The instructions.** The page's instructions on rating are five:
score each dimension on its own, with the rubric's words; judge the
answer as written, look nothing up, and ask no one about an item until
every rater has finished; skip an item that cannot be scored and say
why in the comment; the first items are a warm-up and are not
analysed; work in sessions of about 45 minutes, with the page open in
one tab. The 45 minutes are a judgment call against fatigue, not
derived; nothing in the analysis depends on them. Raters get no scored
examples: an example's score would have to come from someone, and the
judges' scores stay hidden. Raters are not told the conditions or the
hypotheses.

**Who rates.** Three raters. People who did not build or run the
systems are preferred: they are less likely to tell from its style
which system wrote an answer. A rater who knows the hypotheses is
named as such in the report (`analyze --informed`).

## The rubric

The judge prompt v2's general guidance and its three dimensions with
their anchors, word for word (`judge.py`: `SYSTEM_PROMPT`,
`USER_PROMPT_TEMPLATE`; prompt sha256 `17f43dd9…`). `rubric()` reads
them from the prompt when the sample is drawn, the raters' file
carries them, and the page shows them beside every item;
`blind_problems` refuses a raters' file whose rubric is not the
prompt's. What is not shown is the prompt's instructions on the reply
(that the judge is an expert evaluator who answers with a JSON object
only, and the object's keys): a rater gives three scores and, if they
wish, a comment.

**Guidance.** "You are evaluating whether an assistant's response
reflects the user profile and task context given below. A concise
response that correctly references these attributes is
well-personalized; a long response that does not is generic." And:
"Score based on whether the response content references profile and
task attributes, regardless of response length. A short response that
correctly references the user's preferred tools and current project is
well-personalized."

| Score | Profile Usage (1-5) | Task Usage (1-5) | Integration (1-5) |
|---|---|---|---|
| 5 | Correctly and specifically references multiple profile attributes (tools, language, style) in the recommendation, regardless of response length | Correctly and specifically references project goals, blockers, and next steps in the recommendation, regardless of response length | Seamlessly combines profile preferences and task context into a single grounded recommendation |
| 4 | Correctly references most profile attributes | Correctly references most task context details | Combines both sources with minor gaps in integration |
| 3 | References some profile attributes but misses key ones | References some task context details but misses key ones | Addresses profile and task context separately without integrating them |
| 2 | Vague or incorrect references to profile attributes | Vague or incorrect references to task context | Mentions both sources but the recommendation does not logically follow from them |
| 1 | No evidence of profile knowledge; response could apply to any developer | No evidence of task context knowledge; response is generic advice | No integration; response addresses at most one source or is entirely generic |

`judge.py` is the source; this table is a copy for the reader.

## The sampling rule

**Source.** The answers both judges have scored at their k (1 for
both: `results/judge_reliability_s20/report.md`): `pilot_v1_hetero`
(1,080 v1 answers), `pilot_v1_amem` (180) and `bench_v2_smoke_amem`
(90 v2 integration probes), in the re-judged trees
`results/s20_rejudge/gpt-5.4/` and
`results/s20_rejudge/claude-sonnet-5.5/`
(`results/s20_rejudge/PROVENANCE.md`). The trees are not committed:
they are in the checkout's `results/` and archived in `repo-artifacts`
(PROVENANCE.md, "Archive"). The first tree gives the answers and every
tree its judge's records. The sampler refuses two trees that hold
different inputs for one trial, two different scores of one judge for
one trial, and a judge used at two k. It reads no iCloud copy
(`results_x 2.json`).

**Strata.** The cell: dataset version, locus, backend, model and H
(`judge_reliability.cell_of`, the calibration set's cells without its
score band). The dataset version is in the cell beside locus,
backend, model and H because a v1 answer and a v2 integration probe
are different kinds of answer. The three runs have 45 cells of 30
answers each: 36 in `pilot_v1_hetero`, 6 in `pilot_v1_amem`, 3 in
`bench_v2_smoke_amem`. No score is read: unlike `calibration_v1`,
which stratified by the stored hybrid score, the sample takes no band,
so the draw does not depend on a judge.

**Per cell.** 3 answers from each cell: 135 in all. Three, because
near the threshold 135 items give an interval about ±0.05 wide at 5.5
to 6.4 hours per rater; 2 per cell give about ±0.06 at 3.7 to 4.4
hours, 4 per cell about ±0.04 at 7.2 to 8.5 ("What the numbers buy").
By factor: locus 45 each; backend 54 in-house, 54 Mem0, 27 A-MEM;
model 81 Qwen, 54 GPT-4o; H 54 at 0, 36 at 1, 45 at 2; version 126 v1,
9 v2. The cells weigh equally, so the factors do not (the runs' cells
are not balanced).

**Within a cell.** Each pick is the candidate whose person has been
drawn least so far, ties broken by a seeded shuffle of the cell. The
person is the profile, the task context and the query, hashed
(`person_sha256`): what a rater sees of the user. Every cell holds an
answer of each of 30 people (but for the 12 answers the name rule
below removes), and the v2 run's 30 users are the v1 runs' 30 people
(the same profile, task context and query; 30 people in all over the
1,338 candidates), so without this a few people could fill the
sample. With it, the 141 items (135 and the warm-up) come from the 30
people, 21 with 5 items and 9 with 4; the 135 analysed, 15 with 5 and
15 with 4; the 9 v2 items, 9 people who also have v1 items (scratch
run, 2026-11-20).

**Excluded, and why.** Each with its count in the three runs (from the
scratch run, 2026-11-20):

- a failed trial: there is no judged answer (0 of 1,350);
- another condition than the plain one: a negative control, an
  ablation switch, or a stress setting other than the harness's
  default (4 agents, sequential, load 1, no fault: `TrialResult`'s
  defaults). No stratum names them (0);
- a baseline (`kernel_private`, `naive_concat`, `vanilla_rag`): not a
  locus (0);
- a trial without the profile, the task context, the query or the
  answer, or with a blank query or answer: there is nothing to show
  (0);
- an answer that names a model, its maker or a memory system that its
  profile, task context and query do not name: a rater would learn
  what is hidden (12: 11 Qwen answers signed "Qwen" and 1 GPT-4o
  answer that suggests "GPT-based models"). The names are
  `HIDDEN_NAMES`: Qwen, GPT and ChatGPT, OpenAI, Llama, Alibaba, Meta
  AI, Anthropic, Claude, Mem0, A-MEM, Graphiti, Zep, AIOS, Cerebrum;
- a trial in no cell (its path names no model or backend) (0);
- an answer without a complete record of each required judge, or with
  one made under another judge prompt (both judges are required by
  default: `--require-judges`) (0).

The name rule takes answers from some cells only: 2 cells keep 28 of
their 30 answers, 8 keep 29 and 35 keep all 30. An answer signed with
the model's name may differ in style from the others, so the sample is
slightly less representative of those cells; 12 of 1,350 answers are
left out for it.

**Duplicates.** An answer whose inputs (query, answer, profile and
task context, hashed by `judge_reliability.inputs_sha256`) are those
of an answer already drawn is passed over: one text is one item.
Duplicates are common: 317 of the 1,338 candidates repeat another
candidate's inputs (1,021 distinct). An answer repeated across cells
can be drawn in whichever of its cells the order reaches first; the
key lists its twins with their cells and judges' scores (44 of the 141
drawn items have one).

**Seed.** 20261122 (`RATING_SEED`), fixed now, before any rating: the
next of the project's seeds (20261120 the calibration set, 20261121
the second judge's grid subset). Python's `random.Random(seed)`
shuffles each cell's candidates, then the cells into a visiting order,
then the sample before it is numbered.

**Warm-up.** After the sample, the first 6 cells of the visiting
order give one more answer each, by the same rule. The warm-up is
rated first and never analysed: the first items are where a rater
learns the page and the rubric. Six is a judgment call, not derived:
about 15 minutes, a third of a session, so that each dimension's
anchors are used a few times before the analysed items begin.

**Reproducing.** The same trees, runs and seed give the same raters'
file and key, byte for byte (sample id `911207beb4f4`); another seed
gives another sample (seed 20261123 shared 17 of the 135 items). Both
were checked in a scratch run, 2026-11-20. Nothing drawn is committed:
the kit reproduces the sample from the stored results and the seed.

**The full grid, later.** The same rule draws from the grid's answers
(`sample --tree <grid tree> ...`). The grid's cells are not decided
(`FULL_GRID.md`), so the count per cell must be set then: at 3 per
cell the total grows with the cells. The second judge scores 30% of
the grid's users, by user (`FULL_GRID.md`, "The two judges"), so
requiring both judges restricts the draw to those users;
`--require-judges gpt-5.4` drops the requirement for the second. A
cell that loses every trial to the exclusions (all failed, or none
judged by both) is reported short, with 0 answers, like any cell
short of the count.

## The design across raters

**Raters.** 3. An odd number, so the median of their scores is one of
the scores (as METRICS.md takes an odd k for a judge's median); three
is the fewest for a median that no single rater sets.

**Items per rater.** Every rater rates every item: 141, the 6 warm-up
items and the 135. The design is fully crossed: every item has three
ratings, alpha compares every rater with every other on every item,
and the median exists for every item all three scored.

**Time.** About 2.3 to 2.7 minutes per item, and 5.5 to 6.4 hours per
rater, 16.5 to 19.3 rater-hours in all: an estimate, not a
measurement. The 141 drawn items hold 55,912 words (answers: median
318, quartiles 242.5 and 390, at most 639; profile, task context and
query: median 85 per item), which take 3.7 to 4.7 hours to read at 250
to 200 words a minute; scoring is taken as 45 seconds an item. That is
7.3 to 8.6 sessions of 45 minutes, so 8 or 9 per rater. The other
designs' hours scale the same minutes per item. The page records the
seconds spent on each item, and the report gives each rater's median
seconds per complete rating and their hours on every row, the warm-up
and skipped items included.

**What the numbers buy.** A simulation (scratch, 2026-11-20; not
committed): each answer's true score is the mean of the two judges'
LLM scores on it, over the 1,350 stored answers; a rater's score is
that plus normal noise, rounded and kept in 1 to 5, with the noise set
so that alpha is about the value in the first column. For each row, 60
simulated samples of answers drawn independently, each with a
bootstrap interval of 1,000 resamples; the table gives the median
width of the 95% interval and how often the point estimate reached
0.80. Three raters:

| Alpha | Items | Profile: width | Profile: reached 0.80 | Integration: width | Integration: reached 0.80 |
|---|---|---|---|---|---|
| 0.85 | 90 | 0.088 | 58 of 60 | 0.088 | 60 of 60 |
| 0.85 | 135 | 0.072 | 60 of 60 | 0.067 | 60 of 60 |
| 0.85 | 180 | 0.060 | 60 of 60 | 0.059 | 59 of 60 |
| 0.80 | 90 | 0.116 | 26 of 60 | 0.120 | 29 of 60 |
| 0.80 | 135 | 0.092 | 31 of 60 | 0.092 | 33 of 60 |
| 0.80 | 180 | 0.077 | 31 of 60 | 0.080 | 32 of 60 |
| 0.667 | 90 | 0.171 | 0 of 60 | 0.182 | 0 of 60 |
| 0.667 | 135 | 0.142 | 0 of 60 | 0.144 | 0 of 60 |
| 0.667 | 180 | 0.122 | 0 of 60 | 0.128 | 0 of 60 |

So at 135 items an alpha near 0.80 is known to about ±0.05, and a
true alpha of 0.85 reached the threshold in every simulated sample. At
a true 0.80 the point estimate falls on either side of the threshold
about as often (31 and 33 of 60 at 135 items): the rule cannot tell
0.80 from a little less.
Two more raters buy about what 45 more items do, for more ratings: at
alpha 0.80, five raters at 135 items (675 ratings) give an interval
0.081 (Profile) and 0.078 (Integration) wide, three raters at 180
items (540 ratings) 0.077 and 0.080. The simulation assumes
raters without a lean of their own and noise alike on every answer;
real raters' disagreements will differ, so these widths are a guide,
not a promise. At 90 items (2 per cell, 3.7 to 4.4 hours per rater)
the interval at 0.80 is about ±0.06.

**The items are not independent.** The table drew answers
independently; the sample is 30 people's clusters of 4 or 5 answers to
the same inputs. Two measures of what that costs, both scratch,
2026-11-20:

- a second simulation draws 30 people and 4 or 5 answers of each (135
  items), with rater noise independent of the person: at a true 0.80
  the interval is 0.092 wide over items and 0.100 over the people on
  Profile, 0.093 and 0.098 on Integration;
- on the two judges' own agreement on the drawn 135, whose
  disagreements cluster by person, the interval over the people is
  wider than over items by 22% on Profile (0.192 against 0.157), 17%
  on Task (0.070 against 0.060) and 6% on Integration (0.134 against
  0.126).

If the raters' disagreements cluster as the judges' do, the ±0.05 at
135 items is about ±0.06 on Profile and still about ±0.05 on
Integration over the people (an extrapolation: 0.092 widened by 22%
and by 6%). The item intervals are therefore optimistic, and the
report gives the interval over the people beside each one over items.

For a judge against the raters' median, the two judges' agreement on
the same 135 items gives the scale (`analyze` without ratings, scratch
run): alpha Profile 0.728 [0.640, 0.797], Task 0.936 [0.898, 0.958],
Integration 0.783 [0.712, 0.838], and over the people [0.620, 0.811],
[0.891, 0.961] and [0.702, 0.836]; offset (claude-sonnet-5.5 −
gpt-5.4) −0.48 [−0.62, −0.35], −0.30 [−0.37, −0.22], −0.35 [−0.48,
−0.22], and over the people [−0.66, −0.32], [−0.39, −0.21] and
[−0.51, −0.18]. A median that agrees with a judge about as well would
be measured to about ±0.08 (Profile) and ±0.06 (Integration) in alpha
over items, ±0.10 and ±0.07 over the people, and to ±0.14 and ±0.13
in the offset over items, ±0.17 and ±0.17 over the people.

## The agreement statistic

**Between the raters.** Krippendorff's alpha, interval metric, the
raters as coders, per dimension, over the 135 items. A skipped rating
is a missing value, which alpha allows (Krippendorff 2011). Ordinal
alpha is reported beside. The 95% interval is the percentile bootstrap
over items, 2,000 resamples, seeded (`judge_reliability.bootstrap`, as
METRICS.md does for the judges), and beside it the same bootstrap over
the people (a resample draws the 30 people with replacement and takes
every item of each). Beside them: exact and within-1 agreement over
every pair of raters on each item (METRICS.md's, with raters for
repeats), and the two-coder alpha of each pair of raters and of each
judge with each rater.

**Why alpha, interval.** Alpha takes any number of raters, missing
values and the data's metric (Hayes and Krippendorff 2007; Krippendorff
2011), and it is the statistic of the judges' reliability (METRICS.md),
so raters and judges are measured by one module, `judge_reliability`:
its `alpha`, which takes missing values, for the raters; its
`repeats_alpha` and `two_coder_alphas`, which measured the judges and
equal `alpha` on complete data (to 4e-16 on 200 random complete score
matrices, scratch, 2026-11-20); its `agreement` for a judge against
the raters' median. Interval, because the paper treats the scores as
numbers: it reports their means and paired differences with t
intervals (METRICS.md, "Conventions"), and interval alpha does too: it
weighs a disagreement by its squared size, as a variance does. Our
bootstrap resamples items (or people), as the judges' intervals do;
Hayes and Krippendorff (2007) resample pairs of judgments instead. The
two can differ in a small sample.

**The threshold.** Fixed now, before any rating: alpha at least 0.80
(the point estimate) on Profile and on Integration, the bar and the
dimensions of the k rule (METRICS.md, "The k rule"). The bar is the
same; the test is not. The k rule held each judge to 0.80 on its
agreement with itself, the alpha between the medians of disjoint sets
of its own repeats (METRICS.md, "Reliability protocol"): stability.
The raters' alpha is agreement between different people:
reproducibility, which Hayes and Krippendorff (2007) call the kind
that "arguably is the strongest and most feasible kind to test". It is
the stricter test, and the two judges, taken as two coders, do not
pass it: Profile 0.498 [0.382, 0.597] and Integration 0.683 [0.608,
0.741] on `calibration_v1` (`results/judge_reliability_s20/report.md`,
"gpt-5.4 vs claude-sonnet-5.5"), 0.728 and 0.783 on this sample. So
the raters' alpha is read beside the two judges' alpha with each other
on the same items, which the report gives. Task is reported and not in
the rule, as for the judges. The bar follows the usual convention:
rely on data with alpha of at least 0.800, draw only tentative
conclusions from 0.667 to 0.800, and discard the rest (Krippendorff
2004, pp. 241-243, as cited by Wikipedia's "Krippendorff's alpha"; the
book was not read).

**What follows.** Per dimension, from the raters' alpha; the report
marks every comparison with the median by it:

- alpha at least 0.80: the raters' median is the human reference, and
  each judge's agreement with it is reported as the evidence on that
  judge on that dimension (no pass mark is set: see below);
- from 0.667 to 0.80: the same, marked as a tentative reference;
- below 0.667: the median is no reference. Each judge's agreement with
  it is still reported, marked "no reference", and counts neither for
  nor against a judge; the paper says that people could not apply the
  rubric reliably on that dimension, beside the two judges' alpha with
  each other on the same items, measured the same way.

No rater is dropped, no item removed and no item rated again after the
ratings are seen, to reach the threshold or for any other reason. A
second round (revised instructions, other raters, or a new sample from
a new seed) is a new version of this protocol, written before its
ratings.

**The raters' median against each judge.** On the items all three
raters scored: their median, which is one of their scores, against
each judge's LLM score at its k, per dimension, as METRICS.md defines
the agreement between the judges: interval alpha (the median and the
judge as two coders) with its bootstrap interval over items and over
the people, Spearman's ρ, and the mean offset (judge − raters' median)
with its 95% t interval and its bootstrap interval over the people;
and exact agreement. The same against the keyword score, and the two
judges with each other on the sample (second − primary). Per level of
each factor of the cell (locus, backend, model, H, version): the mean
offset with its t interval, so a judge whose leniency differs by locus
or by H shows it. This is descriptive: a level holds 27 to 81 items
here, except the dataset version (126 v1, 9 v2).

No pass mark is set for a judge. The report puts each judge's
pairwise alpha with each rater beside the raters' pairwise alphas, so
a reader can see whether a judge agrees with a rater as well as two
raters agree with each other.

**Skipped items.** An item a rater skipped has no complete rating: no
row, empty scores, or fewer than three scores (the page exports scores
only when all three are given; a hand-edited file may hold fewer). For
alpha it is a missing value. It has no median, is left out of the
median's comparisons, and is listed under "Without a median" with each
rater's scores as given and every rater's comment (the page asks a
rater who skips an item to say why). Each rater's summary counts
complete, incomplete and unrated items.

**If a rater drops out.** With two raters the median is not computed
(the median of two scores need not be one of them); alpha and the
pairwise alphas are.

## Disagreements

**What is listed.** After every rating is in, the report lists:

- between the raters: every item and dimension where the three scores
  span 2 points or more;
- the raters' median against each judge, and against the keyword
  score: every item and dimension where they differ by 2 or more;
- the items without a median.

Two points, because one point is the step between neighbouring
anchors, which METRICS.md's within-1 agreement counts as agreement;
two points means the two readings of the rubric differ. For scale: on
the 1,350 stored answers the two judges differed by 2 or more on
Profile for 201, on Task for none and on Integration for 40 (counted
from the two trees' records, 2026-11-20).

**What is shown beside each.** Every rater's score (on an item without
a median, each rater's three scores as given), the median, each
judge's score, the keyword score, the item's cell and its source trial
(file and trial index), and every rater's comment on the item, the
comment of a skipped or incomplete rating included. The report holds
no answer text: an item is read in the raters' file by its id.

**Nothing dropped.** Every item stays in every statistic it can enter;
the lists are for reading. No list is shown to a rater.

## The kit

**Drawing.**

```
python -m benchmarks.shared_memory.human_rating sample \
    --tree results/s20_rejudge/gpt-5.4 \
    --tree results/s20_rejudge/claude-sonnet-5.5 \
    --items <raters' directory>/items.json \
    --key <private directory>/key.json
```

It refuses a raters' file that is not blind, a key in the raters'
directory or under it or above it, a cell short of answers (a cell
with none included; `--allow-short` writes the sample anyway), and
replacing a file that holds another sample (`--force`). The key holds
each item's source (run, file, condition index, trial index, method),
its cell, its person's hash, both judges' scores, the keyword score
and its twins; no answer text. The raters get the page and
`items.json`; nobody who rates gets the key.

**Rating.** Open `human_rating.html` from disk (no network: the page
loads nothing and its Content-Security-Policy forbids it), pick
`items.json` and type the rater code. One item at a time, the rubric
beside it; the three scores, an optional comment; back, skip, clear
and "first unrated". Keys outside the comment box: 1 to 5 score the
dimension that has the focus, else the first without a score, and move
on (with all three given and no dimension focused, a digit changes no
score and the page says how to change one); Enter or n save and go on,
b back, s skip, x clear, c the comment (Esc leaves it), u first
unrated, e export. Progress is kept in the browser's storage under the
sample's id and the rater code. Where storage is off the page says so
and still works, and progress lasts until the page is closed. One tab
at a time: when another tab of the browser saves the same sample and
rater code, this tab stops and saves nothing more, so that it cannot
overwrite the other's ratings; reloading it and starting again takes
over. The page follows the system's light or dark setting.

**Exporting.** `human_rating_<sample>_<rater>.csv`, one row per item
in the rater's order, with the columns `sample`, `item_id`, `rater`,
`profile`, `task`, `integration`, `comment`, `seconds` (time on the
item while the page was visible), `rated_at` (when the complete
rating was last changed, UTC) and `position`; RFC 4180 quoting, UTF-8
with a byte-order mark. Scores are written only when all three are
given. "Show CSV" gives the same text to copy where a download is
blocked.

**Analysing.**

```
python -m benchmarks.shared_memory.human_rating analyze \
    --key <private directory>/key.json \
    --ratings r1.csv r2.csv r3.csv --informed r2 \
    --md report.md --json report.json
```

`--informed` names the raters who know the hypotheses (here `r2`;
leave the flag out if no rater does). It refuses a row of another
sample, an item the
key does not hold, a score that is not 1 to 5, a row without a rater,
a rater's second row for one item, and an informed rater without
ratings. Without `--ratings` it reports the sample and the judges'
agreement on it. The ratings, the key and the report are archived
with the run records, not committed: a comment may quote an answer.

## What was checked

Scratch runs, 2026-11-20, with every output in a scratch directory and
nothing committed. The scratch scripts blocked every socket connection
before importing the kit, so no kernel, model or network could be
reached:

- `sample` on the two trees: 1,350 trials read, 12 excluded (the name
  rule), 1,338 candidates, 45 cells of 3, `blind_problems` empty, no
  drawn answer with a name of `HIDDEN_NAMES`. Drawn twice, the two
  files were byte-identical. Every profile and task line of the 141
  items is a line of the user message `judge.build_messages` builds
  for that answer, and its query and answer are in it.
- `analyze` on Krippendorff's example (four coders, twelve units,
  missing values): interval alpha 0.849 and ordinal 0.815, the
  published values. On a hand-worked case (medians 1 to 4, a judge one
  higher): alpha 0.708 (1 − 28/96), ρ 1, offset +1, exact 0. On
  made-up ratings with skipped and incomplete rows, comments and an
  informed rater, into a strict JSON report.
- The CSV: files written by the page's own `csv()` (run in Node 20 on
  the revised page and the drawn raters' file) were read back by
  `read_ratings`, and a comment with quotes, a comma, a line break and
  a trailing space came back intact (trimmed).
- The page: its script parses (`node --check`), and its rules without
  the page (the file check, each rater's order, the CSV) ran in Node.
- The unit tests' expected values, where arithmetic did not settle
  them (a seed's draw, a bootstrap interval, a list's order), were
  computed by calling the module by hand on the same made-up inputs;
  the test file itself was neither run nor imported. The person rule's
  test was also drawn with the earlier rule (a v2 user as a person of
  its own): at the test's seed, 3, the earlier rule shows 3 distinct
  people where the test asks for 4.

**Not checked.** The page has not been opened in a browser: its
layout, its keys, its storage, its second-tab guard and its download
are unverified. The unit tests read the page as text only: its CSV
writer, each rater's order, its storage and its keys run in no unit
test (the CSV writer and the order ran only in the scratch Node run
above). The time per item is an estimate. The unit tests are unrun.

## Sources

- Krippendorff, K. (2011; literature updated 2013). Computing
  Krippendorff's alpha-reliability.
  https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf
  (accessed 2026-11-20). The alpha with missing values and its
  metrics; the worked example the tests use.
- Hayes, A. F., and Krippendorff, K. (2007). Answering the call for a
  standard reliability measure for coding data. Communication Methods
  and Measures 1(1): 77-89.
  https://www.asc.upenn.edu/sites/default/files/2021-03/Answering%20the%20Call%20for%20a%20Standard%20Reliability%20Measure%20for%20Coding%20Data.pdf
  (accessed 2026-11-20). Alpha as the standard; its bootstrap;
  reproducibility as the strongest kind of reliability.
- "Krippendorff's alpha", Wikipedia,
  https://en.wikipedia.org/wiki/Krippendorff%27s_alpha (accessed
  2026-11-20): the 0.800 and 0.667 convention, citing Krippendorff,
  K. (2004), Content Analysis, pp. 241-243.

Open: who the three raters are, and whether someone who knows the
hypotheses may rate; 135 items or 90 (5.5 to 6.4 or 3.7 to 4.4 hours
per rater); the count per cell, and whether both judges are required,
for a draw from the grid; whether a second round runs if the threshold
is not met; whether a grid draw stratifies by condition (the stress
levels) instead of keeping the plain condition only; whether a
criterion for a judge against the raters is fixed before the ratings
(for example, each of a judge's alphas with a rater within the range
of the raters' alphas with each other) or none is, as now; whether an
answer that names a hidden factor is left out, as now, kept and listed
in the report, or shown with the name masked (which is not what the
judge saw); whether a person's answers are kept apart in each rater's
order instead of only shuffled.
