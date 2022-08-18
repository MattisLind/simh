/* nd10.h: ND10 simulator definitions

   Copyright (c) 2022, Mattis Lind

   Permission is hereby granted, free of charge, to any person obtaining a
   copy of this software and associated documentation files (the "Software"),
   to deal in the Software without restriction, including without limitation
   the rights to use, copy, modify, merge, publish, distribute, sublicense,
   and/or sell copies of the Software, and to permit persons to whom the
   Software is furnished to do so, subject to the following conditions:

   The above copyright notice and this permission notice shall be included in
   all copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
   MATTIS LIND BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
   IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
   CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

   Except as contained in this notice, the name of Mattis Lind shall not be
   used in advertising or otherwise to promote the sale, use or other dealings
   in this Software without prior written authorization from Mattis Lind.

   18-Aug-22    ML      New simulator.
*/

#ifndef ND10_H_
#define ND10_H_  0

#include "sim_defs.h"

#define STOP_HALT       1
#define STOP_IBKPT      2
#define STOP_ACCESS     3

#define FLAG_PTR     010000
#define FLAG_PTP     000400
#define FLAG_TTY_T   000040
#define FLAG_KBD     000020
#define FLAG_TTY_R   000010
#define FLAG_SYNC    000002

typedef struct {
  uint16 num;
  uint16 (*iot)(uint16 insn, uint16 AC);
  const char *mnemonics[8];
} SUBDEV;

typedef struct {
  int codes;
  SUBDEV subdev[4];
} IMDEV;

extern t_bool build_dev_tab (void);
extern void flag_on (uint16 flag);
extern void flag_off (uint16 flag);
extern uint16 flag_check (uint16 flag);
extern void dp_on (int flag);
extern uint16 dp_is_on (void);
extern void crt_point (uint16 x, uint16 y);
extern void crt_line (uint16 x1, uint16 y1, uint16 x2, uint16 y2);
extern void crt_idle (void);
extern void crt_hvc (void);
extern void rom_data (uint16 *data);
extern void rom_tty (void);
extern void rom_stty (void);
extern void rom_ptr (void);

extern REG cpu_reg[];
extern uint16 M[];
extern uint16 memmask;
extern SUBDEV *dev_tab[0100];
extern DEVICE cpu_dev, irq_dev, rom_dev, dp_dev, crt_dev, kbd_dev;
extern DEVICE tty_dev, ptr_dev, ptp_dev, sync_dev;
extern DEVICE bel_dev;

#endif /* ND10_H_ */
