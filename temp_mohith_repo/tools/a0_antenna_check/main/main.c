/* A0 — antenna-path test for ESP32-S3 boards with BOTH a PCB antenna and a U.FL
 * connector. Answers one question: is the radio actually connected to the U.FL
 * (external antenna), or to the printed PCB antenna?
 *
 * Method: scan nearby Wi-Fi networks repeatedly and average each one's RSSI.
 *   Phase A: external antenna connected.
 *   Press BOOT, unscrew the antenna at the SMA end (NOT the U.FL) within 10 s.
 *   Phase B: antenna removed.
 * If the radio uses the U.FL path, removing the antenna drops RSSI a lot
 * (typically 15–30 dB, weak networks vanish). If it uses the PCB antenna,
 * nothing much changes.
 *
 * Also: prints MAC and flash size, and tests the RGB LED (GPIO from menuconfig,
 * default 48). Output is plain text on the native USB port: idf.py monitor.
 *
 * LED: R,G,B colour check at boot; blue blink = phase A scan; white = unscrew
 * now; magenta blink = phase B scan; verdict: green = U.FL active,
 * red = PCB antenna active, yellow = inconclusive. */
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/rmt_tx.h"
#include "esp_chip_info.h"
#include "esp_event.h"
#include "esp_flash.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#define BOOT_GPIO        GPIO_NUM_0
#define MAX_APS          48
#define MIN_SAMPLES      5
#define LOST_RSSI        (-100)      /* value used for an AP not seen in phase B */
#define SWAP_DELAY_S     10
#define STRONG_RSSI      (-85)      /* only APs at least this strong in phase A count */

/* ---------------------------------------------------------------- RGB LED */
#if CONFIG_A0_LED_WS2812
static rmt_channel_handle_t s_led_chan;
static rmt_encoder_handle_t s_led_enc;

static void led_init(void)
{
    rmt_tx_channel_config_t cc = {
        .gpio_num = CONFIG_A0_LED_GPIO,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,      /* 0.1 us per tick */
        .mem_block_symbols = 64,
        .trans_queue_depth = 4,
    };
    ESP_ERROR_CHECK(rmt_new_tx_channel(&cc, &s_led_chan));
    rmt_bytes_encoder_config_t ec = {           /* WS2812 bit timing */
        .bit0 = {.level0 = 1, .duration0 = 3, .level1 = 0, .duration1 = 9},
        .bit1 = {.level0 = 1, .duration0 = 9, .level1 = 0, .duration1 = 3},
        .flags.msb_first = 1,
    };
    ESP_ERROR_CHECK(rmt_new_bytes_encoder(&ec, &s_led_enc));
    ESP_ERROR_CHECK(rmt_enable(s_led_chan));
}

static void led(uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t grb[3] = {g, r, b};                 /* WS2812 expects G, R, B */
    rmt_transmit_config_t tc = {.loop_count = 0};
    rmt_transmit(s_led_chan, s_led_enc, grb, sizeof(grb), &tc);
    rmt_tx_wait_all_done(s_led_chan, 100);
    vTaskDelay(1);                              /* >50 us low = latch */
}
#else
/* Plain single-colour LED: any colour = on, black = off. */
static void led_init(void)
{
    gpio_reset_pin(CONFIG_A0_LED_GPIO);
    gpio_set_direction(CONFIG_A0_LED_GPIO, GPIO_MODE_OUTPUT);
}

static void led(uint8_t r, uint8_t g, uint8_t b)
{
    gpio_set_level(CONFIG_A0_LED_GPIO, (r | g | b) ? 1 : 0);
}
#endif

/* ---------------------------------------------------------------- AP table */
typedef struct {
    uint8_t bssid[6];
    char ssid[33];
    uint8_t ch;
    int sum[2], n[2];                           /* per phase: A = 0, B = 1 */
} ap_t;

static ap_t s_aps[MAX_APS];
static int s_nap;

