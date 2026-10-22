# Linux host set-up files

## `99-wifi-csi-usb-power.rules` — USB autosuspend off for RX1/RX2 (D-030)

Install it **between recording sessions** (re-plugging resets the receivers):

```bash
sudo install -m 644 setup/linux/99-wifi-csi-usb-power.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules
```

Then unplug and re-plug RX1 and RX2 (the rule fires on `add`). Check: both lines must say `on`:

```bash
for d in /sys/bus/usb/devices/*; do [ -f $d/idVendor ] && case "$(cat $d/idVendor):$(cat $d/idProduct)" in 303a:1001|1a86:55d3) echo "$(cat $d/idVendor):$(cat $d/idProduct) $(cat $d/power/control)";; esac; done
```

Undo: `sudo rm /etc/udev/rules.d/99-wifi-csi-usb-power.rules && sudo udevadm control --reload-rules`.
