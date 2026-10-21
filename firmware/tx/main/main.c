/* csi_tx — standalone CSI transmitter for a classic ESP32 (ESP-WROOM-32U).
 *
 * What it does
 *   Broadcasts one ESP-NOW frame every 1/RATE s (default 200 Hz) on a fixed
 *   channel, at a forced PHY rate and bandwidth (default HT40, MCS0 long GI).
 *   Every frame carries a 32-bit sequence number so RX1 and RX2 can be aligned
 *   packet by packet, plus the TX power used, so E1 (power sweep) is
 *   self-documenting.
 *
 * Status (no host needed)
 *   LED (CONFIG_TX_LED_GPIO, default GPIO2):
 *     solid on      starting up
 *     slow blink 1 Hz   transmitting normally
 *     fast blink 5 Hz   radio problem (init failed, rate not forced, or >1 % send errors)
 *
 * USB serial (115200 baud, via the board's CP2102/CH340), plain text lines:
 *   HELLO {json}   at boot and every 10 s: MAC, firmware, radio read-back
 *   STATS {json}   every second: counters and achieved rate
 *   Commands (type and press Enter):
 *     power <dBm>        set TX power now, 2..20 dBm (lost on reboot)
 *     power <dBm> save   set it now AND keep it after reboot / power-off
 *     power default      forget the saved value (boot power = build default)
 *     status             print HELLO now
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_rom_crc.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5, 5, 5)
#error "Build with ESP-IDF v5.5.5 (project pin)"
#endif

/* ------------------------------------------------------------- settings */
#define CHANNEL         CONFIG_TX_CHANNEL
#define RATE_HZ         CONFIG_TX_RATE_HZ
#define PERIOD_US       (1000000 / RATE_HZ)
#define PAYLOAD_BYTES   32
#if CONFIG_TX_HT40
#define BW              WIFI_BW_HT40
#define SECOND          WIFI_SECOND_CHAN_BELOW
#define PHYMODE         WIFI_PHY_MODE_HT40
#define BW_NAME         "HT40"
#else
#define BW              WIFI_BW_HT20
#define SECOND          WIFI_SECOND_CHAN_NONE
#define PHYMODE         WIFI_PHY_MODE_HT20
#define BW_NAME         "HT20"
#endif
#define PHY_RATE        WIFI_PHY_RATE_MCS0_LGI
#define TX_MAGIC        0x31495343u   /* "CSI1" */

/* Payload layout (little-endian). Must match the RX/host parser. */
typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint32_t seq;          /* increments every slot, even if a send fails */
    uint64_t tx_time_us;   /* TX clock */
    uint32_t radio_id;     /* CRC32 of the fixed radio settings */
    uint16_t rate_hz;
    int8_t   tx_power_qdbm;/* power in force for this frame, 0.25 dBm units */
    uint8_t  reserved;
} tx_payload_t;
_Static_assert(sizeof(tx_payload_t) == 24, "payload header must be 24 bytes");

static const uint8_t BCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static const char *TAG = "csi_tx";

/* ------------------------------------------------------------- state */
static volatile uint32_t s_seq, s_sent, s_fail, s_nomem, s_late;
static volatile int8_t s_power_qdbm;
static int8_t s_saved_qdbm = -1;     /* -1 = nothing saved in NVS */
static volatile bool s_radio_ok;
static esp_err_t s_rate_cfg = ESP_FAIL;
static uint32_t s_radio_id;
static char s_mac[18];
static TaskHandle_t s_tx_task;
static uint8_t s_buf[PAYLOAD_BYTES];

/* ------------------------------------------------------------- LED */
typedef enum { LED_START, LED_OK, LED_ERROR } led_mode_t;
static volatile led_mode_t s_led = LED_START;

static void led_task(void *arg)
{
    gpio_reset_pin(CONFIG_TX_LED_GPIO);
    gpio_set_direction(CONFIG_TX_LED_GPIO, GPIO_MODE_OUTPUT);
    bool on = false;
    for (;;) {
        int half_ms;
        switch (s_led) {
        case LED_START: gpio_set_level(CONFIG_TX_LED_GPIO, 1); vTaskDelay(pdMS_TO_TICKS(100)); continue;
        case LED_OK:    half_ms = 500; break;    /* 1 Hz */
        default:        half_ms = 100; break;    /* 5 Hz */
        }
        on = !on;
        gpio_set_level(CONFIG_TX_LED_GPIO, on);
        vTaskDelay(pdMS_TO_TICKS(half_ms));
    }
}

/* ------------------------------------------------------------- transmit */
static void on_tick(void *arg) { xTaskNotifyGive(s_tx_task); }

