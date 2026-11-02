#!/usr/bin/env python3
"""Emit independently authored DSP gain fixtures; assemble with dsp56300-asm."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile


def assembly():
    lines = ['org p:$0', 'jmp start'] + ['nop'] * 255
    lines.extend(('start: movec #>$0,sr', 'movec #>$2,omr'))
    for route, gain in enumerate((0x400000, 0xc00000, 0x200000)):
        lines.append(f'move #>${gain:06x},y0')
        for sample in range(64):
            lines.extend((f'move x:${0x100 + sample:x},x0', 'mpy x0,y0,a',
                          f'move a,x:${0x200 + route * 64 + sample:x}'))
    lines.extend(('movep #>$20,x:<<$ffffd4', 'movep #1,x:<<$ffffd6',
                  'move #>$51d00d,x0', 'move x0,x:$3f0',
                  'idle: movep #1,x:<<$ffffc4', 'jmp idle'))
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembler', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'program.asm'
        binary = Path(directory) / 'program.bin'
        source.write_text(assembly())
        subprocess.run([args.assembler, str(source), '-o', str(binary)], check=True)
        data = binary.read_bytes()
    if len(data) % 4 or len(data) > 8192:
        raise ValueError('program exceeds the bootstrap image')
    words = struct.unpack('<' + 'I' * (len(data) // 4), data)
    args.output.write_text('/* Generated from generate_program.py; public synthetic microcode. */\n'
                           'static const unsigned program[] = {\n' +
                           ''.join(f'    0x{word:06x},\n' for word in words) + '};\n')


if __name__ == '__main__':
    main()
