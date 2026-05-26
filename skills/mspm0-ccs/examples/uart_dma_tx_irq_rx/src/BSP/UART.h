#ifndef __USER_UART_H__
#define __USER_UART_H__

#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include "ti_msp_dl_config.h"

#define UART_FLOAT_BUF_SIZE 256

#define UART_TX_BUF_SIZE   256  // UART发送缓冲区长度
#define UART_RX_BUF_SIZE   256  // UART接收缓冲区长度
#define UART_RX_TERMINATOR '\n' // UART接收结束符

extern volatile uint8_t UART0TxDMADone;
extern volatile uint8_t UART0RxDone;
extern volatile uint8_t UART0RxBuf[UART_RX_BUF_SIZE];
extern volatile uint16_t UART0RxPos;
extern volatile uint16_t UART0RxLen;
extern volatile uint8_t UART0RxOvf;
extern float UART0FloatBuf[UART_FLOAT_BUF_SIZE];
extern volatile uint16_t UART0FloatLen;
extern volatile uint8_t UART0FloatParseError;

void UART_init(void);

/**
 * @brief UART0发送字符串
 * @note 使用阻塞方式
 * @param str 待发送字符串指针
 * @return 字符串长度
 */
int UART0_sendStr(const char* str);

/**
 * @brief UART0 printf
 * @param fmt 格式控制字符串与参数列表
 * @return 字符串长度(vsprintf返回值)
 */
int UART0_printf(char* fmt, ...);

/**
 * @brief UART0使用DMA方式发送字符串
 * @note 调用该函数时, 若上次UART DMA已传送完成, 则占用时间最短
 * @param str 待发送字符串指针
 * @param len 字符串长度
 */
void UART0_sendStrDMA(const char* str, uint16_t len);

/**
 * @brief UART0 printf (使用DMA方式)
 * @note 调用该函数时, 若上次UART DMA已传送完成, 则占用时间最短
 * @param fmt 格式控制字符串与参数列表
 */
void UART0_printfDMA(char* fmt, ...);

/**
 * @brief UART0开始接收数据
 * @note 先处理完上次接收数据, 再调用该函数继续接收
 */
void UART0_startReceive(void);
uint16_t UART0_parseRxFloats(void);

void UART0_DMADoneTxCallback(void);
void UART0_RxCallback(void);

#endif /* #ifndef __USER_UART_H__ */