static void tx_task(void *arg)
{
    tx_payload_t *p = (tx_payload_t *)s_buf;
    memset(s_buf, 0, sizeof(s_buf));
    p->magic = TX_MAGIC;
    p->radio_id = s_radio_id;
    p->rate_hz = RATE_HZ;
    for (;;) {
        uint32_t n = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (n > 1) s_late += n - 1;               /* woke late: no burst catch-up */
        p->seq = s_seq;
        p->tx_time_us = (uint64_t)esp_timer_get_time();
        p->tx_power_qdbm = s_power_qdbm;
        esp_err_t err = esp_now_send(BCAST, s_buf, sizeof(s_buf));
        if (err == ESP_OK) s_sent++;
        else if (err == ESP_ERR_ESPNOW_NO_MEM) s_nomem++;
        else s_fail++;
        s_seq++;
    }
}

/* ------------------------------------------------------------- saved power (NVS) */
static int8_t nvs_load_power(void)
{
    nvs_handle_t h;
    int8_t v = -1;
    if (nvs_open("csi_tx", NVS_READONLY, &h) == ESP_OK) {
        if (nvs_get_i8(h, "pwr_qdbm", &v) != ESP_OK) v = -1;
        nvs_close(h);
    }
    return (v >= 8 && v <= 80) ? v : -1;
}

static esp_err_t nvs_store_power(int8_t v)   /* v < 0 erases */
{
    nvs_handle_t h;
    esp_err_t e = nvs_open("csi_tx", NVS_READWRITE, &h);
    if (e != ESP_OK) return e;
    e = (v < 0) ? nvs_erase_key(h, "pwr_qdbm") : nvs_set_i8(h, "pwr_qdbm", v);
    if (e == ESP_ERR_NVS_NOT_FOUND) e = ESP_OK;
    if (e == ESP_OK) e = nvs_commit(h);
    nvs_close(h);
    return e;
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
    esp_err_t e1 = esp_wifi_set_bandwidth(WIFI_IF_STA, BW);
    esp_err_t e2 = esp_wifi_set_channel(CHANNEL, SECOND);
    s_saved_qdbm = nvs_load_power();
    s_power_qdbm = (s_saved_qdbm > 0) ? s_saved_qdbm : CONFIG_TX_POWER_QDBM;
    esp_err_t e3 = esp_wifi_set_max_tx_power(s_power_qdbm);
    if (e1 || e2 || e3) {
        ESP_LOGE(TAG, "radio config failed: bw=%s ch=%s pwr=%s", esp_err_to_name(e1),
                 esp_err_to_name(e2), esp_err_to_name(e3));
        return ESP_FAIL;
    }
    ESP_ERROR_CHECK(esp_now_init());
    esp_now_peer_info_t peer = {0};
    memcpy(peer.peer_addr, BCAST, 6);
    peer.ifidx = WIFI_IF_STA;
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));
    /* Without this, ESP-NOW broadcasts go out at 1 Mbps 802.11b: no HT-LTF, no 40 MHz. */
    esp_now_rate_config_t rc = {.phymode = PHYMODE, .rate = PHY_RATE, .ersu = false, .dcm = false};
    s_rate_cfg = esp_now_set_peer_rate_config(BCAST, &rc);
    if (s_rate_cfg != ESP_OK) {
        ESP_LOGE(TAG, "esp_now_set_peer_rate_config: %s", esp_err_to_name(s_rate_cfg));
        return ESP_FAIL;
    }
    return ESP_OK;
}

/* ------------------------------------------------------------- reporting */
static void print_hello(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    uint8_t ch = 0; wifi_second_chan_t sec = 0; wifi_bandwidth_t bw = 0; int8_t pwr = 0;
    esp_wifi_get_channel(&ch, &sec);
    esp_wifi_get_bandwidth(WIFI_IF_STA, &bw);
    esp_wifi_get_max_tx_power(&pwr);
    char saved[16];
    if (s_saved_qdbm > 0) snprintf(saved, sizeof(saved), "%.2f", s_saved_qdbm / 4.0);
    else snprintf(saved, sizeof(saved), "null");
    printf("HELLO {\"role\":\"TX\",\"mac\":\"%s\",\"fw\":\"%s\",\"app_version\":\"%s\",\"idf\":\"%s\","
           "\"radio_id\":\"0x%08" PRIX32 "\",\"channel\":%u,\"second\":%d,\"bw\":%d,\"bw_cfg\":\"%s\","
           "\"phy_rate\":\"MCS0_LGI\",\"rate_cfg\":\"%s\",\"rate_hz\":%d,\"payload\":%d,"
           "\"tx_power_dbm\":%.2f,\"saved_power_dbm\":%s,\"radio_ok\":%s}\n",
           s_mac, app->project_name, app->version, esp_get_idf_version(), s_radio_id,
           ch, (int)sec, (int)bw, BW_NAME, esp_err_to_name(s_rate_cfg), RATE_HZ, PAYLOAD_BYTES,
           pwr / 4.0, saved, s_radio_ok ? "true" : "false");
}

