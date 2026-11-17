# Flashes both cores of the Nucleo-H755ZI-Q over its ST-LINK.
#   powershell -ExecutionPolicy Bypass -File tools/flash.ps1
# It reads the device identity first and stops unless it is a dual-core H745/H755 (ID 0x450),
# so it cannot write these images to another board (the Psyight node's F767, for one).
# It never touches option bytes.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cm7 = Join-Path $root "build/fw/fw/dsp_cm7.elf"
$cm4 = Join-Path $root "build/fw/fw/dsp_cm4.elf"
foreach ($image in @($cm7, $cm4)) {
    if (-not (Test-Path $image)) {
        throw "Missing $image. Build first: cmake --preset fw, then cmake --build --preset fw"
    }
}

$cli = Get-ChildItem "C:/ST/STM32CubeIDE_*/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_*/tools/bin/STM32_Programmer_CLI.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $cli) {
    $cli = Get-Command STM32_Programmer_CLI -ErrorAction SilentlyContinue
    if (-not $cli) { throw "STM32_Programmer_CLI not found (it ships inside STM32CubeIDE)." }
    $cliPath = $cli.Source
} else {
    $cliPath = $cli.FullName
}

Write-Host "Reading the device identity..."
$probe = & $cliPath -c port=SWD 2>&1 | Out-String
if ($probe -notmatch "Device ID\s*:\s*0x450") {
    Write-Host $probe
    throw "No dual-core STM32H745/H755 (device ID 0x450) on the ST-LINK. Nothing was written."
}

# The Cortex-M4 image first: the M7 image is the one that reports whether the M4 parked.
& $cliPath -c port=SWD -w $cm4 -v
if ($LASTEXITCODE -ne 0) { throw "Writing the Cortex-M4 image failed." }
& $cliPath -c port=SWD -w $cm7 -v -rst
if ($LASTEXITCODE -ne 0) { throw "Writing the Cortex-M7 image failed." }
Write-Host "Both cores flashed. Console: python tools/console.py --port COMx"
