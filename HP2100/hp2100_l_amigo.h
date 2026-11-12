/* State of the 7902/9895 endpoint. Include hp2100_defs.h first. */
#ifndef HP2100_L_AMIGO_H
#define HP2100_L_AMIGO_H

typedef struct {
    uint32 cylinder[2], head[2], sector[2], offset, selected, secondary;
    uint32 packet[16], packet_count, reply_count, reply_pos, read_active, write_active;
    uint32 untalk, identified, dsj;
    uint8 reply[256], disk_status[2], loopback[256];
    uint32 loopback_count;
} L_AMIGO_STATE;
extern L_AMIGO_STATE l_amigo_state;
extern UNIT l_amigo_units[];
extern void l_amigo_reset (void);
extern t_stat l_amigo_attach (UNIT *, CONST char *);
extern t_stat l_amigo_detach (UNIT *);
#endif
