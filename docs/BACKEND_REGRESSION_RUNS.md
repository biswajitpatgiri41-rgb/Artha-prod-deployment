# Backend regression suite execution log

Command for every run:

```bash
python -m pytest -q --disable-warnings
```

Environment: Python 3.12 virtual environment, project installed with `.[dev,econometrics]`; tests run from repository root. These are ten separate complete suite invocations, not one invocation counted ten times.

| Run | Result | Duration |
|---:|---|---:|
| 1 | 74 passed, 113 warnings | 3.79 s |
| 2 | 74 passed, 113 warnings | 3.57 s |
| 3 | 74 passed, 113 warnings | 3.58 s |
| 4 | 74 passed, 113 warnings | 3.40 s |
| 5 | 74 passed, 113 warnings | 3.62 s |
| 6 | 74 passed, 113 warnings | 3.84 s |
| 7 | 74 passed, 113 warnings | 3.78 s |
| 8 | 74 passed, 113 warnings | 3.62 s |
| 9 | 74 passed, 113 warnings | 3.54 s |
| 10 | 74 passed, 113 warnings | 3.53 s |

All ten suite invocations passed. The warnings are primarily Pydantic V2 deprecation warnings. These runs do not validate absent multi-agent graph execution, production authorization, real external-provider ingestion, durable Vercel storage, or real-time-vintage model evaluation.
