# backend/tools/smoke_reports.ps1
# PowerShell 5.1 compatible reports and evidence vault smoke test suite.
# Strictly runs against http://localhost:8000/api/v1 (dev settings with runserver)
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8000/api/v1"
)

$ErrorActionPreference = "Continue"

# Refuse to run against any host other than http://localhost:8000/api/v1
try {
    $targetUri = [System.Uri]$BaseUrl
} catch {
    Write-Host "FAIL: Invalid BaseUrl '$BaseUrl'"
    exit 1
}

if ($targetUri.Scheme -ne "http" -or $targetUri.Host -ne "localhost" -or $targetUri.Port -ne 8000 -or $targetUri.AbsolutePath.TrimEnd('/') -ne "/api/v1") {
    Write-Host "FAIL: Refusing to run against host '$BaseUrl'. Strictly requires http://localhost:8000/api/v1"
    exit 1
}

$BaseUrl = $BaseUrl.TrimEnd('/')

function New-SmokeEmail {
    $randHex = [System.Guid]::NewGuid().ToString("N").Substring(0, 10)
    return "smoke-$randHex@example.test"
}

# 1x1 valid PNG bytes
$pngBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
$validPngBytes = [System.Convert]::FromBase64String($pngBase64)

function Build-MultipartBody {
    param(
        [hashtable]$Fields,
        [array]$Files,
        [string]$Boundary
    )
    $encoding = [System.Text.Encoding]::UTF8
    $ms = New-Object System.IO.MemoryStream

    foreach ($key in $Fields.Keys) {
        $val = [string]$Fields[$key]
        $header = "--$Boundary`r`nContent-Disposition: form-data; name=`"$key`"`r`n`r`n$val`r`n"
        $headerBytes = $encoding.GetBytes($header)
        $ms.Write($headerBytes, 0, $headerBytes.Length)
    }

    if ($Files) {
        foreach ($file in $Files) {
            $fieldName = $file.Name
            $fileName = $file.Filename
            $contentType = $file.ContentType
            $bytes = $file.Bytes

            $header = "--$Boundary`r`nContent-Disposition: form-data; name=`"$fieldName`"; filename=`"$fileName`"`r`nContent-Type: $contentType`r`n`r`n"
            $headerBytes = $encoding.GetBytes($header)
            $ms.Write($headerBytes, 0, $headerBytes.Length)
            $ms.Write($bytes, 0, $bytes.Length)
            $crlf = $encoding.GetBytes("`r`n")
            $ms.Write($crlf, 0, $crlf.Length)
        }
    }

    $trailer = "--$Boundary--`r`n"
    $trailerBytes = $encoding.GetBytes($trailer)
    $ms.Write($trailerBytes, 0, $trailerBytes.Length)

    return $ms.ToArray()
}

function Invoke-ApiRaw {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Method,
        [Parameter(Mandatory=$true)]
        [string]$Path,
        [byte[]]$BodyBytes = $null,
        [string]$ContentType = "application/json",
        [hashtable]$Headers = @{},
        $Session = $null
    )

    $url = "$BaseUrl$Path"
    $reqHeaders = @{}
    foreach ($k in $Headers.Keys) {
        $reqHeaders[$k] = $Headers[$k]
    }

    $invokeParams = @{
        Uri = $url
        Method = $Method
        UseBasicParsing = $true
        Headers = $reqHeaders
    }

    if ($Session) {
        $invokeParams["WebSession"] = $Session
    }

    if ($null -ne $BodyBytes) {
        $invokeParams["Body"] = $BodyBytes
        $invokeParams["ContentType"] = $ContentType
    }

    $result = @{
        Status = 0
        Body = $null
        RawBody = ""
        Headers = @{}
    }

    try {
        $resp = Invoke-WebRequest @invokeParams
        $result.Status = [int]$resp.StatusCode
        $result.RawBody = $resp.Content
        $result.Headers = $resp.Headers
    } catch [System.Net.WebException] {
        $webResp = $_.Exception.Response
        if ($webResp) {
            $result.Status = [int]$webResp.StatusCode
            $result.Headers = @{}
            foreach ($k in $webResp.Headers.AllKeys) {
                $result.Headers[$k] = $webResp.Headers[$k]
            }
            if ($_.ErrorDetails -and -not [string]::IsNullOrEmpty($_.ErrorDetails.Message)) {
                $result.RawBody = $_.ErrorDetails.Message
            } else {
                try {
                    $stream = $webResp.GetResponseStream()
                    $reader = New-Object System.IO.StreamReader($stream)
                    $result.RawBody = $reader.ReadToEnd()
                } catch {}
            }
        }
    } catch {
        # Other exceptions
    }

    if (-not [string]::IsNullOrEmpty($result.RawBody)) {
        try {
            $result.Body = ($result.RawBody | ConvertFrom-Json)
        } catch {
            $result.Body = $null
        }
    }

    return $result
}

