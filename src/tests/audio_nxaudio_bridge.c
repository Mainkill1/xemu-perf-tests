#include "audio_nxaudio_bridge.h"

#include <nxaudio.h>

#include <stdlib.h>
#include <string.h>
#include <xboxkrnl/xboxkrnl.h>

#define AUDIO_NX_COMPLETION_TIMEOUT_US 2000000U
#define AUDIO_NX_MAX_VOICES 256U
#define AUDIO_NX_3D_VOICES 64U
#define AUDIO_NX_2D_VOICES (AUDIO_NX_MAX_VOICES - AUDIO_NX_3D_VOICES)
#define AUDIO_NX_SAMPLES_PER_FRAME 32U
#define AUDIO_NX_OUTPUT_RATE 48000U

static bool g_audio_nx_initialized;

static bool resolve_format(const AudioNxBridgeRequest *request,
                           nxAudioFormat *format)
{
    memset(format, 0, sizeof(*format));
    format->sample_rate = request->sample_rate_hz;
    format->channels = (uint8_t)request->channels;
    format->type = request->enable_3d ? NX_VOICE_TYPE_3D_STATIC
                                     : NX_VOICE_TYPE_2D_STATIC;

    switch (request->format) {
        case AUDIO_NX_BRIDGE_U8:
            format->bytes_per_sample = 1;
            format->codec = NX_AUDIO_CODEC_PCM;
            return true;
        case AUDIO_NX_BRIDGE_S16:
            format->bytes_per_sample = 2;
            format->codec = NX_AUDIO_CODEC_PCM;
            return true;
        case AUDIO_NX_BRIDGE_S24_B32:
            // nxdk-audio uses bytes_per_sample=3 to select S24 in B32.
            format->bytes_per_sample = 3;
            format->codec = NX_AUDIO_CODEC_PCM;
            return true;
        case AUDIO_NX_BRIDGE_S32:
            format->bytes_per_sample = 4;
            format->codec = NX_AUDIO_CODEC_PCM;
            return true;
        case AUDIO_NX_BRIDGE_ADPCM:
            // Ignored by the ADPCM format helpers.
            format->bytes_per_sample = 2;
            format->codec = NX_AUDIO_CODEC_ADPCM;
            return true;
    }
    return false;
}

static bool wait_for_all_stopped(nxAudioVoice *voices, uint32_t count)
{
    uint32_t remaining = AUDIO_NX_COMPLETION_TIMEOUT_US;
    while (remaining > 0) {
        uint32_t stopped = 0;
        for (uint32_t i = 0; i < count; ++i) {
            if (nxAudioVoiceGetState(&voices[i]) == NX_STOPPED) {
                ++stopped;
            }
        }
        if (stopped == count) {
            return true;
        }
        KeStallExecutionProcessor(100);
        remaining -= 100;
    }
    return false;
}

static void stall_audio_frames(uint32_t audio_frames)
{
    uint64_t samples =
        (uint64_t)(audio_frames ? audio_frames : 1U) *
        AUDIO_NX_SAMPLES_PER_FRAME;
    uint64_t remaining =
        (samples * 1000000ULL + AUDIO_NX_OUTPUT_RATE - 1) /
        AUDIO_NX_OUTPUT_RATE;
    while (remaining > 0) {
        uint32_t slice = remaining > 1000ULL ? 1000U : (uint32_t)remaining;
        KeStallExecutionProcessor(slice);
        remaining -= slice;
    }
}

bool AudioNxBridgeInitialize(void)
{
    if (g_audio_nx_initialized) {
        return true;
    }
    nxAudioInitParams params = {0};
    g_audio_nx_initialized = nxAudioInit(&params);
    return g_audio_nx_initialized;
}

void AudioNxBridgeShutdown(void)
{
    if (!g_audio_nx_initialized) {
        return;
    }
    nxAudioShutdown();
    g_audio_nx_initialized = false;
}

