$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($payload.action -eq 'voices') {
        $names = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Name })
        ConvertTo-Json -InputObject $names -Compress
    } elseif ($payload.action -eq 'speak') {
        if ($payload.voice) { $synth.SelectVoice([string]$payload.voice) }
        $synth.Rate = [int]$payload.rate
        $synth.Volume = [int]$payload.volume
        $synth.SetOutputToWaveFile([string]$payload.path)
        $synth.Speak([string]$payload.text)
        $synth.SetOutputToNull()
    } else { throw 'Unknown speech action' }
} finally { $synth.Dispose() }