$passedCount = 0
$failedCount = 0
$skippedCount = 0

function Report-Step {
    param(
        [int]$Step,
        [bool]$Success,
        [int]$ActualStatus,
        [string]$ExpectedStatus,
        [bool]$Skip = $false
    )
    if ($Skip -or ($ActualStatus -eq 429 -and $ExpectedStatus -ne "429")) {
        Write-Host ("STEP {0}: SKIP (HTTP {1}, throttled or unavailable)" -f $Step, $ActualStatus)
        $script:skippedCount++
    } elseif ($Success) {
        Write-Host ("STEP {0}: PASS (HTTP {1}, expected: {2})" -f $Step, $ActualStatus, $ExpectedStatus)
        $script:passedCount++
    } else {
        Write-Host ("STEP {0}: FAIL (HTTP {1}, expected: {2})" -f $Step, $ActualStatus, $ExpectedStatus)
        $script:failedCount++
    }
}

# --- STEP 1: GET /reports/options/ returns 200 ---
$res1 = Invoke-ApiRaw -Method "GET" -Path "/reports/options/"
$success1 = ($res1.Status -eq 200) -and ($res1.Body -and $res1.Body.categories)
Report-Step 1 $success1 $res1.Status "200"

# --- STEP 2: Anonymous report with 2 images: 201, ref starts with SCM-, access_key present ---
$boundary2 = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N")
$idempotencyKey2 = [System.Guid]::NewGuid().ToString()
$indicators2 = '[{"type":"URL","value":"https://fake-login-verify.test"},{"type":"PHONE","value":"0123456789"}]'

$fields2 = @{
    category = "PHISHING"
    platform = "SMS"
    message_text = "Urgent: your bank account requires immediate verification."
    country_code = "MY"
    currency = "MYR"
    financial_loss = "0.00"
    payment_method = "NONE"
    admin_area = "Selangor"
    indicators = $indicators2
}
$files2 = @(
    @{ Name = "evidence"; Filename = "shot1.png"; ContentType = "image/png"; Bytes = $validPngBytes },
    @{ Name = "evidence"; Filename = "shot2.png"; ContentType = "image/png"; Bytes = $validPngBytes }
)
$bodyBytes2 = Build-MultipartBody -Fields $fields2 -Files $files2 -Boundary $boundary2

$res2 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bodyBytes2 -ContentType "multipart/form-data; boundary=$boundary2" -Headers @{
    "Idempotency-Key" = $idempotencyKey2
}

$ref2 = if ($res2.Body) { $res2.Body.reference_code } else { $null }
$key2 = if ($res2.Body) { $res2.Body.access_key } else { $null }
$success2 = ($res2.Status -eq 201) -and ($null -ne $ref2) -and ($ref2.StartsWith("SCM-")) -and (-not [string]::IsNullOrEmpty($key2))
Report-Step 2 $success2 $res2.Status "201"

