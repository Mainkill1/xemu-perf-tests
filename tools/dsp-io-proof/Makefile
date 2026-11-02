XBE_TITLE = DSP\ input-output\ proof
GEN_XISO = dsp-io-proof.iso
SRCS = $(CURDIR)/main.c
ifndef NXDK_DIR
$(error Set NXDK_DIR to your built nxdk checkout)
endif
CFLAGS += -O2 -Wall -Wextra
include $(NXDK_DIR)/Makefile
