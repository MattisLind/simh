/* 7902/9895 floppy endpoint on the existing HP-IB bus.
   Initial scope: double-sided, double-density 77/2/30/256-byte HPI media.
   The opcode/secondary protocol follows hp2100_di_da.c; unlike the hard-disc
   backend, a controller here has two individually addressed drive units. */
#include <string.h>
#include "hp2100_defs.h"
#include "hp2100_io.h"
#include "hp2100_di.h"
#include "hp2100_l_amigo.h"

extern DEVICE hpi_dev;
static t_stat floppy_service (UNIT *unit);
extern t_stat l_hpi_service (UNIT *unit);
UNIT l_amigo_units[] = {
    { UDATA(&floppy_service, UNIT_FIX | UNIT_ATTABLE | UNIT_ROABLE, 1182720) },
    { UDATA(&floppy_service, UNIT_FIX | UNIT_ATTABLE | UNIT_ROABLE, 1182720) },
    { UDATA(&l_hpi_service, 0, 0) }
};
L_AMIGO_STATE l_amigo_state;
static void poll (t_bool enabled) { di_poll_response(lh, 0, enabled ? SET : CLEAR); }
void l_amigo_reset (void)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    memset(fd, 0, sizeof *fd);
    sim_cancel(&l_amigo_units[0]); sim_cancel(&l_amigo_units[1]);
    di[lh].acceptors = (l_amigo_units[0].flags & UNIT_ATT) || (l_amigo_units[1].flags & UNIT_ATT) ? 1 : 0;
    di[lh].listeners = di[lh].talker = 0;
    di[lh].bus_cntl = di[lh].cntl_register = di[lh].poll_response = 0;
    poll(TRUE);
}
t_stat l_amigo_attach (UNIT *unit, CONST char *name)
{
    t_stat status = attach_unit(unit, name);
    if (status != SCPE_OK) return status;
    if (sim_fsize(unit->fileref) != 1182720) { detach_unit(unit); return SCPE_FMT; }
    l_amigo_reset(); return SCPE_OK;
}
t_stat l_amigo_detach (UNIT *unit)
{ t_stat status = detach_unit(unit); l_amigo_reset(); return status; }
static void advance (void)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    if (++fd->sector[fd->selected] == 30) {
        fd->sector[fd->selected] = 0;
        if (++fd->head[fd->selected] == 2) { fd->head[fd->selected] = 0; fd->cylinder[fd->selected]++; }
    }
}
static t_bool disk_read (void)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    UNIT *unit = &l_amigo_units[fd->selected];
    t_addr position = ((fd->cylinder[fd->selected] * 2 + fd->head[fd->selected]) * 30 + fd->sector[fd->selected]) * 256;
    if (!(unit->flags & UNIT_ATT) || fd->cylinder[fd->selected] >= 77 || fd->head[fd->selected] >= 2 || fd->sector[fd->selected] >= 30) {
        fd->disk_status[fd->selected] = 020; fd->dsj = 1; fd->read_active = 0; poll(TRUE); return FALSE;
    }
    if (sim_fseek(unit->fileref, position, SEEK_SET) || sim_fread(fd->reply, 1, 256, unit->fileref) != 256) {
        fd->disk_status[fd->selected] = 020; fd->dsj = 1; fd->read_active = 0; poll(TRUE); return FALSE;
    }
    fd->reply_count = 256; fd->reply_pos = 0; advance(); return TRUE;
}
static void command (void)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    uint32 opcode = fd->packet[0];
    if (opcode != 15) {
        if (fd->packet_count > 1 && fd->packet[1] > 1) {
            fd->dsj = 1; fd->packet_count = 0; poll(TRUE); return;
        }
        fd->selected = fd->packet_count > 1 ? fd->packet[1] : 0;
    }
    if (opcode != 3) { fd->disk_status[fd->selected] = 0; fd->dsj = 0; }
    switch (opcode) {
        case 0: fd->cylinder[fd->selected] = fd->head[fd->selected] = fd->sector[fd->selected] = 0; fd->read_active = 1; break;
        case 1: fd->cylinder[fd->selected] = fd->head[fd->selected] = fd->sector[fd->selected] = 0; break;
        case 2:
            if (fd->packet_count != 6) { fd->dsj = 1; break; }
            fd->cylinder[fd->selected] = (fd->packet[2] << 8) | fd->packet[3];
            fd->head[fd->selected] = fd->packet[4]; fd->sector[fd->selected] = fd->packet[5]; fd->offset = 0; break;
        case 3:
            fd->read_active = fd->write_active = 0;
            fd->reply[0] = fd->disk_status[fd->selected]; fd->reply[1] = 0;
            fd->reply[2] = 012; fd->reply[3] = 0; /* double-sided floppy type 5 */
            fd->reply_count = 4; fd->reply_pos = 0; break;
        case 4:
            fd->reply[0] = fd->cylinder[fd->selected] >> 8; fd->reply[1] = fd->cylinder[fd->selected];
            fd->reply[2] = fd->head[fd->selected]; fd->reply[3] = fd->sector[fd->selected]; fd->reply_count = 4; fd->reply_pos = 0; break;
        case 5: fd->read_active = 1; fd->write_active = 0; break;
        case 8: fd->write_active = 1; fd->read_active = 0; fd->offset = 0; break;
        case 10: fd->read_active = fd->write_active = 0; break;
        case 15: break; /* file mask, no fd->cylinder-limited hard-disc extent */
        default: fd->disk_status[fd->selected] = 012; fd->dsj = 1; break;
    }
    fd->packet_count = 0; poll(TRUE);
}
t_bool l_amigo_accept (uint32 unit, uint8 data)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    uint32 address = 0;
    (void)unit;
    if (di[lh].bus_cntl & BUS_ATN) {
        if (data == 077) { di[lh].listeners = 0; return TRUE; }
        if ((data & 0140) == 040) { if ((data & 037) == address) di[lh].listeners = 1; return TRUE; }
        if ((data & 0140) == 0100) {
            fd->untalk = data == 0137;
            if (fd->untalk && fd->secondary == 036) poll(TRUE);
            di[lh].talker = ((data & 037) == address) ? 1 : 0; return TRUE;
        }
        if (data == 024 || (data == 4 && di[lh].listeners)) {
            fd->read_active = fd->write_active = 0; fd->packet_count = fd->reply_count = fd->reply_pos = 0; fd->dsj = 0; poll(TRUE); return TRUE;
        }
        if ((data & 0140) == 0140) {
            fd->secondary = data & 037;
            if (fd->untalk && fd->secondary == address) {
                fd->identified = 1; di[lh].talker = 1;
                fd->reply[0] = 0; fd->reply[1] = 0201; fd->reply_count = 2; fd->reply_pos = 0;
            }
            else if (di[lh].talker) {
                if (fd->secondary == 020) { fd->reply[0] = fd->dsj; fd->reply_count = 1; fd->reply_pos = 0; }
                if (fd->secondary == 0 && fd->read_active) disk_read();
                if (fd->secondary == 036) {
                    memcpy(fd->reply, fd->loopback, sizeof fd->reply);
                    fd->reply_count = sizeof fd->reply; fd->reply_pos = 0;
                }
                if (fd->secondary == 037) { fd->reply[0] = 0; fd->reply_count = 1; fd->reply_pos = 0; }
            }
            else if (di[lh].listeners) {
                if (fd->secondary == 010) fd->packet_count = 0;
                if (fd->secondary == 036) fd->loopback_count = 0;
            }
            return TRUE;
        }
        return TRUE;
    }
    /* 07902-90030 appendix A, Read/Write Loopback Record: secondary 1Eh
       accesses the controller's 256-byte buffer, without touching disk media. */
    if (fd->secondary == 036) {
        if (fd->loopback_count < sizeof fd->loopback)
            fd->loopback[fd->loopback_count++] = data;
        if ((di[lh].bus_cntl & BUS_EOI) || fd->loopback_count == sizeof fd->loopback) poll(TRUE);
        return TRUE;
    }
    if (fd->secondary == 010) {
        if (fd->packet_count < 16) fd->packet[fd->packet_count++] = data;
        if (di[lh].bus_cntl & BUS_EOI) command();
        return TRUE;
    }
    if (fd->secondary == 0 && fd->write_active) {
        UNIT *drive = &l_amigo_units[fd->selected];
        if (!(drive->flags & UNIT_ATT) || (drive->flags & UNIT_RO)
          || fd->cylinder[fd->selected] >= 77
          || fd->head[fd->selected] >= 2
          || fd->sector[fd->selected] >= 30) { fd->dsj = 1; return TRUE; }
        fd->reply[fd->offset++] = data;
        if (fd->offset == 256) {
            t_addr position = ((fd->cylinder[fd->selected] * 2 + fd->head[fd->selected]) * 30 + fd->sector[fd->selected]) * 256;
            if (sim_fseek(drive->fileref, position, SEEK_SET) || sim_fwrite(fd->reply, 1, 256, drive->fileref) != 256) fd->dsj = 1;
            fd->offset = 0; advance();
        }
        if (di[lh].bus_cntl & BUS_EOI) { fd->write_active = 0; poll(TRUE); }
    }
    return TRUE;
}
void l_amigo_respond (CARD_ID card, uint32 unit, uint8 bus)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    (void)card; (void)unit;
    if (bus & BUS_IFC) {
        di[lh].listeners = di[lh].talker = 0;
        fd->packet_count = fd->identified = 0;
    }
    else if (!(bus & (BUS_ATN | BUS_NRFD)) && di[lh].talker)
        sim_activate(&l_amigo_units[0], 5);
}
static t_stat floppy_service (UNIT *unit)
{
    L_AMIGO_STATE * const fd = &l_amigo_state;
    uint32 budget = 8;
    (void)unit;
    while (budget-- && di[lh].talker && !(di[lh].bus_cntl & (BUS_ATN | BUS_NRFD))) {
        if (fd->reply_pos == fd->reply_count) {
            if (fd->secondary != 0 || !fd->read_active || !disk_read()) break;
        }
        /* Identify and status/loopback replies are records even if a prior
           streaming disk read remains armed. Only disk data suppresses EOI. */
        {
            t_bool last = (fd->identified || fd->secondary != 0 || !fd->read_active)
                && fd->reply_pos + 1 == fd->reply_count;
            di_bus_control(lh, 0, last ? BUS_EOI : 0, last ? 0 : BUS_EOI);
        }
        if (!di_bus_source(lh, fd->reply[fd->reply_pos])) break;
        fd->reply_pos++;
        if (fd->reply_pos == fd->reply_count && fd->identified) { fd->identified = 0; break; }
    }
    return SCPE_OK;
}
