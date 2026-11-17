/* Fault capture. A fault records the stacked registers and the fault status registers in memory
 * that survives a reset, then resets. The next start prints the record. After the Psyight node
 * firmware's fault.c. */
#ifndef FAULT_H
#define FAULT_H

#include <stddef.h>

/* Prints the record of a fault that happened before this start, if there is one. */
void fault_report_boot(void);
/* "fault none", or the count and the last record. Returns the length written. */
size_t fault_describe(char *out, size_t capacity);

#endif