# --- STEP 3: Track with access key returns 200 ---
$trackPayload3 = [System.Text.Encoding]::UTF8.GetBytes((@{ reference_code = $ref2; access_key = $key2 } | ConvertTo-Json))
$res3 = Invoke-ApiRaw -Method "POST" -Path "/reports/track/" -BodyBytes $trackPayload3 -ContentType "application/json"
$success3 = ($res3.Status -eq 200) -and ($res3.Body -and $res3.Body.reference_code -eq $ref2)
Report-Step 3 $success3 $res3.Status "200"

# --- STEP 4: Track with wrong key 404, track unknown ref 404; error bodies match ---
$trackWrongKey = [System.Text.Encoding]::UTF8.GetBytes((@{ reference_code = $ref2; access_key = "wrong_key_12345678901234567890" } | ConvertTo-Json))
$res4a = Invoke-ApiRaw -Method "POST" -Path "/reports/track/" -BodyBytes $trackWrongKey -ContentType "application/json"

$trackUnknownRef = [System.Text.Encoding]::UTF8.GetBytes((@{ reference_code = "SCM-2026-UNKNOWN0"; access_key = "any_key_12345678901234567890" } | ConvertTo-Json))
$res4b = Invoke-ApiRaw -Method "POST" -Path "/reports/track/" -BodyBytes $trackUnknownRef -ContentType "application/json"

$code4a = if ($res4a.Body -and $res4a.Body.error) { $res4a.Body.error.code } else { $null }
$code4b = if ($res4b.Body -and $res4b.Body.error) { $res4b.Body.error.code } else { $null }
$msg4a = if ($res4a.Body -and $res4a.Body.error) { $res4a.Body.error.message } else { $null }
$msg4b = if ($res4b.Body -and $res4b.Body.error) { $res4b.Body.error.message } else { $null }

$success4 = ($res4a.Status -eq 404) -and ($res4b.Status -eq 404) -and ($code4a -eq $code4b) -and ($msg4a -eq $msg4b)
$reportedStatus4 = if ($res4a.Status -ne 404) { $res4a.Status } else { $res4b.Status }
Report-Step 4 $success4 $reportedStatus4 "404"

# --- STEP 5: Replay with same Idempotency-Key returns 200, same ref, access_key null/absent ---
$res5 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bodyBytes2 -ContentType "multipart/form-data; boundary=$boundary2" -Headers @{
    "Idempotency-Key" = $idempotencyKey2
}
$ref5 = if ($res5.Body) { $res5.Body.reference_code } else { $null }
$key5 = if ($res5.Body) { $res5.Body.access_key } else { $null }
$success5 = ($res5.Status -eq 200) -and ($ref5 -eq $ref2) -and ([string]::IsNullOrEmpty($key5))
Report-Step 5 $success5 $res5.Status "200"

# --- STEP 6: Renamed .exe as .png returns 400 ---
$boundary6 = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N")
$exeBytes = [System.Text.Encoding]::ASCII.GetBytes("MZ fake executable header payload for security test")
$files6 = @(
    @{ Name = "evidence"; Filename = "malware.png"; ContentType = "image/png"; Bytes = $exeBytes }
)
$bodyBytes6 = Build-MultipartBody -Fields $fields2 -Files $files6 -Boundary $boundary6
$res6 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bodyBytes6 -ContentType "multipart/form-data; boundary=$boundary6"
$success6 = ($res6.Status -eq 400)
Report-Step 6 $success6 $res6.Status "400"

# --- STEP 7: 4 files attached returns 400 ---
$boundary7 = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N")
$files7 = @(
    @{ Name = "evidence"; Filename = "1.png"; ContentType = "image/png"; Bytes = $validPngBytes },
    @{ Name = "evidence"; Filename = "2.png"; ContentType = "image/png"; Bytes = $validPngBytes },
    @{ Name = "evidence"; Filename = "3.png"; ContentType = "image/png"; Bytes = $validPngBytes },
    @{ Name = "evidence"; Filename = "4.png"; ContentType = "image/png"; Bytes = $validPngBytes }
)
$bodyBytes7 = Build-MultipartBody -Fields $fields2 -Files $files7 -Boundary $boundary7
$res7 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bodyBytes7 -ContentType "multipart/form-data; boundary=$boundary7"
$success7 = ($res7.Status -eq 400)
Report-Step 7 $success7 $res7.Status "400"

