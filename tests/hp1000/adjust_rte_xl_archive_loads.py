"""Evidence-driven loader dependency adjustments; retain all earlier scripts/logs."""
from pathlib import Path
from rte_7920 import read_volume,make_image
from rte_records import decode_text,encode_text
from stage_rte_xl_archive import OUT


def main():
    disk=OUT/'installation-7920.disc';volumes={i:read_volume(disk,i) for i in range(10)}
    generator=decode_text(volumes[0]['GNLOAD'][1]).replace('OU,XLGEN','LI,$LDRLN::32001\nOU,XLGEN')
    volumes[0]['GNLD2']=(3,encode_text(generator))
    ft=decode_text(volumes[4]['F4ALT'][1]).replace('LI,$CLIBL::32005\n','')
    ft=ft.replace('LI,$F4XCS::32005\n','LI,$F4XCS::32005\nLI,$CLIBL::32005\n')
    volumes[4]['F4ORD']=(3,encode_text(ft))
    gen=decode_text(volumes[6]['PASGEN'][1]).replace('M2645','M2621')
    volumes[6]['PASGEN']=(3,encode_text(gen))
    (OUT/'pascal-system.gen').write_text(gen)
    make_image(disk,volumes)


if __name__=='__main__':main()
