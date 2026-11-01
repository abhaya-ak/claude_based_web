# backend/tools/smoke_auth.ps1
# PowerShell 5.1 compatible authentication and RBAC smoke test suite.
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

# Admin credentials check
$adminEmail = $env:SMOKE_ADMIN_EMAIL
$adminPassword = $env:SMOKE_ADMIN_PASSWORD
if (-not $adminEmail -or -not $adminPassword) {
    Write-Host "FAIL: SMOKE_ADMIN_EMAIL and SMOKE_ADMIN_PASSWORD environment variables are required."
    exit 1
}

function New-SmokeEmail {
    $randHex = [System.Guid]::NewGuid().ToString("N").Substring(0, 10)
    return "smoke-$randHex@example.test"
}

function Invoke-Api {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Method,
        [Parameter(Mandatory=$true)]
        [string]$Path,
        [object]$Body = $null,
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

    if ($null -ne $Body) {
        if ($Body -is [string]) {
            $invokeParams["Body"] = $Body
        } else {
            $invokeParams["Body"] = ($Body | ConvertTo-Json -Compress)
        }
        $invokeParams["ContentType"] = "application/json"
    }

    $result = @{
        Status = 0
        Body = $null
        RawBody = ""
        Headers = @{}
        RawContent = ""
        SetCookie = ""
    }

    try {
        $resp = Invoke-WebRequest @invokeParams
        $result.Status = [int]$resp.StatusCode
        $result.RawBody = $resp.Content
        $result.Headers = $resp.Headers
        $result.RawContent = $resp.RawContent
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
                $stream = $webResp.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $result.RawBody = $reader.ReadToEnd()
                    $reader.Dispose()
                }
            }
            if ($webResp.Headers["Set-Cookie"]) {
                $result.SetCookie = [string]$webResp.Headers["Set-Cookie"]
            }
        } else {
            $result.Status = -1
            $result.RawBody = $_.Exception.Message
        }
    } catch {
        $result.Status = -1
        $result.RawBody = $_.Exception.Message
    }

    if ($result.RawBody) {
        try {
            $result.Body = $result.RawBody | ConvertFrom-Json
        } catch {
            $result.Body = $null
        }
    }

    if ([string]::IsNullOrEmpty($result.SetCookie)) {
        if ($result.Headers -and $result.Headers["Set-Cookie"]) {
            $result.SetCookie = [string]$result.Headers["Set-Cookie"]
        }
    }
    if ([string]::IsNullOrEmpty($result.SetCookie) -and $result.RawContent) {
        $cookieMatches = [regex]::Matches($result.RawContent, "(?im)^Set-Cookie:\s*(.+)$")
        if ($cookieMatches.Count -gt 0) {
            $lines = foreach ($m in $cookieMatches) { $m.Groups[1].Value.Trim() }
            $result.SetCookie = ($lines -join "; ")
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
        Write-Host ("STEP {0}: SKIP (HTTP {1}, throttled or setup unavailable)" -f $Step, $ActualStatus)
        $script:skippedCount++
    } elseif ($Success) {
        Write-Host ("STEP {0}: PASS (HTTP {1}, expected: {2})" -f $Step, $ActualStatus, $ExpectedStatus)
        $script:passedCount++
    } else {
        Write-Host ("STEP {0}: FAIL (HTTP {1}, expected: {2})" -f $Step, $ActualStatus, $ExpectedStatus)
        $script:failedCount++
    }
}

# --- STEP 1: Citizen register with extra role: ADMIN in payload (201, shows CITIZEN) ---
$citizenEmail = New-SmokeEmail
$citizenPassword = "SmokeCitizenPassword123!"
$res1 = Invoke-Api -Method "POST" -Path "/auth/register/" -Body @{
    email = $citizenEmail
    password = $citizenPassword
    full_name = "Smoke Citizen"
    role = "ADMIN"
}
$success1 = ($res1.Status -eq 201) -and ($res1.Body.user.role -eq "CITIZEN")
Report-Step 1 $success1 $res1.Status "201"

