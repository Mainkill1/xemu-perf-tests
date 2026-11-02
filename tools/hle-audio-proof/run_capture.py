#!/usr/bin/env python3
"""Run the audible public fixture into a private PulseAudio null sink on Linux."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import tomllib
from analyze_capture import analyze

spec = importlib.util.spec_from_file_location('proof_runner', Path(__file__).resolve().parent.parent / 'dsp-io-proof/run_guest.py')
proof_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof_runner)


def process_sample(pid):
    # stat comm is parenthesized and can contain spaces; field 3 starts after it.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    status = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
    return {'cpu_ticks': int(fields[11]) + int(fields[12]),
            'rss_kib': int(status['VmRSS'].split()[0]),
            'peak_rss_kib': int(status['VmHWM'].split()[0])}


def run(args):
    args.output.mkdir(mode=0o700)
    private = args.output / 'private'
    private.mkdir(mode=0o700)
    report = {'status': 'INCOMPLETE', 'engine': args.engine, 'iso_sha256': proof_runner.sha(args.iso),
              'emulator_sha256': proof_runner.sha(args.emulator_binary or args.emulator)}
    env = os.environ.copy()
    # Select the SDL3 Pulse backend explicitly for the isolated sink.
    env.update(XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}', SDL_AUDIO_DRIVER='pulseaudio')
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
    config = tomllib.loads(args.config.read_text())
    files = config['sys']['files']
    for key in ('bootrom_path', 'flashrom_path', 'eeprom_path', 'hdd_path'):
        target = private / key
        subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(files[key]), str(target)], check=True)
        files[key] = str(target)
    settings = ['[general]', 'show_welcome = false', '[audio]', f'engine = {args.engine}',
                'use_dsp = false', 'use_dsp_jit = true', '[net]', 'enable = false', '[sys.files]']
    settings += [key + ' = ' + json.dumps(files[key]) for key in
                 ('bootrom_path', 'flashrom_path', 'eeprom_path', 'hdd_path')]
    cfg = private / 'xemu.toml'
    cfg.write_text('\n'.join(settings) + '\n')
    sink = 'xemu_hle_proof_' + str(os.getpid())
    module = None
    emulator = recorder = qmp = None
    try:
        module = subprocess.check_output(['pactl', 'load-module', 'module-null-sink',
                                          f'sink_name={sink}', 'rate=48000', 'channels=2'],
                                         text=True, env=env).strip()
        if not module.isdecimal():
            raise ValueError('invalid null-sink module identity')
        env['PULSE_SINK'] = sink
        with (args.output / 'capture.s16le').open('wb') as audio, (private / 'emulator.log').open('wb') as log:
            recorder = subprocess.Popen(['parec', '--raw', '--format=s16le', '--rate=48000', '--channels=2',
                                         '--device=' + sink + '.monitor'], stdout=audio, stderr=log, env=env)
            qmp_path = args.output / 'qmp.sock'
            emulator = subprocess.Popen([str(args.emulator), '-config_path', str(cfg), '-dvd_path', str(args.iso),
                                         '-qmp', f'unix:{qmp_path},server=on,wait=off'],
                                        env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + args.timeout
            while not qmp_path.exists() and time.monotonic() < deadline and emulator.poll() is None:
                time.sleep(.1)
            qmp = proof_runner.Qmp(qmp_path)
            marker = 0
            while time.monotonic() < deadline and emulator.poll() is None:
                try:
                    marker = qmp.words(0xfe830fc4, 1)[0]
                except ValueError as error:
                    if 'Cannot access memory' not in str(error):
                        raise
                if marker in (0x600d, 0xbad):
                    break
                time.sleep(.1)
            report['guest_marker'] = marker
            if marker != 0x600d:
                raise ValueError('voice fixture did not report progress')
            gp_sentinel = qmp.words(0xfe830fd8, 1)[0]
            ep_sentinel = qmp.words(0xfe850fd8, 1)[0]
            expected_sentinel = 0 if args.engine == 2 else 0x123456
            report.update(gp_sentinel=gp_sentinel, ep_sentinel=ep_sentinel,
                          expected_dsp_sentinel=expected_sentinel)
            if gp_sentinel != expected_sentinel or ep_sentinel != expected_sentinel:
                report['status'] = 'FAIL'
                raise ValueError('DSP execution sentinel mismatch')
            sinks = subprocess.check_output(['pactl', 'list', 'short', 'sinks'], text=True, env=env)
            matches = [line.split('\t')[0] for line in sinks.splitlines() if '\t' + sink + '\t' in line]
            if len(matches) != 1:
                raise ValueError('private sink missing')
            inputs = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sink-inputs'], text=True, env=env))
            owned = [entry for entry in inputs
                     if str(entry.get('properties', {}).get('application.process.id')) == str(emulator.pid)]
            if not owned:
                raise ValueError('no audio stream belonging to the emulator process')
            for entry in owned:
                subprocess.run(['pactl', 'move-sink-input', str(entry['index']), sink], check=True, env=env)
            inputs = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sink-inputs'], text=True, env=env))
            report['private_sink_stream_count'] = sum(str(entry.get('sink')) == matches[0] and
                                                       str(entry.get('properties', {}).get('application.process.id')) == str(emulator.pid)
                                                       for entry in inputs)
            if not report['private_sink_stream_count']:
                raise ValueError('emulator has no stream on private sink')
            before = process_sample(emulator.pid)
            start = time.monotonic_ns()
            time.sleep(args.capture_seconds)
            elapsed = (time.monotonic_ns() - start) / 1e9
            after = process_sample(emulator.pid)
            cpu_seconds = (after['cpu_ticks'] - before['cpu_ticks']) / os.sysconf('SC_CLK_TCK')
            report['performance'] = {'wall_seconds': elapsed, 'cpu_seconds': cpu_seconds,
                                     'cpu_percent_one_core': cpu_seconds / elapsed * 100,
                                     'rss_before_kib': before['rss_kib'], 'rss_after_kib': after['rss_kib'],
                                     'peak_rss_kib': after['peak_rss_kib'],
                                     'cpu_tick_hz': os.sysconf('SC_CLK_TCK'),
                                     'scope': 'whole emulator during fixed guest tone; not per-DSP or game FPS'}
            if recorder.poll() is not None or emulator.poll() is not None:
                raise ValueError('recorder or emulator exited during capture')
            report['status'] = 'CAPTURED'
    except (OSError, ValueError, TypeError, KeyError, EOFError, subprocess.SubprocessError) as error:
        report.update(reason=type(error).__name__, detail=str(error))
    finally:
        if qmp is not None:
            try:
                qmp.call('quit')
            except (OSError, ValueError, EOFError):
                pass
        if emulator is not None and emulator.poll() is None:
            try:
                emulator.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(emulator.pid, signal.SIGKILL)
                emulator.wait()
        if recorder is not None and recorder.poll() is None:
            recorder.terminate()
            recorder.wait(timeout=5)
        if module is not None and module.isdecimal():
            subprocess.run(['pactl', 'unload-module', module], env=env, check=False)
        # This run owns this copy; preserve logs/config and free the 1+ GiB HDD copy.
        (private / 'hdd_path').unlink(missing_ok=True)
        if report['status'] == 'CAPTURED':
            capture = args.output / 'capture.s16le'
            report['audio'] = analyze(capture.read_bytes())
            report['capture_sha256'] = proof_runner.sha(capture)
            report['status'] = report['audio']['status']
        (args.output / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--emulator-binary', type=Path)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', type=int, choices=(0, 1, 2), default=2)
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--capture-seconds', type=float, default=4)
    raise SystemExit(run(parser.parse_args()))
