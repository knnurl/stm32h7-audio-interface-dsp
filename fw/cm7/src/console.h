/* The serial console on the ST-LINK virtual COM port: USART3 on PD8 (TX) and PD9 (RX),
 * 115200 8N1.
 *
 * Output: printf (through _write) queues text and the interrupt sends it, so printing never
 * stalls the caller. Text that does not fit the queue is dropped and counted. Long dumps call
 * console_flush() between lines, which waits.
 * Input: the interrupt collects bytes; console_read_line() hands over one finished line.
 * Never call any of this from the audio interrupt.
 */
#ifndef CONSOLE_H
#define CONSOLE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

void console_init(void);
void console_write(const char *data, size_t length);
void console_flush(void); /* Sends what is queued, waiting. */
uint32_t console_dropped(void);
size_t console_free(void); /* Bytes the transmit queue can take now. */
/* Copies a finished line (without its line ending, NUL-terminated) and returns true, or returns
 * false when none is ready. Lines longer than the buffer are cut. */
bool console_read_line(char *line, size_t capacity);
void console_irq(void);

#endif
