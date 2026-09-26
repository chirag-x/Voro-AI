import subprocess
out = subprocess.check_output(['powershell', '-NoProfile', '-Command', 'Get-WmiObject -Namespace root\\\\wmi -Class WmiMonitorID | ForEach-Object { ($_.UserFriendlyName | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) -join \'\' }'], text=True)
print(out.strip().split('\n'))
