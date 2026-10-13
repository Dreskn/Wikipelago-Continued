# Simple Testing

Run these from the repo root (the scripts find their own folders, so they also work from elsewhere).

## 1. Quick release check

This rebuilds the APWorld and runs the smoke test.

```powershell
./world/release_check.ps1
```

If this passes, the build is probably fine.

## 2. Fast random settings check (no Archipelago needed)

This makes random Wikipelago YAMLs across the full range of every option and checks each one against the world's rules in two ways: a PowerShell model of the item math and error conditions, and the world's own Python code run with small stand-ins for Archipelago (needs Python 3.10+; without it only the model runs). It always adds fixed cases too: the YAML template, the option defaults and a Realm Master seed must be accepted, and known-bad configs must be rejected with the right error.

```powershell
./world/fuzz_test.ps1 -Runs 25
```

Every case is listed as accepted or rejected, with the reason. The script fails when the model, the world code and the fixed expectations disagree, or when the world code crashes or leaves a location unreachable. Rejections caused by a too-small article pool are shown as "pool-limited"; the model does not predict those.

It does not run Archipelago's generator (item placement, accessibility, output). That is the next check. To repeat a run, pass the `-Seed` it prints.

## 3. Real generator fuzzing (needs Archipelago)

This runs Archipelago's real generator once per case and checks that accepted settings produce a seed and rejected ones fail with the expected error. It needs either:

- an Archipelago **0.6.7+** source checkout with its requirements installed (Python 3.11 to 3.13), for example:

  ```powershell
  git clone --depth 1 --branch 0.6.7 https://github.com/ArchipelagoMW/Archipelago ../Archipelago
  python ../Archipelago/ModuleUpdate.py --yes
  ```

- or an installed Archipelago (the Windows installer's folder with `ArchipelagoGenerate.exe`).

```powershell
./world/real_fuzz_test.ps1 -Runs 25 -ArchipelagoRoot "PATH_TO_ARCHIPELAGO"
```

Without `-ArchipelagoRoot` it uses the `ARCHIPELAGO_ROOT` environment variable, then looks for an `Archipelago` folder next to this repo, `C:\ProgramData\Archipelago` and a few other usual places. For a source checkout whose requirements live in a virtual environment outside the checkout, add `-PythonCommand "PATH_TO_VENV\Scripts\python.exe"`. Add `-NoPause` when running it from a script.

The script builds `world/APWorld/wikipelago.apworld` and copies it to `custom_worlds\wikipelago.apworld` inside that Archipelago for the duration of the run. Any wikipelago apworld already there is renamed to `*.real_fuzz_backup` first and put back at the end, so an installed Archipelago is left as it was. Each run is reported as PASS or FAIL, and the script exits with an error if any run fails.

## 4. What to do before release

Run these in order:

```powershell
./world/release_check.ps1
./world/fuzz_test.ps1 -Runs 25
```

If you want a stronger check:

```powershell
./world/real_fuzz_test.ps1 -Runs 100 -ArchipelagoRoot "PATH_TO_ARCHIPELAGO"
```

GitHub CI (`.github/workflows/ci.yml`) runs the smoke test and generates six fixed seeds against Archipelago 0.6.7 via `world/ci_generate.py`: EN defaults, FR, PL with branches, EN Topic Realms, FR Realm Master with Topic Realms, and EN Realm Master with plain branches. To run the same cases locally after building the apworld, use the Python that has Archipelago's requirements (the script copies the apworld into the checkout's `worlds` folder):

```powershell
python world/ci_generate.py --ap-root "PATH_TO_ARCHIPELAGO_SOURCE" --apworld world/APWorld/wikipelago.apworld
```

## 5. If something fails

- `smoke_test.ps1` failure:
  there is probably a broken file, encoding problem, or old regression

- `fuzz_test.ps1` failure:
  read the `[FAIL]` lines. "model expects ... but the world ..." means the world's rules changed (update the model in `fuzz_test.ps1` if that was intended) or there is a world bug. "the world crashed" is a world bug. An expectation failure means the template, the defaults or a known-bad config no longer behaves as it should. The YAMLs and `results.json` are in `world\fuzz_output`

- `real_fuzz_test.ps1` failure:
  check the Archipelago log for that case in `world\fuzz_output\logs`
