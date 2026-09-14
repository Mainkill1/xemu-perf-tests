$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# The lab root is supplied by the deployment wrapper. Keeping paths relative
# to that root lets the checked-in campaign remain portable and reviewable.
$LabRoot = $env:XEMU_LAB_ROOT
if ([string]::IsNullOrWhiteSpace($LabRoot)) {
    throw 'Set XEMU_LAB_ROOT to the test-box lab root before invoking the campaign.'
}
$IncomingRoot = Join-Path $LabRoot 'incoming'
$XisoRoot = Join-Path $IncomingRoot 'pr71-suite-0044091-r1'
$XisoIdentityPath = Join-Path $XisoRoot 'identity.json'
if (-not (Test-Path -LiteralPath $XisoIdentityPath -PathType Leaf)) {
    throw "Missing pinned latest-suite identity: $XisoIdentityPath"
}
$XisoIdentity = Get-Content -LiteralPath $XisoIdentityPath -Raw |
    ConvertFrom-Json -AsHashtable

$Campaign = [ordered]@{
    SchemaVersion = 3
    CampaignId = 'pr71-4f0a-qualification-20260913'
    PackageRoot = $PSScriptRoot
    ResultsRoot = Join-Path $LabRoot 'captures\pr71-4f0a-qualification-20260913'

    Builds = [ordered]@{
        fixed_baseline = [ordered]@{
            Role = 'fixed_baseline'
            LogicalCommit = '9f618d6d8c4c446ef023955f3d4de22f661f61a4'
            SourceCommit = 'c17591d59c270b352b72e648f5ed65e4b2a3e77e'
            Tree = '6824a5aa4d9ca288ac96092dc9244684e995b08d'
            Xemu = Join-Path $IncomingRoot 'baseline-fixed-c17591d5\xemu.exe'
            XemuSha256 = '3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b'
            BuildInfo = Join-Path $IncomingRoot 'baseline-fixed-c17591d5\BUILD_INFO.txt'
        }
        previous_main = [ordered]@{
            Role = 'previous_main'
            LogicalCommit = '7a14b022baa1e81e6f2f4dd1ca1fda399a6916aa'
            SourceCommit = '7a14b022baa1e81e6f2f4dd1ca1fda399a6916aa'
            Tree = '2301f1cc976f93e5a943e065c4e12e034f33869f'
            Xemu = Join-Path $IncomingRoot 'pr71-current-main-7a14-exact\xemu.exe'
            XemuSha256 = 'a2c5445474daf63e6fc49e3d28698bb8fce95911e96c51d0005a8ba15793f6f1'
            BuildInfo = Join-Path $IncomingRoot 'pr71-current-main-7a14-exact\BUILD_INFO.txt'
        }
        candidate = [ordered]@{
            Role = 'candidate'
            LogicalCommit = '4f0a8797e6fd831f4c53b6bfe8c68f944236a7fa'
            SourceCommit = '4f0a8797e6fd831f4c53b6bfe8c68f944236a7fa'
            Tree = 'f9272cb731ea2f23aab790b7ee22c9e21ed1276e'
            Xemu = Join-Path $IncomingRoot 'pr71-4f0a-exact\xemu.exe'
            XemuSha256 = '773c9428c4013437f755f03c1adbd7e36b46358accfaf5b50a5ef81dc2cb28ff'
            BuildInfo = Join-Path $IncomingRoot 'pr71-4f0a-exact\BUILD_INFO.txt'
        }
    }

    Xiso = [ordered]@{
        Python = Join-Path $LabRoot 'suite\python313\python.exe'
        Runner = Join-Path $LabRoot 'suite\run-suite-pr71-4f0a.py'
        Image = Join-Path $XisoRoot 'xemu-perf-tests-0044091.iso'
        Catalog = Join-Path $XisoRoot 'catalog-0044091.json'
        TestSourceCommit = $XisoIdentity.TestSourceCommit
        TestSourceTree = $XisoIdentity.TestSourceTree
        ImageSha256 = $XisoIdentity.ImageSha256
        ImageBytes = $XisoIdentity.ImageBytes
        CatalogSha256 = $XisoIdentity.CatalogSha256
        CatalogId = $XisoIdentity.CatalogId
        RecordCount = $XisoIdentity.RecordCount
        LeafCount = $XisoIdentity.LeafCount
        GroupCount = $XisoIdentity.GroupCount
        RegisteredRecordCount = $XisoIdentity.RegisteredRecordCount
        RegisteredLeafCount = $XisoIdentity.RegisteredLeafCount
        ExpectedOpenGlNonPass = $XisoIdentity.ExpectedOpenGlNonPass
        ExpectedVulkanNonPass = $XisoIdentity.ExpectedVulkanNonPass
    }

    Retail = [ordered]@{
        Pgr2FreshSeed = Join-Path $LabRoot 'seeds\pgr2-freshboot-base\pgr2-freshboot-base.qcow2'
        Pgr2SnapshotSeed = Join-Path $LabRoot 'seeds\vm-20260907142321\vm-20260907142321.qcow2'
        Pgr2Snapshot = 'vm-20260907142321'
        Pgr2VulkanConfig = Join-Path $PSScriptRoot 'host-configs\pgr2-vulkan-auto.toml'
        Pgr2OpenGlConfig = Join-Path $PSScriptRoot 'host-configs\pgr2-opengl-auto.toml'
        Pgr2Disc = Join-Path $LabRoot 'games\Project Gotham Racing 2 (USA, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko).iso'
        MorrowindDurationSeconds = 60
        Pgr2SnapshotDurationSeconds = 60
        Pgr2FreshBootDurationSeconds = 120
        Pgr2SnapshotWarmupSeconds = 3
        Pgr2FreshBootWarmupSeconds = 30
        MorrowindConfigRoot = Join-Path $PSScriptRoot 'host-configs\morrowind'
        MorrowindSeed = Join-Path $LabRoot 'seeds\morrowind-heavy-vm-20260905015459\morrowind-heavy-vm-20260905015459.qcow2'
        MorrowindDisc = Join-Path $LabRoot 'games\Elder Scrolls III, The - Morrowind - Game of the Year Edition (USA).iso'
    }

    Host = [ordered]@{
        RequiredSessionId = 1
        MinimumFreeMemoryGiB = 8
        GpuPolicy = 'auto'
        ExpectedAutoAdapterVendor = 'NVIDIA'
        TraceProcessNames = @('PresentMon', 'wpr', 'wprui', 'WPA', 'xperf')
    }
    Controls = [ordered]@{
        CacheShaders = $true
        CandidateHybridOff = $false
        CandidateHybridOn = $true
        ImprovementConvention = 'positive-good'
        Reporting = 'tables-only'
    }
}

$Campaign
