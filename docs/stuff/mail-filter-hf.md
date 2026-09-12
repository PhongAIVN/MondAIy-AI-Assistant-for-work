## XLM-R mail filter

The mail pipeline uses three layers:

1. The existing deterministic rules handle obvious keep/drop decisions.
2. Only `llm_judge` candidates are sent to `DungND1107/modaiy_vin` through the
   Hugging Face inference API when `HF_MAIL_FILTER_ENABLED=true`.
3. A mapped label above `HF_MAIL_FILTER_MIN_CONFIDENCE` becomes a keep/drop
   decision. Disabled, timed-out, malformed, low-confidence, or unknown-label
   responses abstain and preserve the existing LLM extraction route.

Configure the real token only in the runtime secret store:

```dotenv
HF_MAIL_FILTER_ENABLED=true
HF_MAIL_FILTER_TOKEN=<runtime-secret>
HF_MAIL_FILTER_MODEL=DungND1107/modaiy_vin
HF_MAIL_FILTER_MIN_CONFIDENCE=0.80
HF_MAIL_FILTER_KEEP_LABELS=LABEL_1,keep,relevant,actionable,important,positive
HF_MAIL_FILTER_DROP_LABELS=LABEL_0,drop,irrelevant,spam,noise,negative
```

If the trained label meaning is reversed, change the two label lists in the
runtime environment. The service never logs or persists the token.
