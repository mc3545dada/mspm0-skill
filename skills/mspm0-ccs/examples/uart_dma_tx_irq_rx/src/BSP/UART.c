#include "UART.h"
#include <stdlib.h>

#define UART_DMA_CH_NONE 0xFFu
#define UART_IRQN_NONE   ((IRQn_Type) (-128))

static UART_Context uartContexts[UART_MAX_CONTEXTS];

static uint16_t UART_clampPrintfLength(int len)
{
    if (len <= 0) {
        return 0;
    }

    if (len >= UART_TX_BUF_SIZE) {
        return UART_TX_BUF_SIZE - 1;
    }

    return (uint16_t) len;
}

static UART_Context *UART_allocContext(UART_Regs *uart)
{
    uint8_t i;

    for (i = 0; i < UART_MAX_CONTEXTS; i++) {
        if (uartContexts[i].inst == uart) {
            return &uartContexts[i];
        }
    }

    for (i = 0; i < UART_MAX_CONTEXTS; i++) {
        if (uartContexts[i].inst == 0) {
            uartContexts[i].inst = uart;
            uartContexts[i].rxMode = UART_RX_MODE_NONE;
            uartContexts[i].onFrame = 0;
            uartContexts[i].txDMADone = 1;
            uartContexts[i].rxBuf[0] = '\0';
            uartContexts[i].rxWorkBuf[0] = '\0';
            return &uartContexts[i];
        }
    }

    return 0;
}

UART_Context *UART_getContext(UART_Regs *uart)
{
    return UART_allocContext(uart);
}

static IRQn_Type UART_getIRQn(UART_Regs *uart)
{
#if defined(UART_0_INST) && defined(UART_0_INST_INT_IRQN)
    if (uart == UART_0_INST) {
        return UART_0_INST_INT_IRQN;
    }
#endif
#if defined(UART_1_INST) && defined(UART_1_INST_INT_IRQN)
    if (uart == UART_1_INST) {
        return UART_1_INST_INT_IRQN;
    }
#endif
#if defined(UART_2_INST) && defined(UART_2_INST_INT_IRQN)
    if (uart == UART_2_INST) {
        return UART_2_INST_INT_IRQN;
    }
#endif
#if defined(UART_3_INST) && defined(UART_3_INST_INT_IRQN)
    if (uart == UART_3_INST) {
        return UART_3_INST_INT_IRQN;
    }
#endif
    return UART_IRQN_NONE;
}

static uint8_t UART_getDMATxChannel(UART_Regs *uart)
{
#if defined(UART_0_INST) && defined(DMA_UART0Tx_CHAN_ID)
    if (uart == UART_0_INST) {
        return DMA_UART0Tx_CHAN_ID;
    }
#endif
#if defined(UART_1_INST) && defined(DMA_UART1Tx_CHAN_ID)
    if (uart == UART_1_INST) {
        return DMA_UART1Tx_CHAN_ID;
    }
#endif
#if defined(UART_2_INST) && defined(DMA_UART2Tx_CHAN_ID)
    if (uart == UART_2_INST) {
        return DMA_UART2Tx_CHAN_ID;
    }
#endif
#if defined(UART_3_INST) && defined(DMA_UART3Tx_CHAN_ID)
    if (uart == UART_3_INST) {
        return DMA_UART3Tx_CHAN_ID;
    }
#endif
    return UART_DMA_CH_NONE;
}