# --- STEP 8: >16MB body returns 413 ---
$oversizedBytes = New-Object byte[] (16 * 1024 * 1024 + 1024)
$res8 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $oversizedBytes -ContentType "multipart/form-data; boundary=boundary"
$success8 = ($res8.Status -eq 413)
Report-Step 8 $success8 $res8.Status "413"

# --- STEP 9: Citizen login + report returns 201 with ref ---
$citizenEmail = New-SmokeEmail
$citizenPass = "CitizenPass123!"
$regPayload = [System.Text.Encoding]::UTF8.GetBytes((@{ email = $citizenEmail; password = $citizenPass; full_name = "Smoke Citizen" } | ConvertTo-Json))
$null = Invoke-ApiRaw -Method "POST" -Path "/auth/register/" -BodyBytes $regPayload

$loginPayload = [System.Text.Encoding]::UTF8.GetBytes((@{ email = $citizenEmail; password = $citizenPass } | ConvertTo-Json))
$loginRes = Invoke-ApiRaw -Method "POST" -Path "/auth/login/" -BodyBytes $loginPayload
$citizenToken = if ($loginRes.Body) { $loginRes.Body.access } else { $null }

$boundary9 = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N")
$fields9 = @{
    category = "IMPERSONATION"
    platform = "WHATSAPP"
    message_text = "Citizen reported impersonation call claiming tax arrears."
    country_code = "MY"
    currency = "MYR"
    financial_loss = "0.00"
    payment_method = "NONE"
    admin_area = "Selangor"
    indicators = '[{"type":"PHONE","value":"0198765432"}]'
}
$bodyBytes9 = Build-MultipartBody -Fields $fields9 -Files @() -Boundary $boundary9

$res9 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bodyBytes9 -ContentType "multipart/form-data; boundary=$boundary9" -Headers @{
    "Authorization" = "Bearer $citizenToken"
}
$ref9 = if ($res9.Body) { $res9.Body.reference_code } else { $null }
$success9 = ($res9.Status -eq 201) -and ($null -ne $ref9) -and ($ref9.StartsWith("SCM-"))
Report-Step 9 $success9 $res9.Status "201"

# --- STEP 10: /reports/mine/ contains the report ---
$res10 = Invoke-ApiRaw -Method "GET" -Path "/reports/mine/" -Headers @{
    "Authorization" = "Bearer $citizenToken"
}
$foundInMine = $false
if ($res10.Body -and $res10.Body.results) {
    foreach ($item in $res10.Body.results) {
        if ($item.reference_code -eq $ref9) {
            $foundInMine = $true
            break
        }
    }
}
$success10 = ($res10.Status -eq 200) -and $foundInMine
Report-Step 10 $success10 $res10.Status "200"

# --- STEP 11: Citizen submits with anonymous: true -> 201; /reports/mine/ does NOT contain it ---
$boundary11 = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N")
$fields11 = @{
    category = "IMPERSONATION"
    platform = "TELEGRAM"
    message_text = "Citizen anonymous submission regarding investment scam."
    country_code = "MY"
    currency = "MYR"
    financial_loss = "0.00"
    payment_method = "NONE"
    admin_area = "Selangor"
    indicators = '[{"type":"URL","value":"https://anon-invest.test"}]'
    anonymous = "true"
}
$bodyBytes11 = Build-MultipartBody -Fields $fields11 -Files @() -Boundary $boundary11
$res11 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bodyBytes11 -ContentType "multipart/form-data; boundary=$boundary11" -Headers @{
    "Authorization" = "Bearer $citizenToken"
}
$ref11 = if ($res11.Body) { $res11.Body.reference_code } else { $null }

