# UART DMA TX + IRQ RX SysConfig Snippet

## Use Case

Tianmengxing MSPM0G3507 UART0 at 115200 baud, using PA10 as TX and PA11 as RX. RX is interrupt-driven for newline-terminated PC-to-MCU test frames, and TX uses DMA for MCU-to-PC echo/debug output. The full `uart_dma_tx_irq_rx` example also includes UART1 on PB6/PB7 with DMA_CH1.

This is a complete UART send/receive smoke-test pattern for agents. Optional ASCII float parsing can be layered on top of the received text frame. It is not a high-throughput DMA RX design.

## Snippet

```js
const UART   = scripting.addModule("/ti/driverlib/UART", {}, false);
const UART1  = UART.addInstance();
const UART2  = UART.addInstance();

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

UART2.$name                = "UART_1";
UART2.targetBaudRate       = 115200;
UART2.enabledInterrupts    = ["DMA_DONE_TX", "RX"];
UART2.enabledDMATXTriggers = "DL_UART_DMA_INTERRUPT_TX";

UART2.peripheral.rxPin.$assign = "PB7";
UART2.peripheral.txPin.$assign = "PB6";
UART2.txPinConfig.$name        = "ti_driverlib_gpio_GPIOPinGeneric2";
UART2.rxPinConfig.$name        = "ti_driverlib_gpio_GPIOPinGeneric3";

UART2.DMA_CHANNEL_TX.$name       = "DMA_UART1Tx";
UART2.DMA_CHANNEL_TX.addressMode = "b2f";
UART2.DMA_CHANNEL_TX.srcLength   = "BYTE";
UART2.DMA_CHANNEL_TX.dstLength   = "BYTE";

UART2.peripheral.$suggestSolution                = "UART1";
UART2.DMA_CHANNEL_TX.peripheral.$suggestSolution = "DMA_CH1";
```

## Runtime Requirement

Call a user helper after `SYSCFG_DL_init()` to bind the generated SysConfig instance, start RX, and enable the UART interrupt in NVIC:

```c
static UART_Context *uart0;
static UART_Context *uart1;

SYSCFG_DL_init();
uart0 = UART_init(UART_0_INST, UART_RX_MODE_ISR_CALLBACK, UART_RxCompleteCallback);
uart1 = UART_init(UART_1_INST, UART_RX_MODE_POLL, UART_RxCompleteCallback);
```

The `DMA_DONE_TX` interrupt calls `UART_DMADoneTxCallback(UART_x_INST)` to mark TX DMA idle again. The `RX` interrupt calls `UART_RxIRQHandler(UART_x_INST)`, which either invokes the frame callback in ISR mode, records the frame for `UART_poll()` in poll mode, or discards RX bytes in TX-only mode.

## Generated Names Observed

```c
#define UART_0_INST              UART0
#define UART_0_INST_INT_IRQN     UART0_INT_IRQn
#define UART_0_INST_DMA_TRIGGER  (DMA_UART0_TX_TRIG)
#define DMA_UART0Tx_CHAN_ID      (0)
#define UART_1_INST              UART1
#define UART_1_INST_INT_IRQN     UART1_INT_IRQn
#define UART_1_INST_DMA_TRIGGER  (DMA_UART1_TX_TRIG)
#define DMA_UART1Tx_CHAN_ID      (1)
```

Always inspect the local generated `ti_msp_dl_config.h`; generated names can change if SysConfig instance names change.