UART_Context *UART_init(UART_Regs *uart, UART_RxMode rxMode, UART_FrameCallback onFrame)
{
    IRQn_Type irqn;
    UART_Context *ctx;

    ctx = UART_allocContext(uart);
    if (ctx == 0) {
        return 0;
    }

    ctx->rxMode = rxMode;
    ctx->onFrame = onFrame;
    if (rxMode != UART_RX_MODE_NONE) {
        UART_startReceive(uart);
    } else {
        ctx->rxDone = 0;
        ctx->rxPos = 0;
        ctx->rxLen = 0;
        ctx->rxOvf = 0;
        ctx->rxBuf[0] = '\0';
        ctx->rxWorkBuf[0] = '\0';
    }
    ctx->txDMADone = 1;

    irqn = UART_getIRQn(uart);
    if (irqn == UART_IRQN_NONE) {
        return 0;
    }

    NVIC_ClearPendingIRQ(irqn);
    NVIC_EnableIRQ(irqn);

    return ctx;
}

int UART_sendStr(UART_Regs *uart, const char *str)
{
    int cnt = 0;

    while (*str) {
        DL_UART_transmitDataBlocking(uart, (uint8_t) *str);
        str++;
        cnt++;
    }

    return cnt;
}

int UART_printf(UART_Regs *uart, const char *fmt, ...)
{
    int len;
    va_list args;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        return 0;
    }

    va_start(args, fmt);
    len = vsnprintf(ctx->txBuf, UART_TX_BUF_SIZE, fmt, args);
    va_end(args);
    UART_sendStr(uart, ctx->txBuf);

    return len;
}

void UART_sendStrDMA(UART_Regs *uart, const char *str, uint16_t len)
{
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        return;
    }

    while (!ctx->txDMADone);
    (void) UART_trySendStrDMA(uart, str, len);
}

void UART_printfDMA(UART_Regs *uart, const char *fmt, ...)
{
    int len;
    va_list args;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        return;
    }

    while (!ctx->txDMADone);
    va_start(args, fmt);
    len = vsnprintf(ctx->txBuf, UART_TX_BUF_SIZE, fmt, args);
    va_end(args);
    UART_sendStrDMA(uart, ctx->txBuf, UART_clampPrintfLength(len));
}

uint8_t UART_trySendStrDMA(UART_Regs *uart, const char *str, uint16_t len)
{
    uint8_t dmaChannel;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if ((ctx == 0) || (str == 0) || (len == 0)) {
        return 0;
    }

    if (!ctx->txDMADone) {
        return 0;
    }

    dmaChannel = UART_getDMATxChannel(uart);
    if (dmaChannel == UART_DMA_CH_NONE) {
        uint16_t i;

        for (i = 0; i < len; i++) {
            DL_UART_transmitDataBlocking(uart, (uint8_t) str[i]);
        }
        return 1;
    }

    ctx->txDMADone = 0;
    DL_DMA_setSrcAddr(DMA, dmaChannel, (uint32_t) str);
    DL_DMA_setDestAddr(DMA, dmaChannel, (uint32_t) (&uart->TXDATA));
    DL_DMA_setTransferSize(DMA, dmaChannel, len);
    DL_DMA_enableChannel(DMA, dmaChannel);

    return 1;
}

uint8_t UART_tryPrintfDMA(UART_Regs *uart, const char *fmt, ...)
{
    int len;
    va_list args;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if ((ctx == 0) || (!ctx->txDMADone)) {
        return 0;
    }

    va_start(args, fmt);
    len = vsnprintf(ctx->txBuf, UART_TX_BUF_SIZE, fmt, args);
    va_end(args);

    return UART_trySendStrDMA(uart, ctx->txBuf, UART_clampPrintfLength(len));
}

void UART_startReceive(UART_Regs *uart)
{
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        return;
    }

    ctx->rxPos = 0;
    ctx->rxDone = 0;
    ctx->rxOvf = 0;
    ctx->rxWorkBuf[0] = '\0';
}

uint8_t UART_hasNewFrame(UART_Regs *uart)
{
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        return 0;
    }

    return ctx->rxDone;
}

void UART_clearNewFrame(UART_Regs *uart)
{
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx != 0) {
        ctx->rxDone = 0;
    }
}