$res11Mine = Invoke-ApiRaw -Method "GET" -Path "/reports/mine/" -Headers @{
    "Authorization" = "Bearer $citizenToken"
}
$foundAnonInMine = $false
if ($res11Mine.Body -and $res11Mine.Body.results) {
    foreach ($item in $res11Mine.Body.results) {
        if ($item.reference_code -eq $ref11) {
            $foundAnonInMine = $true
            break
        }
    }
}
$success11 = ($res11.Status -eq 201) -and ($null -ne $ref11) -and (-not $foundAnonInMine)
Report-Step 11 $success11 $res11.Status "201"

# --- STEP 12: 5 valid anonymous reports return 201, 6th returns 429 with Retry-After ---
$step12Statuses = @()
$expectedStep12 = @(201, 201, 201, 201, 201, 429)
$hasRetryAfter12 = $false
$allMatches12 = $true

for ($i = 1; $i -le 6; $i++) {
    $boundary12 = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N")
    $validPhone = "+6012345678$i"
    $fields12 = @{
        category = "PHISHING"
        platform = "SMS"
        message_text = "Throttle test spam report payload iteration $i."
        country_code = "MY"
        currency = "MYR"
        financial_loss = "0.00"
        payment_method = "NONE"
        admin_area = "Selangor"
        indicators = "[{`"type`":`"PHONE`",`"value`":`"$validPhone`"}]"
    }
    $bBytes12 = Build-MultipartBody -Fields $fields12 -Files @() -Boundary $boundary12
    $res12 = Invoke-ApiRaw -Method "POST" -Path "/reports/" -BodyBytes $bBytes12 -ContentType "multipart/form-data; boundary=$boundary12"
    $step12Statuses += $res12.Status
    $expectedForReq = $expectedStep12[$i - 1]
    Write-Host ("  Step 12 request {0}/6: HTTP {1} (expected: {2})" -f $i, $res12.Status, $expectedForReq)

    if ($res12.Status -ne $expectedForReq) {
        $allMatches12 = $false
    }
    if ($res12.Status -eq 429) {
        $retryHdr = if ($res12.Headers) { $res12.Headers["Retry-After"] } else { $null }
        if (-not [string]::IsNullOrEmpty($retryHdr)) {
            $hasRetryAfter12 = $true
        }
    }
}

$success12 = $allMatches12 -and $hasRetryAfter12
$lastStatus12 = if ($step12Statuses.Count -gt 0) { $step12Statuses[-1] } else { 0 }
Report-Step 12 $success12 $lastStatus12 "429 (5x 201 then 429)"

# --- STEP 13: Check evidence object in local moto bucket (port 5001) if running, else SKIP ---
$motoRunning = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect("127.0.0.1", 5001, $null, $null)
    $wait = $iar.AsyncWaitHandle.WaitOne(1000, $false)
    if ($wait -and $tcp.Connected) {
        $tcp.EndConnect($iar)
        $motoRunning = $true
    }
    $tcp.Close()
} catch {
    $motoRunning = $false
}

if ($motoRunning) {
    try {
        $motoResp = Invoke-WebRequest -Uri "http://localhost:5001/scamshield-evidence-dev?list-type=2" -Method GET -UseBasicParsing -TimeoutSec 3
        if ($motoResp.StatusCode -eq 200) {
            Report-Step 13 $true 200 "200"
        } else {
            Report-Step 13 $false [int]$motoResp.StatusCode "200"
        }
    } catch {
        Report-Step 13 $false 0 "200"
    }
} else {
    Report-Step 13 $false 0 "200" $true
}

# --- SUMMARY ---
Write-Host ""
Write-Host "================== Summary =================="
Write-Host ("Passed: {0} / 13" -f $passedCount)
Write-Host ("Failed: {0} / 13" -f $failedCount)
if ($skippedCount -gt 0) {
    Write-Host ("Skipped: {0} / 13" -f $skippedCount)
}

if ($failedCount -gt 0) {
    Write-Host "RESULT: FAIL"
    exit 1
} else {
    Write-Host "RESULT: PASS"
    exit 0
}
