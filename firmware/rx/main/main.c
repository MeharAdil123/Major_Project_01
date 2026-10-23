/* csi_rx — CSI receiver for ESP32-S3 (repaired YD Sixspan boards).
 *
 * Listens on the TX's channel, keeps only frames from the TX MAC, captures the
 * channel state information (CSI) of each one and streams it to the host as
 * framed binary records (see csi_wire.h). The host tools host/rx_check.py and host/csiwire.py
 * decodes and checks the stream.
 *
 * Link to the host is chosen at build time:
 *   RX1: native USB (USB-Serial-JTAG)
 *   RX2: UART0 through the board's CH343 "UART" port, 2 Mbaud
 *
 * LED (WS2812 on GPIO48): blue = starting, green blink = the radio received TX
 * frames in the last second (whether or not the PC is reading), red blink = none,
 * purple = radio init failed.
 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "driver/rmt_tx.h"
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_rom_crc.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#include "csi_wire.h"
#include "link.h"

#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5, 5, 5)
#error "Build with ESP-IDF v5.5.5 (project pin)"
#endif

#define CHANNEL       CONFIG_RX_CHANNEL
#define CSI_MAX_LEN   768        /* L-LTF 128 + HT-LTF 256 + STBC-HTLTF2 256 = 640 max at HT40 */
#define QUEUE_DEPTH   64
#if CONFIG_RX_HT40
#define BW            WIFI_BW_HT40
#define SECOND        WIFI_SECOND_CHAN_BELOW
#define BW_NAME       "HT40"
#else
#define BW            WIFI_BW_HT20
#define SECOND        WIFI_SECOND_CHAN_NONE
#define BW_NAME       "HT20"
#endif

typedef struct {
    csi_rec_hdr_t hdr;
    int8_t csi[CSI_MAX_LEN];
} item_t;

static QueueHandle_t s_q;
static item_t s_cb_item;                /* CSI callback is single-threaded */
static uint8_t s_tx_mac[6];
static bool s_filter_mac;
static uint32_t s_expected_radio_id;
static char s_mac[18], s_json[1024];
static bool s_radio_ok;

/* counters (one writer each) */
static volatile uint32_t c_from_tx;   /* csi_tx frames received by the radio (before queueing) */
static volatile uint32_t c_cb, c_accepted, c_other_mac, c_no_magic, c_mismatch,
                         c_q_drop, c_oversize, c_last_seq, c_cwb40;
static volatile int32_t  c_last_rssi;

/* ------------------------------------------------------------- LED */
static rmt_channel_handle_t s_led_ch;
static rmt_encoder_handle_t s_led_enc;
static void led_init(void)
{
    rmt_tx_channel_config_t cc = {.gpio_num = CONFIG_RX_LED_GPIO, .clk_src = RMT_CLK_SRC_DEFAULT,
                                  .resolution_hz = 10000000, .mem_block_symbols = 64,
                                  .trans_queue_depth = 4};
    if (rmt_new_tx_channel(&cc, &s_led_ch) != ESP_OK) return;
    rmt_bytes_encoder_config_t ec = {
        .bit0 = {.level0 = 1, .duration0 = 3, .level1 = 0, .duration1 = 9},
        .bit1 = {.level0 = 1, .duration0 = 9, .level1 = 0, .duration1 = 3},
        .flags.msb_first = 1};
    rmt_new_bytes_encoder(&ec, &s_led_enc);
    rmt_enable(s_led_ch);
}
static void led(uint8_t r, uint8_t g, uint8_t b)
{
    if (!s_led_ch) return;
    uint8_t grb[3] = {g, r, b};
    rmt_transmit_config_t tc = {0};
    rmt_transmit(s_led_ch, s_led_enc, grb, 3, &tc);
    rmt_tx_wait_all_done(s_led_ch, 50);
}

/* LED task: reflects what the radio hears, independent of the host link.
 * green blink = TX frames received in the last second, red = none, purple = radio failed. */
static void led_task(void *arg)
{
    uint32_t last = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        uint32_t now = c_from_tx;
        if (!s_radio_ok)     led(20, 0, 20);
        else if (now != last) led(0, 20, 0);
        else                  led(20, 0, 0);
        vTaskDelay(pdMS_TO_TICKS(80));
        if (s_radio_ok) led(0, 0, 0);
        last = now;
    }
}

/* ------------------------------------------------------------- CSI path */
static const tx_payload_t *find_payload(const uint8_t *p, uint16_t n)
{
    if (!p || n < sizeof(tx_payload_t)) return NULL;
    for (uint16_t i = 0; i + sizeof(tx_payload_t) <= n; i++) {
        uint32_t m;
        memcpy(&m, p + i, 4);
        if (m == TX_MAGIC) return (const tx_payload_t *)(p + i);
    }
    return NULL;
}

