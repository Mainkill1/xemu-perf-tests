#!/usr/bin/env bash
# Rebuild the hash-bound text-symbol map for the captured main executable.
set -euo pipefail

input=${1:?usage: extract-defined-text-symbols.sh /absolute/path/to/xemu.exe [output.tsv.gz]}
output=${2:-defined-text-symbols.tsv.gz}
expected_sha=3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b
actual_sha=$(sha256sum "$input" | awk '{print $1}')

if [ "$actual_sha" != "$expected_sha" ]; then
    echo "refusing: expected $expected_sha, got $actual_sha" >&2
    exit 1
fi

{
    printf '%s\n' \
        "# input_sha256=$actual_sha" \
        '# preferred_image_base=0x0000000140000000' \
        '# columns=va,rva,symbol'
    x86_64-w64-mingw32-nm -n --defined-only "$input" |
        perl -ne 'if (/^([0-9A-Fa-f]+)[[:space:]]+[Tt][[:space:]]+(.+)$/) { print join(chr(9), sprintf("0x%016X", hex($1)), sprintf("0x%08X", hex($1) - 0x140000000), $2), chr(10); }'
} | gzip -9 > "$output"

gzip -t "$output"
sha256sum "$output"
