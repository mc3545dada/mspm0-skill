# UART0 Blocking TX Example

Minimal reference for sending text from the LCKFB Tianmengxing MSPM0G3507 board to a PC over UART0.

This example is based on the verified `26testproject4` UART smoke test. It is not a complete CCS import project. It is an agent-readable reference showing the `.syscfg` and C patterns that were verified on real hardware.

## Clock Note

This example uses the 80 MHz clock-tree pattern summarized in `../../references/hardware_validation_notes.md`:

- CPUCLK: 80 MHz
- HFXT: 40 MHz input on PA5 / PA6
- SYSPLL: enabled
- ULPCLK divider: 2
- MFCLK gate: enabled

This differs from the older `empty_project` and `led_blink` examples, which are 32 MHz baseline examples. In actual Tianmengxing projects, 80 MHz is a common configuration, especially before UART, motor, PID, and timing-sensitive work.

## UART Setup

- UART instance: UART0
- TX: PA10
- RX: PA11
- Baud rate: 115200
- Data format: 8N1
- Observed PC adapter: CH340 on COM6

The verified generated header contained:

```c
#define UART_0_INST            UART0
#define UART_0_INST_FREQUENCY  40000000
#define GPIO_UART_0_TX_PIN     DL_GPIO_PIN_10
#define GPIO_UART_0_RX_PIN     DL_GPIO_PIN_11
#define UART_0_BAUD_RATE       (115200)
```

## Files

- `example.syscfg`: 80 MHz clock tree, PB22 LED, and UART0 TX/RX configuration
- `src/main.c`: blocking UART string transmit plus PB22 blink
- `manifest.json`: machine-readable summary for example selection

## PC-Side Test

Close VOFA+ or any other program occupying the serial port, then run:

```powershell
python scripts\serial_console.py --list
python scripts\serial_console.py -p COM6 -b 115200 --timestamp --duration 10
```

Expected output:

```text
Hello World! 316
Hello World! 317
```

## Agent Notes

- Treat this as a blocking TX smoke test only.
- Do not assume this is the final DMA / variable-length receive solution.
- Rebuild after `.syscfg` edits and inspect the local generated `ti_msp_dl_config.h`.
- For automated flashing after 80 MHz clock-tree changes, use DSLite System Reset: `-r 2 -u`.
