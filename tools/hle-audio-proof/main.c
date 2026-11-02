/* SPDX-License-Identifier: Unlicense */
/* Public deterministic stereo VP stimulus, no copyrighted audio. */
#include <hal/debug.h>
#include <hal/video.h>
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stdint.h>
#include <string.h>

#define APU 0xfe800000u
#define MAXRAM 0x03ffafffu
#define VOICE 64u
#define LOOP_FRAMES 4000u

static uint32_t read_reg(unsigned offset)
{
    return *(volatile uint32_t *)(APU + offset);
}

static void write_reg(unsigned offset, uint32_t value)
{
    *(volatile uint32_t *)(APU + offset) = value;
}

static void *alloc(unsigned bytes)
{
    return MmAllocateContiguousMemoryEx(bytes, 0, MAXRAM, 4096,
                                       PAGE_READWRITE | PAGE_NOCACHE);
}

static uint32_t physical(void *p)
{
    return (uint32_t)MmGetPhysicalAddress(p);
}

int main(void)
{
    XVideoSetMode(640, 480, 32, REFRESH_DEFAULT);
    const unsigned tops[] = { 0x2054, 0x2060, 0x206c };
    uint32_t old_engine = read_reg(0x2000);
    if ((old_engine & 0x18) || (read_reg(0x3fffc) & 3) == 3 ||
        (read_reg(0x5fffc) & 3) == 3) {
        debugPrint("HLE audio proof: APU busy\n");
        for (;;) Sleep(1000);
    }
    for (unsigned i = 0; i < 3; i++) {
        uint32_t top = read_reg(tops[i]);
        if (top != 0xffff && (top != 0 || read_reg(0x202c) || read_reg(0x2030))) {
            debugPrint("HLE audio proof: voice list busy\n");
            for (;;) Sleep(1000);
        }
    }
    uint8_t *voices = alloc(256 * 128);
    uint32_t *sge = alloc(4096);
    int16_t *pcm = alloc(4 * 4096);
    uint32_t *dsp_sge = alloc(4096);
    uint32_t *dsp_program = alloc(8192);
    if (!voices || !sge || !pcm || !dsp_sge || !dsp_program) {
        debugPrint("HLE audio proof: allocation failed\n");
        for (;;) Sleep(1000);
    }
    memset(voices, 0, 256 * 128);
    memset(sge, 0, 4096);
    memset(dsp_sge, 0, 4096);
    memset(dsp_program, 0, 8192);
    /* Both DSPs write X:$3f6 then halt when actually executed. The host
     * compares this side-effect sentinel in HLE and legacy modes. */
    const uint32_t program[] = { 0x44f400, 0x123456, 0x447000, 0x0003f6,
                                 0x08f484, 0x000001, 0x0af080, 0x000004 };
    memcpy(dsp_program, program, sizeof(program));
    dsp_sge[0] = physical(dsp_program);
    dsp_sge[2] = physical((uint8_t *)dsp_program + 4096);
    for (unsigned i = 0; i < LOOP_FRAMES; i++) {
        pcm[2 * i] = i % 100 < 50 ? 8192 : -8192;      /* 480 Hz */
        pcm[2 * i + 1] = i % 50 < 25 ? 8192 : -8192;  /* 960 Hz */
    }
    for (unsigned i = 0; i < 4; i++) {
        sge[i * 2] = physical((uint8_t *)pcm + i * 4096);
    }
    uint32_t *voice = (uint32_t *)(voices + VOICE * 128);
    voice[0x00 / 4] = (1 << 5) | (31 << 10) | (31 << 16) | (31 << 21) | (31u << 26);
    voice[0x04 / 4] = 31 | (31 << 5) | (1 << 25) | (1 << 28) |
                      (1u << 30) | (1 << 27) | (1 << 16);
    voice[0x0c / 4] = 0xff000000;
    voice[0x14 / 4] = 0xff000000;
    voice[0x54 / 4] = (1 << 21) | (5 << 24) | (5u << 28);
    voice[0x58 / 4] = 0xff000000;
    voice[0x5c / 4] = 0xff000000 | (LOOP_FRAMES - 1);
#ifdef AUDIO_PROOF_ASYMMETRIC
    voice[0x60 / 4] = 0x180f000f; /* Right: 6 dB attenuation. */
#else
    voice[0x60 / 4] = 0x000f000f;
#endif
    voice[0x64 / 4] = 0xffffffff;
    voice[0x68 / 4] = 0xffffffff;
    voice[0x7c / 4] = 0xffff;
    for (unsigned i = 0; i < 3; i++) {
        write_reg(tops[i], 0xffff);
    }
    write_reg(0x202c, physical(voices));
    write_reg(0x2030, physical(sge));
    write_reg(0x1100, read_reg(0x1100) & ~0xe0u);
    write_reg(0x20200, 0);
    write_reg(0x20204, 0);
    write_reg(0x2040, physical(dsp_sge));
    write_reg(0x2048, physical(dsp_sge));
    write_reg(0x20d4, 1);
    write_reg(0x20dc, 1);
    write_reg(0x30fd8, 0);
    write_reg(0x50fd8, 0);
    write_reg(0x3fffc, 3);
#ifndef AUDIO_PROOF_GP_ONLY
    write_reg(0x5fffc, 3);
#endif
    write_reg(tops[0], VOICE);
    write_reg(0x2000, (old_engine & ~0x18u) | 0x8);
    uint32_t before = read_reg(0x200c);
    for (unsigned i = 0; i < 3000 && read_reg(0x200c) - before < 1024; i++) {
        Sleep(1);
    }
    if (read_reg(0x200c) - before < 1024) {
        debugPrint("HLE audio proof: voice did not advance\n");
        write_reg(0x30fc4, 0xbad);
    } else {
        debugPrint("HLE audio proof: stereo 480/960 Hz square waves active\n");
        write_reg(0x30fc4, 0x600d);
    }
    /* Keep all buffers alive until emulator exit. */
    for (;;) Sleep(1000);
}
