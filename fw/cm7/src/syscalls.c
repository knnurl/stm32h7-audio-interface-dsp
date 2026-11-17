/* printf to the console. newlib-nano calls _write; the other system calls are stubs, since
 * there is no file system or process. */
#include "console.h"

#include <errno.h>
#include <sys/stat.h>

int _write(int file, char *data, int length) {
    (void)file;
    console_write(data, (size_t)length);
    return length;
}

int _close(int file) {
    (void)file;
    return -1;
}

int _fstat(int file, struct stat *st) {
    (void)file;
    st->st_mode = S_IFCHR; /* Character device: printf stays line-buffered. */
    return 0;
}

int _isatty(int file) {
    (void)file;
    return 1;
}

int _lseek(int file, int offset, int whence) {
    (void)file;
    (void)offset;
    (void)whence;
    return 0;
}

int _read(int file, char *data, int length) {
    (void)file;
    (void)data;
    (void)length;
    return 0;
}

int _getpid(void) { return 1; }

int _kill(int pid, int signal) {
    (void)pid;
    (void)signal;
    errno = EINVAL;
    return -1;
}
