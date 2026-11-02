#!/usr/bin/env python3
"""Isolated OpenAL Soft loopback experiment against admitted DSP gain outputs.

Bindings follow public OpenAL and ALC_SOFT_loopback contracts. No mixer source
is copied. This probe neither links OpenAL into xemu nor controls live audio.
"""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import math
import os
from pathlib import Path
import time


def bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, list(arguments)
    return function


def probe(report, library_path):
    if report.get('status') != 'PASS' or not report.get('program_matches'):
        return {'status': 'INCOMPLETE', 'reason': 'admitted DSP guest report required'}
    inputs, expected = report['input_words'], report['output_words']
    if len(inputs) != 64 or len(expected) != 192 or any(type(v) is not int or not 0 <= v <= 0xffffff for v in inputs + expected):
        return {'status': 'INVALID'}
    # Only a loopback device is created; avoid initializing a real audio backend.
    os.environ['ALSOFT_DRIVERS'] = 'null'
    library = C.CDLL(library_path)
    ptr, integer, unsigned, boolean = C.c_void_p, C.c_int, C.c_uint, C.c_char
    extension = bind(library, 'alcIsExtensionPresent', boolean, ptr, C.c_char_p)
    has = lambda device, name: extension(device, name.encode()) != b'\0'
    if not has(None, 'ALC_SOFT_loopback'):
        return {'status': 'UNSUPPORTED', 'reason': 'ALC_SOFT_loopback unavailable'}
    open_device = bind(library, 'alcLoopbackOpenDeviceSOFT', ptr, C.c_char_p)
    close_device = bind(library, 'alcCloseDevice', boolean, ptr)
    create = bind(library, 'alcCreateContext', ptr, ptr, C.POINTER(integer))
    supported = bind(library, 'alcIsRenderFormatSupportedSOFT', boolean, ptr, integer, integer, integer)
    get_integer = bind(library, 'alcGetIntegerv', None, ptr, integer, integer, C.POINTER(integer))
    alc_error = bind(library, 'alcGetError', integer, ptr)
    current = bind(library, 'alcMakeContextCurrent', boolean, ptr)
    destroy = bind(library, 'alcDestroyContext', None, ptr)
    render = bind(library, 'alcRenderSamplesSOFT', None, ptr, ptr, integer)
    al_extension = bind(library, 'alIsExtensionPresent', boolean, C.c_char_p)
    al_string = bind(library, 'alGetString', C.c_char_p, integer)
    al_error = bind(library, 'alGetError', integer)
    gen_buffers = bind(library, 'alGenBuffers', None, integer, C.POINTER(unsigned))
    del_buffers = bind(library, 'alDeleteBuffers', None, integer, C.POINTER(unsigned))
    buffer_data = bind(library, 'alBufferData', None, unsigned, integer, ptr, integer, integer)
    gen_sources = bind(library, 'alGenSources', None, integer, C.POINTER(unsigned))
    del_sources = bind(library, 'alDeleteSources', None, integer, C.POINTER(unsigned))
    source_i = bind(library, 'alSourcei', None, unsigned, integer, integer)
    source_f = bind(library, 'alSourcef', None, unsigned, integer, C.c_float)
    source_play = bind(library, 'alSourcePlay', None, unsigned)
    distance = bind(library, 'alDistanceModel', None, integer)
    routes, identities = [], {}
    for route, gain in enumerate((.5, .5, .25)):
        device = open_device(None)
        context = None
        source, buffer = unsigned(), unsigned()
        if not device:
            raise RuntimeError('loopback device creation failed')
        try:
            if not has(device, 'ALC_SOFT_output_limiter'):
                return {'status': 'UNSUPPORTED', 'reason': 'controllable output limiter required'}
            if supported(device, 48000, 0x1501, 0x1406) == b'\0':
                return {'status': 'UNSUPPORTED', 'reason': '48 kHz stereo float32 required'}
            attributes = [0x1007, 48000, 0x1990, 0x1501, 0x1991, 0x1406, 0x199a, 0]
            has_hrtf = has(device, 'ALC_SOFT_HRTF')
            if has_hrtf:
                attributes += [0x1992, 0]
            attributes += [0]
            context = create(device, (integer * len(attributes))(*attributes))
            if not context or current(context) == b'\0':
                raise RuntimeError('loopback context creation failed')
            for token, expected_value in ((0x1007, 48000), (0x1990, 0x1501),
                                          (0x1991, 0x1406), (0x199a, 0)):
                value = integer()
                get_integer(device, token, 1, C.byref(value))
                if alc_error(device) or value.value != expected_value:
                    raise RuntimeError('loopback format or limiter state mismatch')
            if has_hrtf:
                value = integer()
                get_integer(device, 0x1992, 1, C.byref(value))
                if alc_error(device) or value.value:
                    raise RuntimeError('unexpected HRTF processing')
            if al_extension(b'AL_EXT_FLOAT32') == b'\0' or al_extension(b'AL_SOFT_direct_channels') == b'\0':
                return {'status': 'UNSUPPORTED', 'reason': 'float32 and direct channels required'}
            identities = {'vendor': al_string(0xb001).decode(), 'version': al_string(0xb002).decode(),
                          'renderer': al_string(0xb003).decode()}
            floats = []
            for word in inputs:
                value = word - 0x1000000 if word & 0x800000 else word
                floats += [(-value if route == 1 else value) / 8388608.0, 0.0]
            samples = (C.c_float * 128)(*floats)
            output = (C.c_float * 128)()
            gen_buffers(1, C.byref(buffer))
            gen_sources(1, C.byref(source))
            buffer_data(buffer, 0x10011, samples, C.sizeof(samples), 48000)
            distance(0)
            source_i(source, 0x1033, 1)  # AL_DIRECT_CHANNELS_SOFT
            source_i(source, 0x1009, buffer.value)  # AL_BUFFER
            source_f(source, 0x100a, gain)  # AL_GAIN
            if al_error():
                raise RuntimeError('OpenAL source configuration failed')
            source_play(source)
            start = time.perf_counter_ns()
            render(device, output, 64)
            elapsed = time.perf_counter_ns() - start
            if al_error() or alc_error(device):
                raise RuntimeError('OpenAL render failed')
            actual = [math.floor(output[i * 2] * 8388608.0) & 0xffffff for i in range(64)]
            mismatches = [i for i in range(64) if actual[i] != expected[route * 64 + i]]
            cross_talk = sum(output[i * 2 + 1] != 0.0 for i in range(64))
            first = mismatches[0] if mismatches else None
            routes.append({'name': ('gain_half', 'invert_half', 'gain_quarter')[route],
                           'compared_words': 64, 'mismatching_words': len(mismatches),
                           'right_channel_nonzero': cross_talk, 'render_wall_ns': elapsed,
                           'first_difference': None if first is None else {
                               'sample': first, 'expected': expected[route * 64 + first], 'actual': actual[first]}})
        finally:
            if context:
                if source.value:
                    del_sources(1, C.byref(source))
                if buffer.value:
                    del_buffers(1, C.byref(buffer))
                current(None)
                destroy(context)
            close_device(device)
    result = {'status': 'MISMATCH' if any(r['mismatching_words'] or r['right_channel_nonzero'] for r in routes) else 'BASELINE_MATCH',
              'scope': 'isolated-openal-float-gain-loopback', 'library': identities,
              'routes': routes, 'frequency': 48000, 'output': 'float32-stereo',
              'output_limiter': False, 'hrtf_requested': False, 'live_routing_enabled': False,
              'timing_comparable': False, 'program_sha256': report['program_sha256'],
              'iso_sha256': report['iso_sha256']}
    if Path('/proc/self/maps').exists():
        paths = {line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if 'libopenal.so' in line}
        if len(paths) == 1 and Path(next(iter(paths))).is_file():
            result['library_sha256'] = hashlib.sha256(Path(next(iter(paths))).read_bytes()).hexdigest()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest-report', type=Path, required=True)
    parser.add_argument('--library', default=ctypes.util.find_library('openal'))
    args = parser.parse_args()
    try:
        result = probe(json.loads(args.guest_report.read_text()), args.library)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as error:
        result = {'status': 'INCOMPLETE', 'reason': str(error)}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'BASELINE_MATCH' else 1)
