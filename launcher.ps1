Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$ErrorActionPreference='Stop'
$rootPath=$PSScriptRoot
$script:serverProcess=$null
$script:serviceUrl=$null
$logFolder=Join-Path $rootPath 'launcher-logs'
New-Item -ItemType Directory -Force -Path $logFolder | Out-Null
$script:readyPath=Join-Path $logFolder (([guid]::NewGuid().ToString())+'.json')
$outPath=Join-Path $logFolder 'server.log'
$errPath=Join-Path $logFolder 'error.log'
$window=New-Object Windows.Forms.Form
$window.Text='Video2Blockout Launcher';$window.Size=New-Object Drawing.Size(600,350)
$window.StartPosition='CenterScreen'
$title=New-Object Windows.Forms.Label
$title.Text='Video2Blockout | Video to depth and blockout';$title.Location=New-Object Drawing.Point(24,20);$title.AutoSize=$true
$title.Font=New-Object Drawing.Font('Segoe UI',14)
$status=New-Object Windows.Forms.Label
$status.Text='Ready. Click Start to launch the local tool.';$status.Location=New-Object Drawing.Point(24,70);$status.Size=New-Object Drawing.Size(545,90)
function Button($text,$x){$b=New-Object Windows.Forms.Button;$b.Text=$text;$b.Location=New-Object Drawing.Point($x,170);$b.Size=New-Object Drawing.Size(125,40);$window.Controls.Add($b);return $b}
$start=Button 'Start' 24;$open=Button 'Open tool' 160;$stop=Button 'Stop' 296;$logs=Button 'View logs' 432
$open.Enabled=$false;$stop.Enabled=$false
$hint=New-Object Windows.Forms.Label
$hint.Text='Keep this launcher open. Videos are processed locally. First use may download model weights.'
$hint.Location=New-Object Drawing.Point(24,230);$hint.Size=New-Object Drawing.Size(535,50)
$window.Controls.AddRange(@($title,$status,$hint))
$timer=New-Object Windows.Forms.Timer;$timer.Interval=500
$start.Add_Click({
 try {
  $pythonPath=Join-Path $rootPath 'portable-python\python.exe'
  if (!(Test-Path -LiteralPath $pythonPath)) {throw 'Portable Python is missing. Extract the complete package.'}
  if (!(Test-Path -LiteralPath (Join-Path $rootPath 'runtime-packages\torch'))) {throw 'Model dependencies are missing. Extract the complete portable package.'}
  $script:serviceUrl=$null
  $script:readyPath=Join-Path $logFolder (([guid]::NewGuid().ToString())+'.json')
  $arguments='-u "'+(Join-Path $rootPath 'app.py')+'" --port 0 --ready-file "'+$script:readyPath+'"'
  $script:serverProcess=Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $rootPath -WindowStyle Hidden -RedirectStandardOutput $outPath -RedirectStandardError $errPath -PassThru
  $start.Enabled=$false;$stop.Enabled=$true;$status.Text='Starting local service...';$timer.Start()
 } catch {$status.Text=$_.Exception.Message}
})
$timer.Add_Tick({
 if (!$script:serverProcess) {return}
 $script:serverProcess.Refresh()
 if ($script:serverProcess.HasExited) {
  $status.Text='Service stopped. '+(Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue)
  $start.Enabled=$true;$open.Enabled=$false;$stop.Enabled=$false;$timer.Stop();return
 }
 if (!$script:serviceUrl -and (Test-Path -LiteralPath $script:readyPath)) {
  try {
   $info=Get-Content -LiteralPath $script:readyPath -Raw | ConvertFrom-Json
   if ($info.pid -ne $script:serverProcess.Id) {return}
   $request=[Net.WebRequest]::Create($info.url);$request.Proxy=$null;$request.Timeout=2000
   $response=$request.GetResponse();$response.Close()
   $script:serviceUrl=$info.url;$status.Text='Running: '+$script:serviceUrl
   $open.Enabled=$true;Start-Process $script:serviceUrl
  } catch {$status.Text='Service started; waiting for local connection. '+$_.Exception.Message}
 }
})
function StopOwnedServer {
 $timer.Stop()
 if ($script:serverProcess) { $script:serverProcess.Refresh();if (!$script:serverProcess.HasExited) {$script:serverProcess.Kill()};$script:serverProcess=$null }
 $script:serviceUrl=$null;$open.Enabled=$false;$stop.Enabled=$false;$start.Enabled=$true;$status.Text='Stopped. Click Start to run again.'
}
$stop.Add_Click({StopOwnedServer})
$open.Add_Click({if ($script:serviceUrl) {Start-Process $script:serviceUrl}})
$logs.Add_Click({Start-Process explorer.exe -ArgumentList ('"'+$logFolder+'"')})
$window.Add_FormClosing({StopOwnedServer})
[void]$window.ShowDialog()
