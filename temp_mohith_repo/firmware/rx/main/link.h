#pragma once
#include <stddef.h>
#include <stdint.h>
#include "csi_wire.h"

void link_init(void);
int  link_send(uint8_t type, const void *payload, size_t len);
int  link_send2(uint8_t type, const void *a, size_t alen, const void *b, size_t blen);
const char *link_name(void);
extern volatile uint32_t g_link_frames, g_link_drop;
