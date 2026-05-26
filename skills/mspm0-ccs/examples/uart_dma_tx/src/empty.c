#include "BSP/UART.h"
#include "ti_msp_dl_config.h"


int n = 0;

int main(void)
{
    SYSCFG_DL_init();
    UART_init();

    while (1) {

        n++;
        delay_cycles(80000000);
        UART0_printfDMA("Hello World! %d\n", n);

    }
}

void UART0_IRQHandler(void) {
    switch (DL_UART_getPendingInterrupt(UART_0_INST)) {
        case DL_UART_IIDX_DMA_DONE_TX:
            UART0_DMADoneTxCallback();
            DL_GPIO_togglePins(LED_PORT, LED_PIN_22_PIN);
            break;
        default:
            break;
    }
}