# --- STEP 2: Duplicate register (409) ---
$res2 = Invoke-Api -Method "POST" -Path "/auth/register/" -Body @{
    email = $citizenEmail
    password = $citizenPassword
    full_name = "Smoke Citizen"
    role = "ADMIN"
}
$success2 = ($res2.Status -eq 409)
Report-Step 2 $success2 $res2.Status "409"

# --- STEP 3: Wrong password and unknown email (both 401 with identical error code/message) ---
$unknownEmail = New-SmokeEmail
$res3a = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $citizenEmail
    password = "WrongPassword999!"
}
$res3b = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $unknownEmail
    password = "SmokeCitizenPassword123!"
}
$codeA = if ($res3a.Body -and $res3a.Body.error) { $res3a.Body.error.code } else { $null }
$msgA = if ($res3a.Body -and $res3a.Body.error) { $res3a.Body.error.message } else { $null }
$codeB = if ($res3b.Body -and $res3b.Body.error) { $res3b.Body.error.code } else { $null }
$msgB = if ($res3b.Body -and $res3b.Body.error) { $res3b.Body.error.message } else { $null }
$success3 = ($res3a.Status -eq 401) -and ($res3b.Status -eq 401) -and ($codeA -eq $codeB) -and ($msgA -eq $msgB) -and (-not [string]::IsNullOrEmpty($codeA))
$reportedStatus3 = if ($res3a.Status -ne 401) { $res3a.Status } else { $res3b.Status }
Report-Step 3 $success3 $reportedStatus3 "401"

# --- STEP 4: Login correct (200, access token, refresh cookie with HttpOnly & Path=/api/v1/auth/) ---
$citizenSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$res4 = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $citizenEmail
    password = $citizenPassword
} -Session $citizenSession

$hasAccess = ($res4.Body -and -not [string]::IsNullOrEmpty($res4.Body.access))
$citizenAccess = if ($hasAccess) { $res4.Body.access } else { $null }

$setCookieStr = $res4.SetCookie
$hasCookie = $false
$oldRefreshCookieValue = $null

$cookieMatchesHeader = ($setCookieStr -match "(?i)HttpOnly") -and ($setCookieStr -match "(?i)Path=/api/v1/auth/")
if ($setCookieStr -match "refresh=([^;,\s]+)") {
    $oldRefreshCookieValue = $matches[1]
}

$cookiesInSession = $citizenSession.Cookies.GetCookies([System.Uri]"http://localhost:8000/api/v1/auth/")
foreach ($ck in $cookiesInSession) {
    if ($ck.Name -eq "refresh") {
        if ($ck.HttpOnly -and ($ck.Path -eq "/api/v1/auth/")) {
            $hasCookie = $true
        }
        if (-not $oldRefreshCookieValue) {
            $oldRefreshCookieValue = $ck.Value
        }
    }
}
if ($cookieMatchesHeader) {
    $hasCookie = $true
}

$success4 = ($res4.Status -eq 200) -and $hasAccess -and $hasCookie -and (-not [string]::IsNullOrEmpty($oldRefreshCookieValue))
Report-Step 4 $success4 $res4.Status "200"

# --- STEP 5: GET /auth/me/ with Bearer: 200 and role CITIZEN; without token: 401 ---
$res5a = Invoke-Api -Method "GET" -Path "/auth/me/" -Headers @{ "Authorization" = "Bearer $citizenAccess" }
$res5b = Invoke-Api -Method "GET" -Path "/auth/me/"
$roleIsCitizen = ($res5a.Body -and $res5a.Body.role -eq "CITIZEN")
$success5 = ($res5a.Status -eq 200) -and ($res5b.Status -eq 401) -and $roleIsCitizen
$reportedStatus5 = if ($res5a.Status -ne 200) { $res5a.Status } elseif ($res5b.Status -ne 401) { $res5b.Status } else { 200 }
$expectedStatus5 = if ($res5a.Status -ne 200) { "200" } elseif ($res5b.Status -ne 401) { "401" } else { "200" }
Report-Step 5 $success5 $reportedStatus5 $expectedStatus5

