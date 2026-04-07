Get-ChildItem -Path 'C:\Users' -Directory | ForEach-Object {
  $p = Join-Path $_.FullName 'shared-memory\security.json'
  Get-ChildItem -Path $p -ErrorAction SilentlyContinue
}