uint8_t UART_poll(UART_Regs *uart)
{
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if ((ctx == 0) || (ctx->rxMode != UART_RX_MODE_POLL) || (!ctx->rxDone)) {
        return 0;
    }

    if (ctx->onFrame != 0) {
        ctx->onFrame(ctx);
    }

    return 1;
}

uint16_t UART_parseRxFloats(UART_Regs *uart)
{
    uint16_t i;
    char *cursor;
    char *end;
    float value;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        return 0;
    }

    for (i = 0; i < UART_FLOAT_BUF_SIZE; i++) {
        ctx->floatBuf[i] = 0.0f;
    }
    ctx->floatLen = 0;
    ctx->floatParseError = 0;

    cursor = (char *) ctx->rxBuf;
    while ((*cursor != '\0') && (ctx->floatLen < UART_FLOAT_BUF_SIZE)) {
        while ((*cursor == ' ') || (*cursor == '\t') || (*cursor == ',') || (*cursor == ';')) {
            cursor++;
        }

        if (*cursor == '\0') {
            break;
        }

        end = cursor;
        value = strtof(cursor, &end);
        if (end == cursor) {
            ctx->floatParseError = 1;
            break;
        }

        ctx->floatBuf[ctx->floatLen] = value;
        ctx->floatLen++;
        cursor = end;

        if ((*cursor != '\0') && (*cursor != ' ') && (*cursor != '\t') && (*cursor != ',') && (*cursor != ';')) {
            ctx->floatParseError = 1;
            break;
        }
    }

    return ctx->floatLen;
}

void UART_DMADoneTxCallback(UART_Regs *uart)
{
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx != 0) {
        ctx->txDMADone = 1;
    }
}

uint8_t UART_RxCallback(UART_Regs *uart)
{
    uint8_t rxData;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        (void) DL_UART_receiveData(uart);
        return 0;
    }

    rxData = DL_UART_receiveData(uart);

    if (rxData == '\r') {
        return 0;
    }

    if (rxData == UART_RX_TERMINATOR) {
        uint16_t i;

        ctx->rxWorkBuf[ctx->rxPos] = '\0';
        for (i = 0; i <= ctx->rxPos; i++) {
            ctx->rxBuf[i] = ctx->rxWorkBuf[i];
        }
        ctx->rxLen = ctx->rxPos;
        ctx->rxFrameCount++;
        ctx->rxDone = 1;
        ctx->rxPos = 0;
        ctx->rxWorkBuf[0] = '\0';
        return 1;
    }

    if (ctx->rxPos >= (UART_RX_BUF_SIZE - 1)) {
        uint16_t i;

        ctx->rxWorkBuf[UART_RX_BUF_SIZE - 1] = '\0';
        for (i = 0; i < UART_RX_BUF_SIZE; i++) {
            ctx->rxBuf[i] = ctx->rxWorkBuf[i];
        }
        ctx->rxLen = UART_RX_BUF_SIZE - 1;
        ctx->rxOvf = rxData;
        ctx->rxFrameCount++;
        ctx->rxDone = 1;
        ctx->rxPos = 0;
        ctx->rxWorkBuf[0] = '\0';
        return 1;
    }

    ctx->rxWorkBuf[ctx->rxPos] = rxData;
    ctx->rxPos++;
    return 0;
}

uint8_t UART_RxIRQHandler(UART_Regs *uart)
{
    uint8_t frameReady;
    UART_Context *ctx;

    ctx = UART_getContext(uart);
    if (ctx == 0) {
        (void) DL_UART_receiveData(uart);
        return 0;
    }

    if (ctx->rxMode == UART_RX_MODE_NONE) {
        (void) DL_UART_receiveData(uart);
        return 0;
    }

    frameReady = UART_RxCallback(uart);
    if (!frameReady) {
        return 0;
    }

    if ((ctx != 0) && (ctx->rxMode == UART_RX_MODE_ISR_CALLBACK) && (ctx->onFrame != 0)) {
        ctx->onFrame(ctx);
    }

    return 1;
}
