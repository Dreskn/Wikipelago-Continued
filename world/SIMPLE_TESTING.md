# Simple Testing

Run these scripts from the `world/` directory (repo root sibling of `bridge/`, `web/`, and `yaml/`).

## 1. Quick release check

This rebuilds the APWorld and runs the smoke test.

```powershell
.\release_check.ps1
```

If this passes, the build is probably fine.

## 2. Fast random settings check

This makes a bunch of random Wikipelago YAMLs and checks that the settings are internally sane.

```powershell
.\fuzz_test.ps1 -Runs 25
```

If this passes, your options are behaving reasonably.

## 3. Real generator fuzzing

If you want to test actual Archipelago generation many times, use:

```powershell
.\real_fuzz_test.ps1 -Runs 25
```

If it cannot find your Archipelago folder automatically, use:

```powershell
.\real_fuzz_test.ps1 -Runs 25 -ArchipelagoRoot "PATH_TO_ARCHIPELAGO"
```

## 4. What to do before release

Run these in order:

```powershell
.\release_check.ps1
.\fuzz_test.ps1 -Runs 25
```

If you want a stronger check:

```powershell
.\real_fuzz_test.ps1 -Runs 100
```

GitHub CI also generates three fixed seeds (EN default, FR, PL with branches) against Archipelago 0.6.7 via `world/ci_generate.py`. To run that locally after building the apworld:

```powershell
python .\ci_generate.py --ap-root "PATH_TO_ARCHIPELAGO_SOURCE" --apworld .\APWorld\wikipelago.apworld
```

## 5. If something fails

- `smoke_test.ps1` failure:
  there is probably a broken file, encoding problem, or old regression

- `fuzz_test.ps1` local failure:
  an option combination is mathematically invalid

- `real_fuzz_test.ps1` generator failure:
  check the logs in `fuzz_output\logs`