static void set_power(float dbm, bool save)
{
    int q = (int)(dbm * 4 + (dbm >= 0 ? 0.5f : -0.5f));
    if (q < 8 || q > 80) {
        printf("ERR power must be 2..20 dBm\n");
        return;
    }
    esp_err_t e = esp_wifi_set_max_tx_power((int8_t)q);
    int8_t got = 0;
    esp_wifi_get_max_tx_power(&got);
    s_power_qdbm = got;
    printf("OK power asked %.2f dBm, set %.2f dBm (%s)\n", q / 4.0, got / 4.0, esp_err_to_name(e));
    if (save) {
        esp_err_t se = nvs_store_power(got);
        if (se == ESP_OK) s_saved_qdbm = got;
        printf("%s saved %.2f dBm for next boot (%s)\n", se == ESP_OK ? "OK" : "ERR",
               got / 4.0, esp_err_to_name(se));
    }
}

static void console_task(void *arg)
{
    char line[64];
    for (;;) {
        if (!fgets(line, sizeof(line), stdin)) { vTaskDelay(pdMS_TO_TICKS(50)); continue; }
        line[strcspn(line, "\r\n")] = 0;
        if (!strcmp(line, "power default")) {
            esp_err_t se = nvs_store_power(-1);
            if (se == ESP_OK) s_saved_qdbm = -1;
            printf("%s boot power back to build default %.2f dBm (%s); current power unchanged\n",
                   se == ESP_OK ? "OK" : "ERR", CONFIG_TX_POWER_QDBM / 4.0, esp_err_to_name(se));
        } else if (!strncmp(line, "power ", 6)) {
            set_power(strtof(line + 6, NULL), strstr(line + 6, "save") != NULL);
        } else if (!strcmp(line, "status")) {
            print_hello();
        } else if (line[0]) {
            printf("ERR unknown '%s'. Commands: power <2..20> [save], power default, status\n", line);
        }
    }
}

void app_main(void)
{
    xTaskCreate(led_task, "led", 2048, NULL, 2, NULL);
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }

    /* Blocking line input on the USB-UART console. */
    ESP_ERROR_CHECK(uart_driver_install(CONFIG_ESP_CONSOLE_UART_NUM, 256, 0, 0, NULL, 0));
    uart_vfs_dev_use_driver(CONFIG_ESP_CONSOLE_UART_NUM);
    uart_vfs_dev_port_set_rx_line_endings(CONFIG_ESP_CONSOLE_UART_NUM, ESP_LINE_ENDINGS_CR);

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(s_mac, sizeof(s_mac), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    /* radio_id fingerprints the settings that must not change during a study
     * (power is excluded: it is sent per frame instead). */
    char fp[96];
    int n = snprintf(fp, sizeof(fp), "ch=%d;bw=%s;rate=MCS0_LGI;hz=%d;payload=%d",
                     CHANNEL, BW_NAME, RATE_HZ, PAYLOAD_BYTES);
    s_radio_id = esp_rom_crc32_le(0, (const uint8_t *)fp, n);

    s_radio_ok = (radio_start() == ESP_OK);
    if (s_radio_ok) {
        xTaskCreatePinnedToCore(tx_task, "tx", 4096, NULL, configMAX_PRIORITIES - 2, &s_tx_task, 1);
        const esp_timer_create_args_t ta = {.callback = on_tick, .name = "tx_tick"};
        esp_timer_handle_t t;
        ESP_ERROR_CHECK(esp_timer_create(&ta, &t));
        ESP_ERROR_CHECK(esp_timer_start_periodic(t, PERIOD_US));
    }
    s_led = s_radio_ok ? LED_OK : LED_ERROR;
    xTaskCreate(console_task, "console", 3072, NULL, 3, NULL);
    print_hello();

    uint32_t last_sent = 0, last_bad = 0, k = 0;
    int64_t last_t = esp_timer_get_time();
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        int64_t now = esp_timer_get_time();
        uint32_t sent = s_sent, bad = s_fail + s_nomem;
        float rate = (sent - last_sent) * 1e6f / (float)(now - last_t);
        uint32_t d_bad = bad - last_bad;
        if (s_radio_ok)   /* >1 % errors in the last second: show the error pattern */
            s_led = (d_bad * 100 > (sent - last_sent + d_bad)) ? LED_ERROR : LED_OK;
        printf("STATS {\"t_s\":%.1f,\"seq\":%" PRIu32 ",\"rate\":%.1f,\"sent\":%" PRIu32
               ",\"fail\":%" PRIu32 ",\"nomem\":%" PRIu32 ",\"late\":%" PRIu32
               ",\"tx_power_dbm\":%.2f,\"heap\":%u}\n",
               now / 1e6, s_seq, rate, sent, s_fail, s_nomem, s_late, s_power_qdbm / 4.0,
               (unsigned)esp_get_free_heap_size());
        last_sent = sent; last_bad = bad; last_t = now;
        if (++k % 10 == 0) print_hello();
    }
}
