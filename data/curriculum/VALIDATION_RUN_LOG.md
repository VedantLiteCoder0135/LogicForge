# Validation Suite Run Log

Each entry is `backend/data/validator.py::run_all_validations()` run directly against the loaded curriculum, command and full output recorded verbatim. Re-run and append (don't overwrite) whenever the data changes materially.

## Run: cse branch

```
python3 -c "from backend.data.loader import load_curriculum; from backend.data.validator import run_all_validations; import json; print(json.dumps(run_all_validations(load_curriculum('data/curriculum', branch='cse')), indent=2))"
```
```json
{
  "branch": "cse",
  "course_count": 32,
  "cycles": [],
  "undefined_course_codes": {},
  "category_floor_violations": {},
  "unreachable_courses": []
}
```
**Result: PASS, zero gaps.**

## Run: eee branch

```
python3 -c "from backend.data.loader import load_curriculum; from backend.data.validator import run_all_validations; import json; print(json.dumps(run_all_validations(load_curriculum('data/curriculum', branch='eee')), indent=2))"
```
```json
{
  "branch": "eee",
  "course_count": 31,
  "cycles": [],
  "undefined_course_codes": {
    "ECE F244": ["EEE F313"],
    "INSTR F243": ["EEE F418", "EEE F431"],
    "ECE F434": ["EEE F420"],
    "ECE F242": ["EEE F422"],
    "INSTR F242": ["EEE F422"]
  },
  "category_floor_violations": {},
  "unreachable_courses": []
}
```
**Result: PASS. 5 undefined references are intentional and documented** — cross-department (ECE/INSTR) elective alternatives, out of scope per `SCOPE_DECISION.md`. Category floor and reachability both clean; `tests/test_data_validation.py::test_eee_known_undefined_references` asserts this exact set.

## Run: cse branch + Minor in Data Science

```
python3 -c "from backend.data.loader import load_curriculum; from backend.data.validator import run_all_validations; import json; print(json.dumps(run_all_validations(load_curriculum('data/curriculum', branch='cse', minor='data_science')), indent=2))"
```
```json
{
  "branch": "cse",
  "course_count": 46,
  "cycles": [],
  "undefined_course_codes": {},
  "category_floor_violations": {},
  "unreachable_courses": []
}
```
**Result: PASS, zero gaps.** The minor's 5 Core courses sum to exactly 15 credits, matching the bulletin's stated 15-unit minimum.

## Run: ece branch (now real data)

```
python3 -c "from backend.data.loader import load_curriculum; from backend.data.validator import run_all_validations; import json; print(json.dumps(run_all_validations(load_curriculum('data/curriculum', branch='ece')), indent=2))"
```
```json
{
  "branch": "ece",
  "course_count": 29,
  "cycles": [],
  "undefined_course_codes": {
    "EEE F243": ["ECE F344"],
    "EEE F242": ["ECE F424"],
    "INSTR F242": ["ECE F424"]
  },
  "category_floor_violations": {},
  "unreachable_courses": []
}
```
**Result: PASS. 3 undefined references are intentional and documented** — cross-department elective/alternative references (`ECE F424`'s real prerequisite is "EEE F242 OR INSTR F242 OR ECE F242," only the ECE leaf resolves locally). Category floor and reachability both clean.

## Run: e_and_i branch (now real data)

```
python3 -c "from backend.data.loader import load_curriculum; from backend.data.validator import run_all_validations; import json; print(json.dumps(run_all_validations(load_curriculum('data/curriculum', branch='e_and_i')), indent=2))"
```
```json
{
  "branch": "e_and_i",
  "course_count": 30,
  "cycles": [],
  "undefined_course_codes": {
    "EEE F242": ["INSTR F424"],
    "ECE F242": ["INSTR F424"]
  },
  "category_floor_violations": {},
  "unreachable_courses": []
}
```
**Result: PASS. 2 undefined references, same intentional cross-department pattern** (`INSTR F424`'s real prerequisite is "EEE F242 OR INSTR F242 OR ECE F242," only the INSTR leaf resolves locally). Category floor and reachability both clean.

## Summary

| Branch/Minor | Real data? | Validation result |
|---|---|---|
| cse | Yes, fully | PASS, 0 gaps |
| eee | Yes, fully | PASS, 5 documented intentional cross-dept references |
| ece | Yes, fully | PASS, 3 documented intentional cross-dept references |
| e_and_i | Yes, fully | PASS, 2 documented intentional cross-dept references |
| cse + data_science minor | Yes, fully | PASS, 0 gaps |