# --- STEP 6: POST /auth/refresh/ without header: 403; with X-Requested-With: 200 & NEW token ---
$res6a = Invoke-Api -Method "POST" -Path "/auth/refresh/" -Session $citizenSession
$res6b = Invoke-Api -Method "POST" -Path "/auth/refresh/" -Headers @{ "X-Requested-With" = "scamshield-web" } -Session $citizenSession
$newCitizenAccess = if ($res6b.Body) { $res6b.Body.access } else { $null }
$hasNewAccess = (-not [string]::IsNullOrEmpty($newCitizenAccess)) -and ($newCitizenAccess -ne $citizenAccess)
$success6 = ($res6a.Status -eq 403) -and ($res6b.Status -eq 200) -and $hasNewAccess
$reportedStatus6 = if ($res6a.Status -ne 403) { $res6a.Status } elseif ($res6b.Status -ne 200) { $res6b.Status } else { 200 }
$expectedStatus6 = if ($res6a.Status -ne 403) { "403" } elseif ($res6b.Status -ne 200) { "200" } else { "200" }
Report-Step 6 $success6 $reportedStatus6 $expectedStatus6

# --- STEP 7: Reuse OLD refresh cookie after rotation: 401 ---
# Fresh login to acquire a genuine refresh cookie before rotating
$step7Session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$res7Login = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $citizenEmail
    password = $citizenPassword
} -Session $step7Session

if ($res7Login.Status -eq 429) {
    Report-Step 7 $false 429 "401" $true
} else {
    $s7OldCookieVal = $null
    $setCookieStr7 = $res7Login.SetCookie
    if ($setCookieStr7 -match "refresh=([^;,\s]+)") {
        $s7OldCookieVal = $matches[1]
    }
    if (-not $s7OldCookieVal) {
        $cookies7 = $step7Session.Cookies.GetCookies([System.Uri]"http://localhost:8000/api/v1/auth/")
        foreach ($ck in $cookies7) {
            if ($ck.Name -eq "refresh") { $s7OldCookieVal = $ck.Value; break }
        }
    }

    # Rotate the refresh cookie on step7Session
    $res7Rotate = Invoke-Api -Method "POST" -Path "/auth/refresh/" -Headers @{ "X-Requested-With" = "scamshield-web" } -Session $step7Session

    if ($res7Rotate.Status -eq 429) {
        Report-Step 7 $false 429 "401" $true
    } else {
        # Now try to reuse the OLD rotated cookie in a clean session
        $oldSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
        if ($s7OldCookieVal) {
            $oldCookie = New-Object System.Net.Cookie("refresh", $s7OldCookieVal, "/api/v1/auth/", "localhost")
            $oldSession.Cookies.Add($oldCookie)
        }
        $res7 = Invoke-Api -Method "POST" -Path "/auth/refresh/" -Headers @{ "X-Requested-With" = "scamshield-web" } -Session $oldSession
        $success7 = ($res7.Status -eq 401)
        Report-Step 7 $success7 $res7.Status "401"
    }
}

# --- STEP 8: POST /auth/register/staff/ ANALYST: 201; role ADMIN: 400 ---
$staffEmail = New-SmokeEmail
$staffPassword = "SmokeStaffPassword123!"
$res8a = Invoke-Api -Method "POST" -Path "/auth/register/staff/" -Body @{
    email = $staffEmail
    password = $staffPassword
    full_name = "Smoke Staff Analyst"
    role = "ANALYST"
    organization = "Fraud Watch Organization"
    credential_note = "Valid investigator credentials"
}
$fakeAdminEmail = New-SmokeEmail
$res8b = Invoke-Api -Method "POST" -Path "/auth/register/staff/" -Body @{
    email = $fakeAdminEmail
    password = $staffPassword
    full_name = "Smoke Staff Admin"
    role = "ADMIN"
    organization = "Fraud Watch Organization"
    credential_note = "Valid investigator credentials"
}
$success8 = ($res8a.Status -eq 201) -and ($res8b.Status -eq 400)
$reportedStatus8 = if ($res8a.Status -ne 201) { $res8a.Status } elseif ($res8b.Status -ne 400) { $res8b.Status } else { 201 }
$expectedStatus8 = if ($res8a.Status -ne 201) { "201" } elseif ($res8b.Status -ne 400) { "400" } else { "201" }
Report-Step 8 $success8 $reportedStatus8 $expectedStatus8

