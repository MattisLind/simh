"""Exercise original IMAGE/L DBDS on a schema derived from its HP source grammar.

This is a database-creation gate, not a CRUD/persistence acceptance test.
"""
import json
from pathlib import Path
from rte_7920 import read_volume,make_image
from rte_records import encode_text
from run_rte_xl_archive import OUT,session

SCHEMA='''BEGIN DATA BASE: TDB:1:32010;
LEVELS: 1 TEST;
ITEMS:
VALUE,I1(1,1);
SETS:
NAME: ROWS::32010,DETAIL;
ENTRY: VALUE;
CAPACITY: 10;
END.
'''


def main():
    source=OUT/'image-load.disc';disk=OUT/'image-schema.disc'
    volumes={v:read_volume(source,v) for v in range(10)}
    volumes[9]['SCHEMA']=(3,encode_text(SCHEMA))
    make_image(disk,volumes)
    (OUT/'image-test.schema').write_text(SCHEMA)
    run,text=session('image-schema',['MC,11','RU,DBDS::32010,SCHEMA::32010,1'],disk=disk)
    files=read_volume(disk,9)
    created={n:dict(type=files[n][0],bytes=len(files[n][1])) for n in ['TDB','ROWS'] if n in files}
    passed=run['status']=='PASS' and len(created)==2 and 'ABORTED' not in text
    report=dict(status='PASS' if passed else 'FAIL',execution=run,created=created,
                persistent_database_accepted=False)
    (OUT/'image-schema-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return int(not passed)


if __name__=='__main__':raise SystemExit(main())
