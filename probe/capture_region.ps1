param([int]$X = 0, [int]$Y = 0, [int]$W = 400, [int]$H = 80, [string]$Out = "$env:TEMP\region.png")

Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap($W, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($X, $Y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $Out ($W x $H at $X,$Y)"