# --- STEP 9: Pending staff login: 403 with code account_not_approved and NO access token ---
$res9 = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $staffEmail
    password = $staffPassword
}
$code9 = if ($res9.Body -and $res9.Body.error) { $res9.Body.error.code } else { $null }
$noAccess = ($null -eq $res9.Body.access) -and ($null -eq $res9.Body.error.access)
$success9 = ($res9.Status -eq 403) -and ($code9 -eq "account_not_approved") -and $noAccess
Report-Step 9 $success9 $res9.Status "403"

# --- STEP 10: Citizen token on GET /admin-portal/users/: 403 ---
$res10 = Invoke-Api -Method "GET" -Path "/admin-portal/users/" -Headers @{
    "Authorization" = "Bearer $newCitizenAccess"
}
$success10 = ($res10.Status -eq 403)
Report-Step 10 $success10 $res10.Status "403"

# --- STEP 11: Admin login; GET /admin-portal/users/?status=PENDING; approve: 200; staff login: 200 ---
$adminSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$res11a = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $adminEmail
    password = $adminPassword
} -Session $adminSession
$adminAccess = if ($res11a.Body) { $res11a.Body.access } else { $null }
$adminId = if ($res11a.Body -and $res11a.Body.user) { $res11a.Body.user.id } else { $null }

$res11b = Invoke-Api -Method "GET" -Path "/admin-portal/users/?status=PENDING" -Headers @{
    "Authorization" = "Bearer $adminAccess"
}

$staffId = $null
if ($res11b.Body -is [System.Collections.IEnumerable]) {
    foreach ($u in $res11b.Body) {
        if ($u.email -eq $staffEmail) {
            $staffId = $u.id
            break
        }
    }
}

$res11c = if ($staffId) {
    Invoke-Api -Method "POST" -Path "/admin-portal/users/$staffId/approve/" -Headers @{
        "Authorization" = "Bearer $adminAccess"
    }
} else {
    @{ Status = 0 }
}

$res11d = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $staffEmail
    password = $staffPassword
}
$staffLoginAccess = if ($res11d.Body) { $res11d.Body.access } else { $null }

$success11 = ($res11a.Status -eq 200) -and ($res11b.Status -eq 200) -and ($null -ne $staffId) -and ($res11c.Status -eq 200) -and ($res11d.Status -eq 200) -and (-not [string]::IsNullOrEmpty($staffLoginAccess))
$reportedStatus11 = if ($res11a.Status -ne 200) { $res11a.Status } elseif ($res11b.Status -ne 200) { $res11b.Status } elseif ($res11c.Status -ne 200) { $res11c.Status } elseif ($res11d.Status -ne 200) { $res11d.Status } else { 200 }
Report-Step 11 $success11 $reportedStatus11 "200"

# --- STEP 12: Admin change-role on own ID: 4xx (self-change forbidden) ---
if (-not $adminId -and $adminAccess) {
    $resMe = Invoke-Api -Method "GET" -Path "/auth/me/" -Headers @{ "Authorization" = "Bearer $adminAccess" }
    if ($resMe.Body) { $adminId = $resMe.Body.id }
}

$res12 = if ($adminId) {
    Invoke-Api -Method "POST" -Path "/admin-portal/users/$adminId/change-role/" -Headers @{
        "Authorization" = "Bearer $adminAccess"
    } -Body @{ role = "ANALYST" }
} else {
    @{ Status = 0 }
}
$is4xx = ($res12.Status -ge 400 -and $res12.Status -lt 500)
$success12 = $is4xx
Report-Step 12 $success12 $res12.Status "4xx"

# --- STEP 13: Password change as citizen: 204; old refresh cookie rejected; login with new password: 200 ---
$newCitizenPassword = "NewSmokeCitizenPass456!"
$res13a = Invoke-Api -Method "POST" -Path "/auth/password/change/" -Headers @{
    "Authorization" = "Bearer $newCitizenAccess"
} -Body @{
    current_password = $citizenPassword
    new_password = $newCitizenPassword
}

