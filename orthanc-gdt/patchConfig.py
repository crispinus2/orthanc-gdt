#!/usr/bin/python3
# patchConfig.py

import json, sys, re

with open(sys.argv[1], "r") as f:
    content = f.read()
    content = re.sub(r"/\*.*?\*/|//.*?$", "", content, flags = re.DOTALL | re.MULTILINE)
    #content = re.sub(r"//.*$", "", content, flags = re.MULTILINE)
    print(content)
    configObj = json.loads(content)
    
configObj["PythonScript"] = "/usr/local/share/orthanc/plugins/restworklist.py"
configObj["Worklists"] = { 
    'Enable': True, 
    'Database': '/var/lib/orthanc/worklist', 
    'FilterIssuerAet': False, 
    "CleanupInterval": 600
    }
configObj["AuthenticationEnabled"] = False
configObj["GdtGenerator"] = { 
    'Enable': True,
    "IncomingDir": "/var/lib/orthanc/GdtIncoming",
    "TransmittedStudiesDatabase": "/var/lib/orthanc/worklist/gdt-transmitted.db"

    }

with open(sys.argv[1], "w") as f:
    json.dump(configObj, f, indent = 4)
