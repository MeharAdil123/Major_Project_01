/* csi_rx wire protocol v2. Mirror: host/csiwire.py (and host/rx_check.py).
 * Frame: A5 5A | type u8 | len u16 | payload | crc16 (CCITT-FALSE over type,len,payload)
 * All integers little-endian. */
#pragma once
#include <stdint.h>

#define WIRE_PROTO_VERSION  2
#define WIRE_T_HELLO        0x01   /* JSON */
#define WIRE_T_STATS        0x02   /* JSON */
#define WIRE_T_CSI          0x10   /* csi_rec_hdr_t + int8 csi[csi_len] */
#define WIRE_MAX_PAYLOAD    2048

#define CSI_F_SEQ_VALID         (1u << 0)  /* our TX payload found */
#define CSI_F_RADIO_MISMATCH    (1u << 1)  /* TX radio_id differs from the expected one */
#define CSI_F_FIRST_WORD_INVALID (1u << 2)
#define CSI_F_SMOOTHING         (1u << 3)
#define CSI_F_NOT_SOUNDING      (1u << 4)
#define CSI_F_AGGREGATION       (1u << 5)
#define CSI_F_STBC              (1u << 6)
#define CSI_F_SGI               (1u << 7)
#define CSI_F_FEC_LDPC          (1u << 8)

typedef struct __attribute__((packed)) {
    uint8_t  version;           /* 2 */
    uint8_t  rx_id;             /* 1 or 2 */
    uint16_t flags;
    uint32_t seq;               /* TX sequence number (restarts at 0 when TX reboots) */
    uint64_t tx_time_us;        /* TX clock */
    uint64_t rx_time_us;        /* RX clock, in the CSI callback */
    uint32_t rx_ctrl_ts;        /* RX MAC timestamp, us */
    uint32_t radio_id;          /* from the TX payload */
    uint16_t mac_seq;           /* 802.11 sequence number */
    int8_t   rssi;
    int8_t   noise_floor;
    int8_t   tx_power_qdbm;     /* TX power for this frame, 0.25 dBm units */
    uint8_t  rate;
    uint8_t  sig_mode;          /* 0 non-HT, 1 HT */
    uint8_t  mcs;
    uint8_t  cwb;               /* 0 = 20 MHz, 1 = 40 MHz */
    uint8_t  channel;
    uint8_t  secondary_channel; /* 0 none, 1 above, 2 below */
    uint8_t  reserved;
    uint16_t sig_len;
    uint16_t csi_len;
} csi_rec_hdr_t;
_Static_assert(sizeof(csi_rec_hdr_t) == 48, "csi_rec_hdr_t must be 48 bytes");

/* Payload sent by csi_tx (first 24 bytes of the ESP-NOW body). */
#define TX_MAGIC 0x31495343u    /* "CSI1" */
typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint32_t seq;
    uint64_t tx_time_us;
    uint32_t radio_id;
    uint16_t rate_hz;
    int8_t   tx_power_qdbm;
    uint8_t  reserved;
} tx_payload_t;
_Static_assert(sizeof(tx_payload_t) == 24, "tx_payload_t must be 24 bytes");