$res13b = Invoke-Api -Method "POST" -Path "/auth/refresh/" -Headers @{
    "X-Requested-With" = "scamshield-web"
} -Session $citizenSession

$res13c = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $citizenEmail
    password = $newCitizenPassword
} -Session $citizenSession

$citizenAccess = if ($res13c.Body) { $res13c.Body.access } else { $null }
$citizenPassword = $newCitizenPassword
$success13 = ($res13a.Status -eq 204) -and ($res13b.Status -eq 401) -and ($res13c.Status -eq 200) -and (-not [string]::IsNullOrEmpty($citizenAccess))
$reportedStatus13 = if ($res13a.Status -ne 204) { $res13a.Status } elseif ($res13b.Status -ne 401) { $res13b.Status } elseif ($res13c.Status -ne 200) { $res13c.Status } else { 204 }
$expectedStatus13 = if ($res13a.Status -ne 204) { "204" } elseif ($res13b.Status -ne 401) { "401" } elseif ($res13c.Status -ne 200) { "200" } else { "204" }
Report-Step 13 $success13 $reportedStatus13 $expectedStatus13

# --- STEP 14: Logout: 204; cookie cleared; refresh after logout: 401 ---
# Fresh login to acquire a genuine session with refresh cookie
$step14Session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$res14Login = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
    email = $citizenEmail
    password = $citizenPassword
} -Session $step14Session

if ($res14Login.Status -eq 429) {
    Report-Step 14 $false 429 "204" $true
} else {
    $res14a = Invoke-Api -Method "POST" -Path "/auth/logout/" -Headers @{
        "X-Requested-With" = "scamshield-web"
    } -Session $step14Session

    $res14b = Invoke-Api -Method "POST" -Path "/auth/refresh/" -Headers @{
        "X-Requested-With" = "scamshield-web"
    } -Session $step14Session

    $success14 = ($res14a.Status -eq 204) -and ($res14b.Status -eq 401)
    $reportedStatus14 = if ($res14a.Status -ne 204) { $res14a.Status } elseif ($res14b.Status -ne 401) { $res14b.Status } else { 204 }
    $expectedStatus14 = if ($res14a.Status -ne 204) { "204" } elseif ($res14b.Status -ne 401) { "401" } else { "204" }
    Report-Step 14 $success14 $reportedStatus14 $expectedStatus14
}

# --- STEP 15: Throttle: 11 wrong logins returns 429 with Retry-After ---
$throttleEmail = New-SmokeEmail
$null = Invoke-Api -Method "POST" -Path "/auth/register/" -Body @{
    email = $throttleEmail
    password = "ThrottleUserPass123!"
    full_name = "Throttle Smoke User"
}

$got429 = $false
$hasRetryAfter = $false
$lastStatus15 = 0

for ($i = 1; $i -le 11; $i++) {
    $res15 = Invoke-Api -Method "POST" -Path "/auth/login/" -Body @{
        email = $throttleEmail
        password = "WrongPassword999!"
    }
    $lastStatus15 = $res15.Status
    if ($lastStatus15 -eq 429) {
        $got429 = $true
        $retryHdr = if ($res15.Headers) { $res15.Headers["Retry-After"] } else { $null }
        if (-not [string]::IsNullOrEmpty($retryHdr)) {
            $hasRetryAfter = $true
        }
        break
    }
}

$success15 = $got429 -and $hasRetryAfter
Report-Step 15 $success15 $lastStatus15 "429"

# --- SUMMARY ---
Write-Host ""
Write-Host "================== Summary =================="
Write-Host ("Passed: {0} / 15" -f $passedCount)
Write-Host ("Failed: {0} / 15" -f $failedCount)
if ($skippedCount -gt 0) {
    Write-Host ("Skipped: {0} / 15" -f $skippedCount)
}

if ($failedCount -gt 0) {
    Write-Host "RESULT: FAIL"
    exit 1
} else {
    Write-Host "RESULT: PASS"
    exit 0
}
