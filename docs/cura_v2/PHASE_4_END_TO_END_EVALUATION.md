# Phase 4 end-to-end evaluation

Questions were sent to `POST /api/v1/chat` with the mock health provider and the live OpenRouter models. This is synthetic fixture data (`demo-user-001`), not a production member. The landing screen and health screens were not changed.

## The 180-token cutoff

The previous two answers stopped at 180 tokens because the evaluation script set `max_tokens` to 180. CURA’s own limit is `llm_max_output_tokens` 1200, plus the reasoning cap when the provider counts hidden reasoning inside that budget. That production limit was not changed.

One pipeline call still logged `llm_truncated` for `openai/gpt-5.6-luna` and fell back. The user-facing text did not contain raw JSON.

## What ran

Eighteen turns in one conversation, about 174 seconds in total. Jev was off, so routing used the deterministic planner. The safety classifier timed out on several turns (`ReadTimeout`) and the request continued.

| Turn | Seconds | Words | Follow-ups | Model | Sources |
| --- | --- | --- | --- | --- | --- |
| What is HDL? | 8.34 | 144 | 4 | gpt-5.6-luna | general |
| What is my HDL level? | 7.40 | 66 | 2 | gpt-5.6-luna | supershyft |
| What does my result mean? | 18.85 | 234 | 4 | gpt-5-mini | supershyft |
| How is it connected to LDL? | 8.85 | 87 | 4 | gpt-5.6-luna | supershyft |
| What can influence HDL? | 7.24 | 171 | 2 | gpt-5.6-luna | general |
| What is ferritin? | 6.38 | 78 | 4 | gpt-5.6-luna | general |
| What does my ferritin result mean? | 2.66 | 36 | 4 | none | supershyft |
| How is ferritin connected to haemoglobin? | 7.14 | 105 | 2 | gpt-5.6-luna | supershyft |
| Explain that more simply. | 7.82 | 106 | 2 | gpt-5.6-luna | supershyft |
| Can iron stores be low if haemoglobin is normal? | 8.16 | 100 | 3 | gpt-5.6-luna | supershyft |
| What is Bio-AI? | 6.57 | 120 | 4 | gpt-5.6-luna | general |
| What does my cardiac health risk mean? | 1.82 | 86 | 3 | none | supershyft |
| Does this prediction mean I have heart disease? | 3.33 | 86 | 2 | none | supershyft |
| What does my cholesterol report tell me? | 12.66 | 168 | 4 | gpt-5-mini | supershyft |
| What about my vitamin D? | 7.48 | 69 | 3 | gpt-5.6-luna | supershyft |
| What is diabetes? | 32.44 | 258 | 4 | gpt-5-mini | general |
| Has my HbA1c changed? | 15.39 | 61 | 4 | gpt-5-mini | supershyft |
| What should I eat based on my blood report? | 10.38 | 135 | 4 | gpt-5.6-luna | supershyft |

Median time for these 18 was about 8 seconds. The slowest was “What is diabetes?” at 32 seconds. No separate cache-token or cost field was returned on the chat response. The earlier direct calls are not counted as CURA evaluations.

## Representative answers

Synthetic fixture values only.

- “What is HDL?” explained HDL as a carrier that moves cholesterol away from blood vessels. Follow-ups stayed on HDL: a healthy level, food and exercise, why it matters for the heart.
- “What is my HDL level?” said the result was inside the report range and named 41.0 mg/dL against 40–60. Two follow-ups were generic (“What stands out most in my results?”).
- “What does my result mean?” left HDL and listed liver, kidneys, fats, vitamins, and fasting sugar. That is too wide for the question.
- “What is ferritin?” was a clear general explanation. The fixture has no ferritin row, and the next turn said so instead of inventing a value.
- “Explain that more simply.” kept ferritin and haemoglobin and used a store-cupboard comparison. A follow-up then jumped to a Dyslipidemia score.
- “What does my cardiac health risk mean?” and “Does this prediction mean I have heart disease?” did not answer the prediction. Both returned a blood-result list (vitamin D, LDL, B12) with no model call.
- “What is diabetes?” stayed general after the personal turns. That topic switch worked. It was long, 258 words.
- “What about my vitamin D?” switched to vitamin D and gave the fixture result against its range.
- “Has my HbA1c changed?” compared the current and previous fixture results and said the change was small and still inside the range.

## Follow-ups

The answer model’s questions were kept. Counts were 2, 3, or 4, not always four. The prompt line that demanded exactly four questions now says up to four, and fewer when another question would repeat the answer. `test_house_prompt.py` checks that wording.

Useful follow-ups appeared after the HDL and ferritin definitions. Weaker ones were “What stands out most in my results?”, “Is everything in my report in the healthy range?”, and a jump from iron to a Bio-AI score.

## Prompt caching and models

Fast turns used `openai/gpt-5.6-luna`. Longer turns used `openai/gpt-5-mini`. No provider cached-token count was available on the chat response, so caching is not claimed. Models were not changed.

## Targeted change

Only the follow-up instruction changed, from “exactly 4” to “up to 4”. No other pipeline or screen change.

## Not completed

One hundred user-facing answers were not generated. Eighteen completed answers are the live set. The other conversations in the brief (full Bio-AI attribution, activity and blood sugar) were not each run. No production member was selected. Per-stage timers were not added. The full backend suite finished in 17 minutes 18 seconds: 34 failed, 2122 passed, 4 skipped. That is three more failures than the previous 31. They were not reclassified in this note. The frontend suite was not re-run after the one prompt sentence.

## Weaknesses

- A short follow-up (“What does my result mean?”) pulled in unrelated body systems.
- Cardiac-risk questions fell through to a blood-report list when the model was not called.
- The safety classifier often timed out before the answer.
- Some follow-ups leave the topic the user just asked about.
- “What is diabetes?” was much longer than a simple definition needs.
