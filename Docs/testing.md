# Testing

The project now has a dependency-free unit test suite under `Tests/`.

Run it from the repository root:

```bat
python -m unittest discover -s Tests
```

The suite is intentionally focused on code that can be exercised without
starting the Vein server or writing to the game installation. New tests should
use temporary directories inside the repository root and must not write to the
external `Vein/` game folder.

`Scripts/TestSuite.bat` runs these unit tests before its existing diagnostic
checks.
