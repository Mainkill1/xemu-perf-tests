#!/usr/bin/env python3
"""Run the public DSP XISO on Linux; verify guest verdict and all GP words."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import time
import tomllib


class Qmp:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(5)
        self.sock.connect(str(path))
        self.stream = self.sock.makefile('rwb')
        self.receive()
        self.call('qmp_capabilities')

    def receive(self):
        while True:
            line = self.stream.readline()
            if not line:
                raise EOFError('QMP disconnected')
            value = json.loads(line)
            if 'event' not in value:
                return value

    def call(self, command, arguments=None):
        request = {'execute': command}
        if arguments is not None:
            request['arguments'] = arguments
        self.stream.write(json.dumps(request).encode() + b'\n')
        self.stream.flush()
        response = self.receive()
        if 'error' in response:
            raise ValueError(response['error'])
        return response.get('return')

    def words(self, address, count):
        output = self.call('human-monitor-command',
                           {'command-line': f'xp /{count}wx 0x{address:x}'})
        words = []
        for line in output.splitlines():
            if ':' in line:
                words.extend(int(word, 16) for word in re.findall(r'0x[0-9a-fA-F]+', line.split(':', 1)[1]))
        if len(words) != count:
            raise ValueError('incomplete QMP memory observation: ' + output)
        return words


def inputs():
    edges = [0, 1, -1, 0x7fffff, -0x800000, 0x400001, -0x400001, 255]
    return edges + [((i * 7919) & 0x7fffff) - 0x400000 for i in range(8, 64)]


def mailbox_terminal(mailbox, guest_ready):
    return ((guest_ready and mailbox[1] == 0xbad) or
            (mailbox[0] == 0x51d00d and mailbox[1] in (0x600d, 0xbad)))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(args):
    args.output.mkdir(mode=0o700)
    config = tomllib.loads(args.config.read_text())
    files = config['sys']['files']
    private = args.output / 'private'
    private.mkdir(mode=0o700)
    for key in ('bootrom_path', 'flashrom_path', 'eeprom_path', 'hdd_path'):
        source = Path(files[key])
        target = private / key
        subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(source), str(target)], check=True)
        files[key] = str(target)
    settings = ['[general]', 'show_welcome = false', '[audio]', 'use_dsp = true',
                f'use_dsp_jit = {str(args.engine == "jit").lower()}', '[net]',
                'enable = false', '[sys.files]']
    if args.audio_engine == 'hle':
        settings.insert(3, 'engine = 2')
    settings += [key + ' = ' + json.dumps(files[key]) for key in
                 ('bootrom_path', 'flashrom_path', 'eeprom_path', 'hdd_path')]
    cfg = private / 'xemu.toml'
    cfg.write_text('\n'.join(settings) + '\n')
    env = os.environ.copy()
    env.update(SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='x11')
    if args.capture:
        words = [int(word, 16) for word in re.findall(r'0x([0-9a-fA-F]+)', args.program_header.read_text())]
        if not words or len(words) > 2048 or any(word > 0xffffff for word in words):
            raise ValueError('invalid bootstrap program')
        image = private / 'gp-program.bin'
        image.write_bytes(struct.pack('<4096I', *(words + [0] * (4096 - len(words)))))
        env.update(XEMU_DSP_CAPTURE_PATH=str(args.output / 'capture.xcr'),
                   XEMU_DSP_CAPTURE_FRAMES='1', XEMU_DSP_CAPTURE_SKIP_FRAMES='0',
                   XEMU_DSP_CAPTURE_GP_PROGRAM=str(image))
    # Reuse only the user's graphical-session selectors, never print them.
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid() or b'plasmashell' not in (process / 'cmdline').read_bytes():
                continue
            entries = dict(item.split(b'=', 1) for item in (process / 'environ').read_bytes().split(b'\0') if b'=' in item)
            for key in (b'DISPLAY', b'XAUTHORITY', b'XDG_RUNTIME_DIR'):
                if key in entries:
                    env[key.decode()] = entries[key].decode()
            break
        except (OSError, ValueError):
            continue
    qmp_path = args.output / 'qmp.sock'
    report = {'status': 'INCOMPLETE', 'engine': args.engine, 'audio_engine': args.audio_engine,
              'iso_sha256': sha(args.iso),
              'launcher_sha256': sha(args.emulator),
              'emulator_sha256': sha(args.emulator_binary or args.emulator),
              'authority': 'EMULATOR_BASELINE',
              'timing_comparable': False, 'audio_device': 'dummy'}
    with (private / 'emulator.log').open('wb') as log:
        process = subprocess.Popen([str(args.emulator), '-config_path', str(cfg),
                                    '-dvd_path', str(args.iso), '-qmp',
                                    f'unix:{qmp_path},server=on,wait=off'],
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
        qmp = None
        try:
            deadline = time.monotonic() + args.timeout
            while not qmp_path.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(.1)
            qmp = Qmp(qmp_path)
            mailbox = [0, 0, 0, 0]
            guest_ready = False
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    mailbox = qmp.words(0xfe830fc0, 4)
                    guest_ready |= qmp.words(0xfe830fd8, 1)[0] == 0x5a07e1
                except ValueError as error:
                    if 'Cannot access memory' not in str(error):
                        raise
                    time.sleep(.1)
                    continue
                if mailbox_terminal(mailbox, guest_ready):
                    break
                time.sleep(.1)
            qmp.call('stop')
            actual_input = qmp.words(0xfe830400, 64)
            actual = qmp.words(0xfe830800, 192)
            actual_program = qmp.words(0xfe83a000, 4096)
            program = [int(word, 16) for word in re.findall(r'0x([0-9a-fA-F]+)', args.program_header.read_text())]
            if len(program) > 2048:
                raise ValueError('program exceeds bootstrap size')
            program += [0] * (4096 - len(program))
            program_matches = actual_program == program
            program_sha256 = hashlib.sha256(struct.pack('<4096I', *actual_program)).hexdigest()
            dma_parts = qmp.words(0xfe830fd0, 2)
            dma_address = dma_parts[0] | (dma_parts[1] << 24)
            if not 0 <= dma_address <= 67108864 - 192 * 4:
                raise ValueError('DMA output outside guest RAM')
            dma_output = qmp.words(dma_address, 192)
            want_input = [value & 0xffffff for value in inputs()]
            want = [(value * numerator // denominator) & 0xffffff
                    for numerator, denominator in ((1, 2), (-1, 2), (1, 4)) for value in inputs()]
            differences = [i for i, (a, b) in enumerate(zip(actual, want)) if a != b]
            success = mailbox[0] == 0x51d00d and mailbox[1] == 0x600d and mailbox[3] == 0 and actual_input == want_input and not differences and dma_output == want and program_matches
            report.update(status='PASS' if success else 'FAIL', mailbox=mailbox,
                          guest_ready=guest_ready,
                          input_preserved=actual_input == want_input,
                          input_words=actual_input, program_matches=program_matches,
                          program_sha256=program_sha256,
                          output_words=actual, expected_words=want,
                          dma_output_words=dma_output, dma_matches=dma_output == want,
                          mismatching_outputs=differences, output_count=192)
        except (OSError, ValueError, EOFError) as error:
            report.update(reason=type(error).__name__, detail=str(error))
        finally:
            if qmp is not None:
                try:
                    qmp.call('quit')
                except (OSError, ValueError, EOFError):
                    pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    (args.output / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--emulator-binary', type=Path)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--program-header', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', choices=('jit', 'interpreter'), default='jit')
    parser.add_argument('--audio-engine', choices=('default', 'hle'), default='default',
                        help='select the experimental HLE path for the same DSP/DMA oracle')
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--capture', action='store_true')
    options = parser.parse_args()
    for field in ('emulator', 'iso', 'config', 'output'):
        setattr(options, field, getattr(options, field).resolve())
    raise SystemExit(run(options))