static ap_t *ap_get(const wifi_ap_record_t *r)
{
    for (int i = 0; i < s_nap; i++)
        if (!memcmp(s_aps[i].bssid, r->bssid, 6)) return &s_aps[i];
    if (s_nap == MAX_APS) return NULL;
    ap_t *a = &s_aps[s_nap++];
    memset(a, 0, sizeof(*a));
    memcpy(a->bssid, r->bssid, 6);
    strncpy(a->ssid, (const char *)r->ssid, 32);
    a->ch = r->primary;
    return a;
}

static int scan(int phase)
{
    wifi_scan_config_t sc = {.show_hidden = true, .scan_type = WIFI_SCAN_TYPE_ACTIVE,
                             .scan_time.active = {.min = 100, .max = 200}};
    if (esp_wifi_scan_start(&sc, true) != ESP_OK) return 0;
    uint16_t n = 0;
    esp_wifi_scan_get_ap_num(&n);
    static wifi_ap_record_t recs[MAX_APS];
    uint16_t want = n > MAX_APS ? MAX_APS : n;
    esp_wifi_scan_get_ap_records(&want, recs);
    for (int i = 0; i < want; i++) {
        ap_t *a = ap_get(&recs[i]);
        if (a) { a->sum[phase] += recs[i].rssi; a->n[phase]++; }
    }
    if (want > 0)   /* records are sorted strongest first */
        printf("   strongest now: %-20.20s %4d dBm\n",
               recs[0].ssid[0] ? (const char *)recs[0].ssid : "(hidden)", recs[0].rssi);
    return want;
}

static int cmp_int(const void *a, const void *b) { return *(const int *)a - *(const int *)b; }

/* Compare phases; returns verdict 1 = U.FL active, -1 = PCB active, 0 = unsure */
static int report(int scans_b)
{
    int deltas[MAX_APS], nd = 0;
    printf("\n%-20s %3s %8s %8s %7s\n", "SSID", "ch", "A (dBm)", "B (dBm)", "change");
    for (int i = 0; i < s_nap; i++) {
        ap_t *a = &s_aps[i];
        if (a->n[0] < MIN_SAMPLES) continue;   /* need a stable phase-A mean */
        float ma = (float)a->sum[0] / a->n[0];
        /* Weaker APs flicker in and out even with nothing changed; they would
         * read as "lost" and fake a drop. Only reliable ones vote. */
        if (ma < STRONG_RSSI) continue;
        /* An AP seen in A but in fewer than half the B scans has dropped below
         * sensitivity: count it at LOST_RSSI (a lower bound on the drop). */
        float mb = (a->n[1] * 2 >= scans_b) ? (float)a->sum[1] / a->n[1] : LOST_RSSI;
        int d = (int)lroundf(mb - ma);
        deltas[nd++] = d;
        const char *name = a->ssid[0] ? a->ssid : "(hidden)";
        if (mb == LOST_RSSI)   /* drop is at least this much */
            printf("%-20.20s %3u %8.1f %8s %+6d or more\n", name, a->ch, ma, "lost", d);
        else
            printf("%-20.20s %3u %8.1f %8.1f %+6d\n", name, a->ch, ma, mb, d);
    }
    if (nd < 3) {
        printf("Only %d networks stronger than %d dBm: inconclusive. "
               "Put a phone hotspot 2-3 m away and repeat.\n", nd, STRONG_RSSI);
        return 0;
    }
    qsort(deltas, nd, sizeof(int), cmp_int);
    int med = deltas[nd / 2];
    printf("Median change over %d networks: %+d dB\n", nd, med);
    if (med <= -15) { printf("VERDICT: radio uses the U.FL / EXTERNAL antenna. Good.\n"); return 1; }
    if (med >= -5)  { printf("VERDICT: radio uses the PCB antenna. External antenna is NOT connected to the radio.\n"); return -1; }
    printf("VERDICT: inconclusive (-15..-5 dB). Repeat without moving the board or people.\n");
    return 0;
}

