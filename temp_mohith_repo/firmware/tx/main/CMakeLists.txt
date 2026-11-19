idf_component_register(SRCS "main.c"
                       REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_timer
                                esp_driver_gpio esp_driver_uart esp_app_format esp_rom vfs esp_system)
