# Installer Icon Assets

Place `VeinServerManager.ico` in this directory to brand both the packaged
`VeinManager.exe` and the final installer.

The repository currently includes this icon. Build scripts automatically look for:

```
Installer/assets/VeinServerManager.ico
```

If the file is present, PyInstaller embeds it into `VeinManager.exe` and the
Inno Setup script uses it as the installer icon. Without this file, builds fall
back to the default PyInstaller/Inno Setup icons.
