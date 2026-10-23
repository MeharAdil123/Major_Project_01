idf_component_register(SRCS "main.c" "link.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_timer esp_rom
                                esp_driver_rmt esp_driver_uart esp_driver_usb_serial_jtag esp_app_format esp_system)
