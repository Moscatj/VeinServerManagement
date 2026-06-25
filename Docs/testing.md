# Testing

The project now has a dependency-free unit test suite under `Tests/`.

Run it from the repository root:

```bat
python -m unittest discover -s Tests
```

Or use the Windows diagnostic wrapper:

```bat
Scripts\TestSuite.bat
```

Coverage reporting uses `coverage.py`, which is listed in
`requirements-dev.txt` but is not required for normal runtime use:

```bat
py -3 -m pip install -r requirements-dev.txt
Scripts\RunCoverage.bat
```

The suite is intentionally focused on code that can be exercised without
starting the Vein server or writing to the game installation. New tests should
use temporary directories inside the repository root and must not write to the
external `Vein/` game folder.

`Scripts/TestSuite.bat` runs these unit tests before its existing diagnostic
checks.
