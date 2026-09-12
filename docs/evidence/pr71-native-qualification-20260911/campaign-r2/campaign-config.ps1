$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# The lab root is supplied by the deployment wrapper. Keeping paths relative
# to that root lets the checked-in campaign remain portable and reviewable.
$LabRoot = $env:XEMU_LAB_ROOT
if ([string]::IsNullOrWhiteSpace($LabRoot)) {
    throw 'Set XEMU_LAB_ROOT to the test-box lab root before invoking the campaign.'
}
$IncomingRoot = Join-Path $LabRoot 'incoming'
$XisoRoot = Join-Path $IncomingRoot 'pr71-suite-0bb7618-r1'
$XisoIdentityPath = Join-Path $XisoRoot 'identity.json'
if (Test-Path -LiteralPath $XisoIdentityPath -PathType Leaf) {
    $XisoIdentity = Get-Content -LiteralPath $XisoIdentityPath -Raw |
        ConvertFrom-Json -AsHashtable
} else {
    # Root stages the latest current-main XISO and this identity file after
    # building from perf-tests main 0bb7618... . The runner refuses to run
    # while any token remains, so an old image cannot be reused.
    $XisoIdentity = [ordered]@{
        TestSourceCommit = '0bb7618aec5ea73355a03bcb176a922ea8b3ec2e'
        TestSourceTree = 'd0dfbf18f5fccafd3fc06b2401bbe1c17affdda4'
        ImageSha256 = 'a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687'
        ImageBytes = 3670016
        CatalogSha256 = '8298d8baa59144caa4fd8715c4709b86e40e47fb5f830539b853fefa2a9f1a29'
        CatalogId = 'sha256:a0d41d33c1f5da2ba60db7102b094847df048d489ee2a7d7c72d9c6d0048a86e'
        RecordCount = 157
        LeafCount = 152
        GroupCount = 5
        RegisteredRecordCount = 152
        RegisteredLeafCount = 147
        ExpectedOpenGlNonPass = @(
            'report_query.dma_range_guard',
            'texture_cubemap_fallback.unbordered_subblock_dxt1'
        )
        ExpectedVulkanNonPass = @('report_query.dma_range_guard')
    }
}

$Campaign = [ordered]@{
    SchemaVersion = 3
    CampaignId = 'pr71-native-qualification-20260911-r2'
    PackageRoot = $PSScriptRoot
    ResultsRoot = Join-Path $LabRoot 'captures\pr71-native-qualification-20260911-r2'

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
            LogicalCommit = '5edff26383c6440da35bc92b9fca35f4a404b03b'
            SourceCommit = 'a08c4d92916554f55f09231f525cda1f93b55129'
            Tree = '11981a736703553349357cd89926b443901cadb9'
            Xemu = Join-Path $IncomingRoot 'pr76-cross-gpu-a08c4d9291-r2\xemu.exe'
            XemuSha256 = '91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3'
            BuildInfo = Join-Path $IncomingRoot 'pr76-cross-gpu-a08c4d9291-r2\BUILD_INFO.txt'
        }
        candidate = [ordered]@{
            Role = 'candidate'
            LogicalCommit = 'd21072b39fd3a84b06943977f5f441116f229b2e'
            SourceCommit = 'd21072b39fd3a84b06943977f5f441116f229b2e'
            Tree = '5280daf18730ffd57441bcc80ddbea3d33e84ee9'
            Xemu = Join-Path $IncomingRoot 'pr71-282909-release-r1\xemu.exe'
            XemuSha256 = 'e161c4cfe6b7b6af9d91fc7f28afde52efa43e6d899db24f1b0d2a2324e0d2c5'
            BuildInfo = Join-Path $IncomingRoot 'pr71-282909-release-r1\BUILD_INFO.txt'
        }
    }

    Xiso = [ordered]@{
        Python = Join-Path $LabRoot 'suite\python313\python.exe'
        Runner = Join-Path $LabRoot 'suite\run-suite-pr71.py'
        Image = Join-Path $XisoRoot 'xemu-perf-tests-0bb7618.iso'
        Catalog = Join-Path $XisoRoot 'catalog-0bb7618.json'
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
