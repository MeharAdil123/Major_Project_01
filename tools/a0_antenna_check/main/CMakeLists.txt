idf_component_register(SRCS "main.c"
                       REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_driver_rmt esp_driver_gpio spi_flash)
