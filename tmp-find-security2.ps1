Get-ChildItem -Path C:\ -Filter security.json -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 FullName