static bool boot_pressed(void)
{
    if (gpio_get_level(BOOT_GPIO)) return false;
    vTaskDelay(pdMS_TO_TICKS(30));
    if (gpio_get_level(BOOT_GPIO)) return false;
    while (!gpio_get_level(BOOT_GPIO)) vTaskDelay(pdMS_TO_TICKS(10));
    return true;
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }
    gpio_config_t io = {.pin_bit_mask = 1ULL << BOOT_GPIO, .mode = GPIO_MODE_INPUT,
                        .pull_up_en = GPIO_PULLUP_ENABLE};
    gpio_config(&io);

    vTaskDelay(pdMS_TO_TICKS(1500));            /* give the monitor time to attach */
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    uint32_t flash = 0;
    esp_flash_get_size(NULL, &flash);
    esp_chip_info_t ci;
    esp_chip_info(&ci);
    printf("\n===== A0 antenna-path test v2 =====\n");
    printf("Wi-Fi MAC   %02X:%02X:%02X:%02X:%02X:%02X   <- write this on the board's label\n",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    printf("Chip        %s rev %d.%d, %d cores\n", CONFIG_IDF_TARGET, ci.revision / 100, ci.revision % 100, ci.cores);
    printf("Flash       %" PRIu32 " MB\n", flash >> 20);

    led_init();
    #if CONFIG_A0_LED_WS2812
    printf("LED test (GPIO %d): red, green, blue, 1 s each. Note which colours you see.\n",
           CONFIG_A0_LED_GPIO);
#else
    printf("LED test (GPIO %d): LED on for 3 s. Note whether it lights.\n", CONFIG_A0_LED_GPIO);
#endif
    led(40, 0, 0); vTaskDelay(pdMS_TO_TICKS(1000));
    led(0, 40, 0); vTaskDelay(pdMS_TO_TICKS(1000));
    led(0, 0, 40); vTaskDelay(pdMS_TO_TICKS(1000));
    led(0, 0, 0);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t wc = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wc));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    esp_wifi_set_ps(WIFI_PS_NONE);

    printf("\nPHASE A: antenna CONNECTED. Keep still. After at least %d scans, press BOOT.\n",
           MIN_SAMPLES);
    int phase = 0, scans[2] = {0, 0};
    for (;;) {
        if (boot_pressed()) {
            if (phase == 0 && scans[0] >= MIN_SAMPLES) {
                printf("\n>>> Unscrew the antenna at the SMA end NOW (not the U.FL). "
                       "Phase B starts in %d s.\n", SWAP_DELAY_S);
                led(30, 30, 30);
                vTaskDelay(pdMS_TO_TICKS(SWAP_DELAY_S * 1000));
                led(0, 0, 0);
                phase = 1;
                printf("PHASE B: antenna REMOVED. Results appear after %d scans.\n", MIN_SAMPLES);
            } else if (phase == 0) {
                printf("(need %d phase-A scans first, have %d)\n", MIN_SAMPLES, scans[0]);
            } else {
                printf("\nRESET: reconnect the antenna. Starting again at phase A.\n");
                s_nap = 0; scans[0] = scans[1] = 0; phase = 0;
            }
        }
        if (phase == 0) led(0, 0, 30); else led(30, 0, 30);
        int n = scan(phase);
        led(0, 0, 0);
        scans[phase]++;
        printf("phase %c scan %2d: %2d networks\n", phase ? 'B' : 'A', scans[phase], n);
        if (phase == 1 && scans[1] >= MIN_SAMPLES) {
            int v = report(scans[1]);
            led(v > 0 ? 0 : 40, v < 0 ? 0 : 40, 0);      /* green / red / yellow */
            printf("Keep watching: the table updates every scan. Press BOOT to restart.\n");
            vTaskDelay(pdMS_TO_TICKS(2000));
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
