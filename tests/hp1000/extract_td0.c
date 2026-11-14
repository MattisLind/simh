#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "libdsk.h"
int main(int argc,char **argv) {
 DSK_PDRIVER d; DSK_GEOMETRY g; FILE *f; unsigned c,h,i,errors=0;
 if(argc!=3)return 2;
 if(dsk_open(&d,argv[1],"tele",NULL)||dsk_getgeom(d,&g))return 3;
 f=fopen(argv[2],"wb");if(!f)return 4;
 for(c=0;c<85;c++)for(h=0;h<2;h++){
  dsk_psect_t n=0;DSK_FORMAT *ids=NULL;
  if(dsk_ptrackids(d,&g,c,h,&n,&ids))continue;
  for(i=0;i<n;i++){
   DSK_GEOMETRY geo=g; unsigned char *b=malloc(ids[i].fmt_secsize);
   uint32_t rec[5]={c,h,ids[i].fmt_sector,(uint32_t)ids[i].fmt_secsize,0};
   geo.dg_secsize=ids[i].fmt_secsize;
   rec[4]=dsk_pread(d,&geo,b,c,h,ids[i].fmt_sector);
   if(rec[4]){fprintf(stderr,"error %u/%u/%u: %s\n",c,h,ids[i].fmt_sector,dsk_strerror(rec[4]));errors++;}
   fwrite(rec,sizeof rec,1,f);fwrite(b,1,geo.dg_secsize,f);free(b);
  }
  dsk_free(ids);
 }
 fclose(f);dsk_close(&d);return errors?1:0;
}
