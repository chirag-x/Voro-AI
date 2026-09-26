Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID | ForEach-Object { ($_.UserFriendlyName | Where-Object { $_ -ne 0 } | ForEach-Object {[char]$_}) -join '' }
