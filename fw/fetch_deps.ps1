# Fetches the pinned ST and Arm sources into fw/third_party/ (gitignored).
# Licences: BSD-3-Clause (HAL driver), Apache-2.0 (CMSIS core, CMSIS device, CMSIS-DSP); see each
# repository's LICENSE file. CMSIS-DSP (owner's go, 2026-11-18): the yardstick for dsp_fft.
# Run from anywhere: powershell -ExecutionPolicy Bypass -File fw/fetch_deps.ps1

$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot "third_party"
New-Item -ItemType Directory -Force $root | Out-Null

# Repository, commit. These are the versions inside STM32Cube_FW_H7 V1.12.1. Bump deliberately,
# one at a time, and rebuild and re-test on the board.
$pins = @(
    @("cmsis_core",           "b7487de1303e2eb77c402432e368691e9dcfb5f0", "STMicroelectronics/cmsis_core"), # v5.9.0_20250520
    @("cmsis_device_h7",      "e8d40ae6e2fa06afe5b46d24756f141b363342a7", "STMicroelectronics/cmsis_device_h7"), # v1.10.6
    @("stm32h7xx_hal_driver", "57ed86b4c358e2333a71fd895b17f1ccdb68739e", "STMicroelectronics/stm32h7xx_hal_driver"), # v1.11.5
    @("cmsis_dsp",            "d5717e454fec0337bef114a21f1d2d01d74f2701", "ARM-software/CMSIS-DSP") # v1.16.2
)

foreach ($pin in $pins) {
    $name = $pin[0]
    $commit = $pin[1]
    $repo = $pin[2]
    $dir = Join-Path $root $name
    if (-not (Test-Path (Join-Path $dir ".git"))) {
        git init --quiet $dir
        git -C $dir remote add origin "https://github.com/$repo.git"
    }
    $have = (git -C $dir rev-parse --verify --quiet HEAD) 2>$null
    if ($have -ne $commit) {
        Write-Host "Fetching $name at $commit"
        git -C $dir fetch --quiet --depth 1 origin $commit
        git -C $dir checkout --quiet --detach FETCH_HEAD
    }
    Write-Host ("{0,-22} {1}" -f $name, (git -C $dir rev-parse HEAD))
}
