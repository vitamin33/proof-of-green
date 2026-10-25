---
title: "The Check the Agent Cannot Skip: 0 of 40 Silent Failures vs 22 of 40"
published: false
description: "A check the agent cannot skip removed every silent failure in 40 injected runs at the cost of no check. As an optional tool it doubled the bill and let 6 through."
tags: ai, agents, testing, llm
canonical_url: https://serbyn.io/blog/enforced-checkpoint-0-of-40-silent-failures-vs-22-of-40
---

> Part of the series: [When an AI Agent Says Done: 0% vs 100% False Greens](https://serbyn.io/blog/same-model-0-and-100-where-the-verifier-gap-actually-lives)

A check the agent cannot skip removed every silent failure, a run that finishes wrong and reports success, in 40 runs with a planted error, and cost the same as running no check at all. The same check, offered to the agent as a tool it could call when it wanted, was used in 38 of 40 runs, doubled the bill, and still let 6 of 40 through. The difference was never whether the agent had access to the truth. It was who decided when to look.

## The Short Version

- **What I tested.** A checkpoint: ordinary code that re-runs a query against the source of truth and hands the agent the real answer next to the tool's answer. Does it stop an agent from finishing wrong and saying "done"?
- **What I found.** With no checkpoint, 22 of 40 runs finished wrong and claimed success. With the checkpoint offered as an optional tool, 6 of 40. With the checkpoint forced into every tool result by the code around the agent, 0 of 40.
- **How.** One model, `deepseek-flash`. Eight tasks over a small order database, one silently wrong tool result planted in each run. 160 runs at the final stage, 40 per arm. Five hypotheses with numeric thresholds, written and committed before any data. Right and wrong decided by asserts on the final state, never by a model.
- **What it means.** Reconciliation works when the code enforces it. Handed to the agent as a choice, it gets used a lot, aimed at the wrong things, and paid for twice.
- **What it cost.** The forced checkpoint ran at 1.00x the cost of no checkpoint. The optional tool ran at 1.94x. The whole experiment, pilot, both stages, the follow-up without the sentence and three aborted starts, was $3.67.

## Why I Ran This

The [flagship post](https://serbyn.io/blog/same-model-0-and-100-where-the-verifier-gap-actually-lives) ends with advice: put a deterministic check at every hand-off, because the agent will not notice a wrong tool result on its own. That advice came from the failure I had measured. It did not come from a measurement of the fix. Telling the model to double-check itself had bought [nothing at 1.03x](https://serbyn.io/blog/same-model-0-and-100-where-the-verifier-gap-actually-lives), so I knew what did not work. I did not know what did, or what it cost.

The question also splits into two that matter for different people. For whoever pays: what does a checkpoint cost per run, and how many silent failures does it remove. For whoever builds: must the code around the agent force the check? Or is it enough to give the agent a reconcile tool and trust it to use it. I predicted it would not use it. That prediction was wrong. The agent used the tool in 38 of 40 runs and still missed the same blind spot, and that pattern is the useful part of this post.

## The Setup

The environment is the same small order desk as the previous experiment: 15 orders, 6 customers, a handful of tools like `list_orders`, `get_customer` and `sum_totals`. Small enough that every run is graded by code, which is what makes a 0 of 40 checkable. Eight tasks, such as "ship every pending EU order and report how many" or "sum the shipped orders of customer C4". Every task has a right answer computed by code from the data. A run is graded by asserting on the final state, and no model ever judges another model.

In each injected run, one tool result is silently wrong: a list missing its last item, a sum missing its smallest part, a customer returned with the wrong region. No error, no warning, a plausible number. The previous experiment had a flaw here, and I fixed it before collecting any data. Two of its injections fired in every run and could not change the answer, because the corrupted value never touched what the task asked for. This time a script checks two things for every task: that the planted failure fires on the obvious path, and that believing it produces a wrong answer. A planted failure that cannot change the answer measures nothing.

The new piece is `reconcile`. It takes a tool name and its arguments, re-runs that query directly against the data, and returns the authoritative result. It is never corrupted. Three arms use the same injections and differ in one thing each:

- No checkpoint. The baseline, run on the same day and the same model as the other two.
- Reconcile as a tool. The agent sees `reconcile` in its tool list with a one-line description. Whether to call it is its choice. The instructions are byte-for-byte the baseline's.
- Reconcile enforced. After every tool call, my code runs `reconcile` on the same query and hands the agent both answers side by side, the tool's own result and the checkpoint's, labelled so the agent can tell which is which (in code: `{"result": ..., "checkpoint": {"source_of_record": ...}}`). One line is added to the instructions, saying the checkpoint is the one to trust. A test in the repository compares the three arms' instructions and tool lists line by line, and fails if anything besides the reconcile behaviour differs.

The number I care about is the silent failure rate: of the runs where the injection actually fired, how many finished wrong and claimed success. That is the run a team never hears about until a customer does.

## What Came Out

160 runs in the final stage, 40 per arm, every one of the 120 injections fired. The chart is generated from the raw records.

![Silent failures per fired injection and cost per run, by arm, deepseek-flash](https://serbyn.io/blog/checkpoint-silent-failures.png "Left: runs that finished wrong and claimed success, out of 40 fired injections per arm. Right: cost per run relative to no checkpoint. Error bars are Wilson 95% intervals, the range the true rate could sit in given only 40 runs per arm.")

With no checkpoint, 22 of 40 runs finished wrong, and all 22 said they had succeeded. That is the same failure as the previous experiment's 45 of 45, the agent claiming success while wrong, on a newer model with corrected tasks. Every answer comes with a confidence score the model reports on a 0 to 100 scale. On those 22 wrong runs it never dropped below 95.

With the optional tool, 6 of 40. With the enforced checkpoint, 0 of 40, and every run finished with the right answer. Forty runs cannot prove a true zero. With this few runs, "none in forty" only rules out a real failure rate above 8.8%, about one run in eleven. It does not prove the check is perfect.

Cost per run: $0.00723 with no checkpoint, $0.01399 with the optional tool, $0.00720 enforced. The enforced arm cost the same as doing nothing, to three decimals. I explain why below.

Three of the five pre-registered hypotheses held. The enforced checkpoint pushed silent failures under the 25% threshold, cost under 1.5x, and restored the correct outcome in far more than the 70% of runs I had required. Two were falsified, both about the optional tool. I had predicted the agent would use it in fewer than half its runs and that its silent failure rate would stay near the baseline. It used it in 38 of 40 runs, and the rate fell to 15%. Being wrong here changed the prediction and left the conclusion in place: the agent used the tool in 38 of 40 runs and still failed 6 times, so it stayed behind the enforced arm's 0 of 40, and the advice to force the check stands.

## Where the Optional Tool Went Wrong

Given a reconcile tool, the agent reconciled a great deal. In the optional arm, 371 of its 952 tool calls were reconciliations, close to four calls in ten, a median of 6 per run. That is the doubled bill. And 6 runs still ended wrong and confident.

All 6 are on the two tasks where the corruption was a customer's region. In four of them the agent reconciled between one and four things, and none of them was the customer whose region had been changed. In the other two it reconciled nothing at all. Those two are the only runs in the whole arm that never touched the tool. In all 6 failures the agent's own choice of what to reconcile never landed on the corrupted field, the same blind spot that let the error in. Nothing checked the checking. In this run, voluntary reconciliation checked what was easy to check, broadly and at a price, and missed the one field, the customer's region, that all six failures turned on.

## Why the Enforced Check Was Free

Every tool result in the enforced arm carries a second copy of the data, so its input should cost more. It did not, because the agent took fewer steps. On the task that reads shipment records it averaged 8.6 tool calls against 17.8 without the checkpoint. Handed the truth next to every answer, this model stopped re-deriving it. Fewer re-reads, fewer cross-checks, a shorter run. Whether another model behaves the same is not measured here. Input tokens per run came out lower than the baseline's, 25,493 against 26,582. The extra bytes on the wire were paid for by the steps the agent no longer needed.

The checkpoint did not switch the agent's own suspicion off, either. One of the eight tasks makes re-reading the job itself, which would make this count meaningless, so I leave its 5 runs out and count 35. In 11 of those 35 enforced runs the agent still went back and re-examined the corrupted record after seeing the contradiction, mostly on the two tasks that write to the database.

## What I Would Do Differently on Monday

**If you run or fund a team shipping agents:**

- Budget the reconciliation as part of the pipeline, not as a prompt or a tool. In this experiment it removed every silent failure at no extra cost per run. The same check as an optional tool cost 1.94x and left 6 of 40.
- Ask for the silent failure rate, the share of runs that finished wrong and reported success, with its baseline. A vendor who reports only "accuracy" is not reporting the number that reaches your customers.
- Treat a doubled bill with more tool calls as a warning sign. Here the extra calls were aimed by the same judgement that missed the error.

**If you build them:**

- Put the check in the code that wraps every tool call, return both answers together, and say in the instructions which one wins. One line was enough for this model.
- Do not rely on the agent to choose what to verify. In the optional arm it verified constantly and still skipped the corrupted field in all six failures.
- Prove that your planted failures can change the answer before you count them. Two of my previous injections could not, and their runs read as survival when nothing had been at risk.
- Log tool calls and tokens per run in both arms. The enforced arm looked more expensive on paper and was not, and only the per-run accounting showed why.

## What This Does Not Show

One model, `deepseek-flash`, which is the successor of the model the previous experiments used. Between the earlier posts and this one the provider retired the old model id, `deepseek-v4-flash`, and now serves `deepseek-flash` under requests for it. None of this post's numbers is a like-for-like replication of the earlier ones. The baseline's 22 of 22 wrong runs claiming success matches the earlier 45 of 45 in shape, and that is all I can say.

A synthetic environment, where the source of truth is exact, instant and free. A real reconciliation is slower, sometimes partial and sometimes wrong itself. What this measures is whether an agent acts on a contradiction it is handed and told to trust. It does not measure how to build the reconciliation.

Eight tasks, three kinds of planted failure, one kind per task, so no claim about which kind of failure is caught more easily. Forty runs per arm, so the intervals are wide: the enforced arm's zero could be anything up to 8.8%, and the baseline's 55% sits between 39.8% and 69.3%.

The enforced arm's cost includes the wrapper on every call, including calls that read data no injection ever touched. A team that checkpoints only writes would pay less and, in this design, would have caught nothing on six of the eight tasks, because every injection here corrupted a read.

The instructions in the enforced arm say the checkpoint is authoritative. I then ran the wrapper without that line, 40 more runs on the same model. Handed the truth with no explanation, the agent still used it on seven of the eight tasks: 4 of 40 silent failures, all on the one task whose job is to report whether two counts agree, where it reported the disagreement it had been shown. And without the line the agent kept re-deriving, so that arm cost 1.58x. The line is what turns the checkpoint from evidence into the answer, and what makes it free.

## FAQ

**What is a deterministic checkpoint in an agent pipeline?** A piece of ordinary code that re-runs a query against the system of record after a tool returns, and gives the agent the real answer next to the tool's answer. Deterministic because no model is involved in producing it. Here it took the form `reconcile(tool, args)`.

**Does giving the agent a reconcile tool help?** It helped, and less than forcing it. Used as an optional tool, silent failures fell from 22 of 40 to 6 of 40, at 1.94x the cost. Forced on every call, none remained, at the cost of no check. All six remaining failures were on tasks where the corrupted field was a customer's region the agent never chose to check.

**Why did the enforced check not cost more?** The agent took fewer steps. Handed the true value next to every tool result, it stopped re-reading and cross-checking on its own. Total input tokens per run fell slightly, 25,493 against 26,582. The larger tool results were paid for by the steps that disappeared.

**Does the agent need to be told the checkpoint is authoritative?** Mostly no, and it matters where. Without the sentence, 4 of 40 runs still failed silently, every one on the task that asks whether two counts agree, and the arm cost 1.58x because the agent kept re-checking. With the sentence, 0 of 40 at 0.86x.

**How do I know these numbers were not tuned after the fact?** The five hypotheses, their thresholds and the stopping rule were committed to the repository before the first run. A test fails if a threshold in the code stops matching the design document. Every number in this post is recomputed from the raw run records by a test in the same repository. The three defects the run exposed are written up with their cost.

## The Transferable Lesson

An agent will use a verification tool if you give it one. It will use it often, at real cost, and aimed by the same judgement that let the error in. The check that works is the one the agent cannot skip and did not have to choose: run it in the code, return both answers, say which one wins. Then take one tool call in your own pipeline where a wrong result would propagate, re-run it against the source of record, and count how often the two disagree. That count is your silent failure rate before anyone has to report it.

## In this series

- [When an AI Agent Says Done: 0% vs 100% False Greens](https://serbyn.io/blog/same-model-0-and-100-where-the-verifier-gap-actually-lives)
- [The API Served a Different Model and My Check Passed](https://serbyn.io/blog/the-api-served-a-different-model-and-my-check-passed)
- [Self-Verification Cost 1.64x and Caught Nothing](https://serbyn.io/blog/self-verification-cost-1-64x-and-caught-nothing)
- [Nine Times the Eval Tried to Lie to Me](https://serbyn.io/blog/nine-times-the-eval-tried-to-lie-to-me)
- [The Arc Since the Six Were Caught](https://serbyn.io/blog/the-arc-since-the-six-were-caught)
- [The Calibration Ledger: 58 Runs, 93% Pass, n Is Small](https://serbyn.io/blog/the-calibration-ledger-58-runs-93-pass-n-is-small)
- [False Greens: Three Structural Observations](https://serbyn.io/blog/false-greens-three-structural-observations)
- [QA Is Only as Honest as Its Coverage](https://serbyn.io/blog/qa-is-only-as-honest-as-its-coverage)
- [One-Sided Contracts Break Agent Pipelines](https://serbyn.io/blog/one-sided-contracts-break-agent-pipelines)
- [Permissive Parsing Is a False-Green Factory](https://serbyn.io/blog/permissive-parsing-is-a-false-green-factory)
- [Six False-Greens in a Self-Auditing Agent Pipeline](https://serbyn.io/blog/six-false-greens-in-a-self-auditing-agent-pipeline)

The experiments, raw records, and checks are public: [github.com/vitamin33/agent-eval-labs](https://github.com/vitamin33/agent-eval-labs).

*Originally published at [serbyn.io](https://serbyn.io/blog/enforced-checkpoint-0-of-40-silent-failures-vs-22-of-40).*
