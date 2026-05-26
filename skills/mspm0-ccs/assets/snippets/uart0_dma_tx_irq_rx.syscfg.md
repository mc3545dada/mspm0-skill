# UART0 DMA TX + IRQ RX SysConfig Snippet

## Use Case

Tianmengxing MSPM0G3507 UART0 at 115200 baud, using PA10 as TX and PA11 as RX. RX is interrupt-driven for newline-terminated PC-to-MCU test frames, and TX uses DMA for MCU-to-PC echo/debug output.

This is a complete UART send/receive smoke-test pattern for agents. Optional ASCII float parsing can be layered on top of the received text frame. It is not a high-throughput DMA RX design.

## Snippet

```js
const UART   = scripting.addModule("/ti/driverlib/UART", {}, false);
const UART1  = UART.addInstance();

UART1.$name                = "UART_0";
UART1.targetBaudRate       = 115200;
UART1.enabledInterrupts    = ["DMA_DONE_TX", "RX"];
UART1.enabledDMATXTriggers = "DL_UART_DMA_INTERRUPT_TX";

UART1.peripheral.rxPin.$assign = "PA11";
UART1.peripheral.txPin.$assign = "PA10";
UART1.txPinConfig.$name        = "ti_driverlib_gpio_GPIOPinGeneric0";
UART1.rxPinConfig.$name        = "ti_driverlib_gpio_GPIOPinGeneric1";

UART1.DMA_CHANNEL_TX.$name       = "DMA_UART0Tx";
UART1.DMA_CHANNEL_TX.addressMode = "b2f";
UART1.DMA_CHANNEL_TX.srcLength   = "BYTE";
UART1.DMA_CHANNEL_TX.dstLength   = "BYTE";

UART1.peripheral.$suggestSolution                = "UART0";
UART1.DMA_CHANNEL_TX.peripheral.$suggestSolution = "DMA_CH0";
```

## Runtime Requirement

Call a user helper after `SYSCFG_DL_init()` to enable the UART interrupt in NVIC:

```c
SYSCFG_DL_init();
UART_init();
```

```c
void UART_init(void) {
    NVIC_ClearPendingIRQ(UART_0_INST_INT_IRQN);
    NVIC_EnableIRQ(UART_0_INST_INT_IRQN);
}
```

The `DMA_DONE_TX` interrupt sets `UART0TxDMADone` back to 1. The `RX` interrupt lets the user callback collect bytes until `\n`.

## Generated Names Observed

```c
#define UART_0_INST              UART0
#define UART_0_INST_INT_IRQN     UART0_INT_IRQn
#define UART_0_INST_DMA_TRIGGER  (DMA_UART0_TX_TRIG)
#define DMA_UART0Tx_CHAN_ID      (0)
```

Always inspect the local generated `ti_msp_dl_config.h`; generated names can change if SysConfig instance names change.
