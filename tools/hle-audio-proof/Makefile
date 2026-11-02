XBE_TITLE = HLE\ audible\ voice\ proof
GEN_XISO = hle-audio-proof.iso
SRCS = $(CURDIR)/main.c
ifndef NXDK_DIR
$(error Set NXDK_DIR to your built nxdk checkout)
endif
CFLAGS += -O2 -Wall -Wextra
ifeq ($(AUDIO_PROOF_ASYMMETRIC),1)
CFLAGS += -DAUDIO_PROOF_ASYMMETRIC
endif
ifeq ($(AUDIO_PROOF_GP_ONLY),1)
CFLAGS += -DAUDIO_PROOF_GP_ONLY
endif
ifeq ($(AUDIO_PROOF_ADPCM),1)
CFLAGS += -DAUDIO_PROOF_ADPCM
endif
include $(NXDK_DIR)/Makefile