bool AudioNxBridgeRun(const AudioNxBridgeRequest *request,
                      const void *source_data,
                      uint32_t source_size,
                      AudioNxBridgeResult *result)
{
    if (!result) {
        return false;
    }
    memset(result, 0, sizeof(*result));

    if (!g_audio_nx_initialized || !request || !source_data ||
        source_size == 0 || request->voice_count == 0 ||
        request->channels < 1 || request->channels > 2 ||
        request->sample_rate_hz == 0) {
        result->backend_error = NX_AUDIO_ERR_INVALID_PARAM;
        return false;
    }

    const uint32_t limit =
        request->enable_3d ? AUDIO_NX_3D_VOICES : AUDIO_NX_2D_VOICES;
    if (request->voice_count > limit) {
        result->backend_error = NX_AUDIO_ERR_OUT_OF_VOICES;
        return false;
    }

    nxAudioFormat format;
    if (!resolve_format(request, &format)) {
        result->backend_error = NX_AUDIO_ERR_UNSUPPORTED;
        return false;
    }

    nxAudioVoice *voices =
        (nxAudioVoice *)calloc(request->voice_count, sizeof(nxAudioVoice));
    nxAudioBuffer *buffers =
        (nxAudioBuffer *)calloc(request->voice_count, sizeof(nxAudioBuffer));
    if (!voices || !buffers) {
        free(buffers);
        free(voices);
        result->backend_error = NX_AUDIO_ERR_OUT_OF_MEMORY;
        return false;
    }

    bool ok = true;
    uint32_t created = 0;
    uint32_t started = 0;

    for (uint32_t i = 0; i < request->voice_count; ++i) {
        if (!nxAudioVoiceCreate(&voices[i], &format)) {
            ok = false;
            break;
        }
        ++created;

        if (!nxAudioBufferInitialize(&buffers[i], source_data, source_size) ||
            !nxAudioBufferSubmit(&voices[i], &buffers[i])) {
            ok = false;
            break;
        }

        if (request->loop && !nxAudioVoiceSetLooping(&voices[i], true)) {
            ok = false;
            break;
        }
    }

    if (ok) {
        // Configure all voices before starting any of them so concurrency is
        // not dominated by setup skew.
        for (uint32_t i = 0; i < created; ++i) {
            if (!nxAudioVoiceStart(&voices[i])) {
                ok = false;
                break;
            }
            ++started;
        }
    }

    result->created_voices = created;
    result->started_voices = started;

    if (ok && request->loop) {
        stall_audio_frames(request->audio_frames);
    } else if (ok && !wait_for_all_stopped(voices, started)) {
        ++result->completion_timeouts;
        ok = false;
    }

    for (uint32_t i = 0; i < created; ++i) {
        nxAudioVoiceDestroy(&voices[i]);
    }

    if (request->format == AUDIO_NX_BRIDGE_ADPCM) {
        result->completed_frames_per_voice =
            (source_size / (36U * request->channels)) * 64ULL;
    } else {
        uint32_t bytes_per_sample = 0;
        switch (request->format) {
            case AUDIO_NX_BRIDGE_U8:
                bytes_per_sample = 1;
                break;
            case AUDIO_NX_BRIDGE_S16:
                bytes_per_sample = 2;
                break;
            case AUDIO_NX_BRIDGE_S24_B32:
            case AUDIO_NX_BRIDGE_S32:
                bytes_per_sample = 4;
                break;
            case AUDIO_NX_BRIDGE_ADPCM:
                break;
        }
        if (bytes_per_sample) {
            result->completed_frames_per_voice =
                source_size / (bytes_per_sample * request->channels);
        }
    }

    if (!ok) {
        result->backend_error = (uint32_t)nxAudioGetLastError();
        if (!result->backend_error) {
            result->backend_error = NX_AUDIO_ERR_TIMEOUT;
        }
    }

    free(buffers);
    free(voices);
    return ok;
}
