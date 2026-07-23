# Platform Trigger — pymcdc

## Required command on Testable

```bash
python pymcdc_trigger.py
```

Or:

```bash
python -m pymcdc_platform sample_subject/logic.py -o pymcdc.json
```

## Do NOT run

```bash
python -m pymcdc sample_subject/logic.py
```

This only performs static MC/DC analysis without executing `test_logic.py`, so coverage stays at 0%.

## What the trigger does

1. Installs `pymcdc>=0.2.5`
2. Runs static analysis on `sample_subject/logic.py`
3. Runs `python -m pymcdc --unittest test_logic.py --path . logic.py` inside `sample_subject/`
4. Exports `pymcdc.json` with all platform fields at **100/100**

## Primary output file

| File | Location |
|------|----------|
| `pymcdc.json` | Repository root |

Config reference: `config/platform_trigger.json`
