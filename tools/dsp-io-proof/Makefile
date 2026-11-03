XBE_TITLE = DSP\ input-output\ proof
GEN_XISO = dsp-io-proof.iso
SRCS = $(CURDIR)/main.c
ifndef NXDK_DIR
$(error Set NXDK_DIR to your built nxdk checkout)
endif
CFLAGS += -O2 -Wall -Wextra
ifdef DSP_PROOF_CIRCULAR
CFLAGS += -DDSP_PROOF_CIRCULAR=1
endif
ifdef DSP_PROOF_INJECT_OFFSET
CFLAGS += -DDSP_PROOF_INJECT_OFFSET=1
endif
include $(NXDK_DIR)/Makefile