static void csi_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || !info->buf) return;
    c_cb++;
    if (s_filter_mac && memcmp(info->mac, s_tx_mac, 6) != 0) { c_other_mac++; return; }
    const tx_payload_t *tp = find_payload(info->payload, info->payload_len);
    if (!tp) { c_no_magic++; return; }       /* from TX MAC but not a csi_tx frame */
    c_from_tx++;
    if (info->len > CSI_MAX_LEN) { c_oversize++; return; }

    tx_payload_t t;
    memcpy(&t, tp, sizeof(t));              /* may be unaligned */
    const wifi_pkt_rx_ctrl_t *rc = &info->rx_ctrl;
    csi_rec_hdr_t *h = &s_cb_item.hdr;
    uint16_t f = CSI_F_SEQ_VALID;
    if (t.radio_id != s_expected_radio_id) { f |= CSI_F_RADIO_MISMATCH; c_mismatch++; }
    if (info->first_word_invalid) f |= CSI_F_FIRST_WORD_INVALID;
    if (rc->smoothing)    f |= CSI_F_SMOOTHING;
    if (rc->not_sounding) f |= CSI_F_NOT_SOUNDING;
    if (rc->aggregation)  f |= CSI_F_AGGREGATION;
    if (rc->stbc)         f |= CSI_F_STBC;
    if (rc->sgi)          f |= CSI_F_SGI;
    if (rc->fec_coding)   f |= CSI_F_FEC_LDPC;

    h->version = WIRE_PROTO_VERSION;
    h->rx_id = CONFIG_RX_ID;
    h->flags = f;
    h->seq = t.seq;
    h->tx_time_us = t.tx_time_us;
    h->rx_time_us = (uint64_t)esp_timer_get_time();
    h->rx_ctrl_ts = rc->timestamp;
    h->radio_id = t.radio_id;
    h->mac_seq = info->rx_seq;
    h->rssi = (int8_t)rc->rssi;
    h->noise_floor = (int8_t)rc->noise_floor;
    h->tx_power_qdbm = t.tx_power_qdbm;
    h->rate = rc->rate;
    h->sig_mode = rc->sig_mode;
    h->mcs = rc->mcs;
    h->cwb = rc->cwb;
    h->channel = rc->channel;
    h->secondary_channel = rc->secondary_channel;
    h->reserved = 0;
    h->sig_len = rc->sig_len;
    h->csi_len = info->len;
    memcpy(s_cb_item.csi, info->buf, info->len);

    if (xQueueSend(s_q, &s_cb_item, 0) == pdTRUE) {
        c_accepted++;
        c_last_seq = t.seq;
        c_last_rssi = h->rssi;
        if (rc->cwb) c_cwb40++;
    } else {
        c_q_drop++;
    }
}

/* FW-1: a driver's interrupt is allocated on the core that installs it. app_main runs on
 * core 0, where the Wi-Fi task also runs, so before v2.1 the RX2 UART ISR competed with Wi-Fi
 * (suspected cause of RX2's extra loss, D-012). Install the link from a task on core 1. */
static void link_init_task(void *arg)
{
    link_init();
    xTaskNotifyGive((TaskHandle_t)arg);
    vTaskDelete(NULL);
}

static const char *reset_name(esp_reset_reason_t r)
{
    switch (r) {
    case ESP_RST_POWERON:  return "poweron";
    case ESP_RST_SW:       return "sw";
    case ESP_RST_PANIC:    return "panic";
    case ESP_RST_INT_WDT:  return "int_wdt";
    case ESP_RST_TASK_WDT: return "task_wdt";
    case ESP_RST_WDT:      return "wdt";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_USB:      return "usb";
    case ESP_RST_EXT:      return "ext";
    default:               return "other";
    }
}

static void writer_task(void *arg)
{
    static item_t it;
    for (;;)
        if (xQueueReceive(s_q, &it, portMAX_DELAY) == pdTRUE)
            link_send2(WIRE_T_CSI, &it.hdr, sizeof(it.hdr), it.csi, it.hdr.csi_len);
}

/* ------------------------------------------------------------- radio */
static esp_err_t radio_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_country_code("IN", false));
    ESP_ERROR_CHECK(esp_wifi_set_protocol(WIFI_IF_STA,
                    WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    if (esp_wifi_set_bandwidth(WIFI_IF_STA, BW) != ESP_OK) return ESP_FAIL;
    if (esp_wifi_set_channel(CHANNEL, SECOND) != ESP_OK) return ESP_FAIL;

    wifi_promiscuous_filter_t pf = {.filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT};
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_filter(&pf));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));

    wifi_csi_config_t cc = {
        .lltf_en = true, .htltf_en = true, .stbc_htltf2_en = true,
        .ltf_merge_en = false,        /* keep L-LTF and HT-LTF separate (raw) */
        .channel_filter_en = false,   /* no smoothing across subcarriers (raw) */
        .manu_scale = false, .shift = 0, .dump_ack_en = false,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&cc));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    return ESP_OK;
}

