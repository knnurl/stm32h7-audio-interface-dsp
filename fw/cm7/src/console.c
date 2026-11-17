#include "console.h"

#include "board.h"

#include <stdio.h>

#define TX_BYTES 4096u
#define RX_BYTES 128u

static UART_HandleTypeDef s_uart;
/* Transmit queue: console_write adds at the head, the interrupt takes from the tail. */
static uint8_t s_tx[TX_BYTES];
static volatile uint32_t s_tx_head;
static volatile uint32_t s_tx_tail;
static uint32_t s_dropped;
/* Receive: the interrupt fills s_rx until a line ending, then raises s_line_ready and drops
 * further input until the main loop has taken the line. */
static char s_rx[RX_BYTES];
static volatile uint32_t s_rx_length;
static volatile bool s_line_ready;

void console_init(void) {
    GPIO_InitTypeDef pin = {0};
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_USART3_CLK_ENABLE();
    pin.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    pin.Mode = GPIO_MODE_AF_PP;
    pin.Pull = GPIO_PULLUP;
    pin.Speed = GPIO_SPEED_FREQ_LOW;
    pin.Alternate = GPIO_AF7_USART3;
    HAL_GPIO_Init(GPIOD, &pin);

    s_uart.Instance = USART3;
    s_uart.Init.BaudRate = 115200;
    s_uart.Init.WordLength = UART_WORDLENGTH_8B;
    s_uart.Init.StopBits = UART_STOPBITS_1;
    s_uart.Init.Parity = UART_PARITY_NONE;
    s_uart.Init.Mode = UART_MODE_TX_RX;
    s_uart.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    s_uart.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&s_uart) != HAL_OK) {
        board_led(kLedRed, true); /* No console to report it on. */
    }
    USART3->CR1 |= USART_CR1_RXNEIE_RXFNEIE;
    HAL_NVIC_SetPriority(USART3_IRQn, kPriorityConsole, 0);
    HAL_NVIC_EnableIRQ(USART3_IRQn);
}

void console_write(const char *data, size_t length) {
    uint32_t head = s_tx_head;
    for (size_t i = 0; i < length; ++i) {
        const uint32_t next = (head + 1u) % TX_BYTES;
        if (next == s_tx_tail) {
            ++s_dropped;
            continue;
        }
        s_tx[head] = (uint8_t)data[i];
        head = next;
    }
    s_tx_head = head;
    USART3->CR1 |= USART_CR1_TXEIE_TXFNFIE; /* The interrupt sends it and turns itself off. */
}

void console_irq(void) {
    const uint32_t status = USART3->ISR;
    if ((status & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE)) != 0u) {
        USART3->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF;
    }
    if ((status & USART_ISR_RXNE_RXFNE) != 0u) {
        const char byte = (char)USART3->RDR;
        if (!s_line_ready) {
            if (byte == '\r' || byte == '\n') {
                if (s_rx_length > 0u) {
                    s_rx[s_rx_length] = '\0';
                    s_line_ready = true;
                }
            } else if (s_rx_length < RX_BYTES - 1u) {
                s_rx[s_rx_length++] = byte;
            }
        }
    }
    uint32_t tail = s_tx_tail;
    while ((USART3->ISR & USART_ISR_TXE_TXFNF) != 0u && tail != s_tx_head) {
        USART3->TDR = s_tx[tail];
        tail = (tail + 1u) % TX_BYTES;
    }
    s_tx_tail = tail;
    if (tail == s_tx_head) {
        USART3->CR1 &= ~USART_CR1_TXEIE_TXFNFIE;
    }
}

void console_flush(void) {
    fflush(stdout);
    USART3->CR1 &= ~USART_CR1_TXEIE_TXFNFIE; /* Sent from here on, by polling. */
    while (s_tx_tail != s_tx_head) {
        while ((USART3->ISR & USART_ISR_TXE_TXFNF) == 0u) {
        }
        USART3->TDR = s_tx[s_tx_tail];
        s_tx_tail = (s_tx_tail + 1u) % TX_BYTES;
    }
    while ((USART3->ISR & USART_ISR_TC) == 0u) {
    }
}

uint32_t console_dropped(void) { return s_dropped; }

bool console_read_line(char *line, size_t capacity) {
    if (!s_line_ready || capacity == 0u) {
        return false;
    }
    size_t i = 0;
    for (; i < capacity - 1u && s_rx[i] != '\0'; ++i) {
        line[i] = s_rx[i];
    }
    line[i] = '\0';
    s_rx_length = 0;
    s_line_ready = false;
    return true;
}
