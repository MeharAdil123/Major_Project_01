/* Byte transport to the host: native USB (USB-Serial-JTAG) or UART0.
 * Chosen at build time (menuconfig "CSI receiver" -> link). */
#include "link.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "sdkconfig.h"

#if CONFIG_RX_LINK_UART
#include "driver/uart.h"
#define LINK_UART UART_NUM_0
#else
#include "driver/usb_serial_jtag.h"
#endif

static SemaphoreHandle_t s_lock;
#if !CONFIG_RX_LINK_UART
static bool s_stalled;             /* last USB write timed out: host not reading */
#endif
static uint8_t s_frame[7 + WIRE_MAX_PAYLOAD];
volatile uint32_t g_link_frames, g_link_drop;

static uint16_t crc16_ccitt(const uint8_t *p, size_t n)
{
    uint16_t crc = 0xFFFF;
    while (n--) {
        crc ^= (uint16_t)(*p++) << 8;
        for (int i = 0; i < 8; i++)
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

void link_init(void)
{
#if CONFIG_RX_LINK_UART
    uart_config_t c = {
        .baud_rate = CONFIG_RX_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(LINK_UART, 256, 32768, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(LINK_UART, &c));
    /* With the console disabled nothing routes UART0 to its pins, so do it here:
     * GPIO43 = U0TXD, GPIO44 = U0RXD, wired to the board's UART/COM port chip. */
    ESP_ERROR_CHECK(uart_set_pin(LINK_UART, CONFIG_RX_UART_TX_GPIO, CONFIG_RX_UART_RX_GPIO,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
#else
    usb_serial_jtag_driver_config_t cfg = {.tx_buffer_size = 32768, .rx_buffer_size = 256};
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&cfg));
#endif
    s_lock = xSemaphoreCreateMutex();
}

int link_send2(uint8_t type, const void *a, size_t alen, const void *b, size_t blen)
{
    size_t len = alen + blen;
    if (len > WIRE_MAX_PAYLOAD) return -1;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    uint8_t *f = s_frame;
    f[0] = 0xA5; f[1] = 0x5A; f[2] = type;
    f[3] = (uint8_t)(len & 0xFF); f[4] = (uint8_t)(len >> 8);
    if (alen) memcpy(f + 5, a, alen);
    if (blen) memcpy(f + 5 + alen, b, blen);
    uint16_t crc = crc16_ccitt(f + 2, 3 + len);
    f[5 + len] = (uint8_t)(crc & 0xFF);
    f[6 + len] = (uint8_t)(crc >> 8);
    size_t total = 7 + len;
#if CONFIG_RX_LINK_UART
    int n = uart_write_bytes(LINK_UART, f, total);       /* waits for ring-buffer space */
#else
    /* If the PC is not reading, the USB buffer fills and every write would wait.
     * After one timed-out write, stop waiting (drop instantly) until a write
     * succeeds again, so the rest of the firmware (LED, stats) keeps running. */
    int n = usb_serial_jtag_write_bytes(f, total, s_stalled ? 0 : pdMS_TO_TICKS(20));
    s_stalled = (n != (int)total);
#endif
    xSemaphoreGive(s_lock);
    if (n == (int)total) { g_link_frames++; return 0; }
    g_link_drop++;          /* partial frame: the host rejects it by CRC */
    return -1;
}

int link_send(uint8_t type, const void *p, size_t len) { return link_send2(type, p, len, NULL, 0); }

const char *link_name(void)
{
#if CONFIG_RX_LINK_UART
    return "uart";
#else
    return "usb_jtag";
#endif
}