/* ------------------------------------------------------------- reporting */
static void send_hello(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    uint8_t ch = 0; wifi_second_chan_t sec = 0; wifi_bandwidth_t bw = 0;
    esp_wifi_get_channel(&ch, &sec);
    esp_wifi_get_bandwidth(WIFI_IF_STA, &bw);
    int n = snprintf(s_json, sizeof(s_json),
        "{\"type\":\"hello\",\"proto\":%d,\"role\":\"RX\",\"rx_id\":%d,\"mac\":\"%s\","
        "\"link\":\"%s\",\"uart_baud\":%d,\"fw\":\"%s\",\"app_version\":\"%s\",\"idf\":\"%s\","
        "\"tx_mac_filter\":\"%s\",\"expected_radio_id\":\"0x%08" PRIX32 "\","
        "\"channel\":%u,\"second\":%d,\"bw\":%d,\"bw_cfg\":\"%s\",\"radio_ok\":%s,"
        "\"reset\":\"%s\",\"uptime_s\":%" PRId64 ",\"link_core\":1,"
        "\"csi\":{\"lltf\":1,\"htltf\":1,\"stbc_htltf2\":1,\"ltf_merge\":0,\"chan_filter\":0}}",
        WIRE_PROTO_VERSION, CONFIG_RX_ID, s_mac, link_name(),
#if CONFIG_RX_LINK_UART
        CONFIG_RX_UART_BAUD,
#else
        0,
#endif
        app->project_name, app->version, esp_get_idf_version(),
        CONFIG_RX_TX_MAC, s_expected_radio_id, ch, (int)sec, (int)bw, BW_NAME,
        s_radio_ok ? "true" : "false", reset_name(esp_reset_reason()), esp_timer_get_time() / 1000000);
    if (n > 0 && n < (int)sizeof(s_json)) link_send(WIRE_T_HELLO, s_json, n);
}

static void send_stats(void)
{
    int n = snprintf(s_json, sizeof(s_json),
        "{\"type\":\"stats\",\"rx_id\":%d,\"t_us\":%" PRId64 ",\"from_tx\":%" PRIu32 ",\"cb\":%" PRIu32
        ",\"accepted\":%" PRIu32 ",\"other_mac\":%" PRIu32 ",\"no_magic\":%" PRIu32
        ",\"radio_mismatch\":%" PRIu32 ",\"cwb40\":%" PRIu32 ",\"q_drop\":%" PRIu32
        ",\"oversize\":%" PRIu32 ",\"last_seq\":%" PRIu32 ",\"last_rssi\":%" PRId32
        ",\"link_frames\":%" PRIu32 ",\"link_drop\":%" PRIu32 ",\"heap\":%u}",
        CONFIG_RX_ID, esp_timer_get_time(), c_from_tx, c_cb, c_accepted, c_other_mac, c_no_magic,
        c_mismatch, c_cwb40, c_q_drop, c_oversize, c_last_seq, c_last_rssi,
        g_link_frames, g_link_drop, (unsigned)esp_get_free_heap_size());
    if (n > 0 && n < (int)sizeof(s_json)) link_send(WIRE_T_STATS, s_json, n);
}

static bool parse_mac(const char *s, uint8_t out[6])
{
    unsigned v[6];
    if (sscanf(s, "%x:%x:%x:%x:%x:%x", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]) != 6) return false;
    for (int i = 0; i < 6; i++) out[i] = (uint8_t)v[i];
    return true;
}

void app_main(void)
{
    led_init();
    led(0, 0, 20);
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }
    xTaskCreatePinnedToCore(link_init_task, "link_init", 3072, xTaskGetCurrentTaskHandle(), 10, NULL, 1);
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

    uint8_t m[6];
    esp_read_mac(m, ESP_MAC_WIFI_STA);
    snprintf(s_mac, sizeof(s_mac), "%02X:%02X:%02X:%02X:%02X:%02X", m[0], m[1], m[2], m[3], m[4], m[5]);
    s_filter_mac = parse_mac(CONFIG_RX_TX_MAC, s_tx_mac);

    /* Same fingerprint string as csi_tx: a TX built with other settings is flagged. */
    char fp[96];
    int n = snprintf(fp, sizeof(fp), "ch=%d;bw=%s;rate=MCS0_LGI;hz=%d;payload=%d",
                     CHANNEL, BW_NAME, CONFIG_RX_EXPECTED_RATE_HZ, 32);
    s_expected_radio_id = esp_rom_crc32_le(0, (const uint8_t *)fp, n);

    s_q = xQueueCreate(QUEUE_DEPTH, sizeof(item_t));
    xTaskCreatePinnedToCore(writer_task, "csi_wr", 4096, NULL, 5, NULL, 1);
    s_radio_ok = (s_q != NULL) && (radio_start() == ESP_OK);
    xTaskCreate(led_task, "led", 3072, NULL, 3, NULL);
    send_hello();

    uint32_t k = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        send_stats();
        if (++k % 5 == 0) send_hello();
    }
}
