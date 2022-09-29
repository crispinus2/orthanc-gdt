FROM osimis/orthanc:22.9.2

MAINTAINER Julian Hartig <julian@whisper-net.de>
LABEL Description="Docker image of Orthanc, free DICOM server, with plugins and configuration for GDT interfacing with AIS (Arztinformationssystemen)" Vendor="Julian Hartig"

RUN pip install pydicom pillow

RUN ln -snf /usr/share/zoneinfo/Europe/Berlin /etc/localtime && echo "Europe/Berlin" > /etc/timezone
    
VOLUME [ "/var/lib/orthanc/db", "/var/lib/orthanc/worklist", "/var/lib/orthanc/GdtIncoming" ]
EXPOSE 4242
EXPOSE 8042

# define a default configuration thanks to environment variables.  They can be overriden at runtime

ENV ORTHANC__PYTHON_SCRIPT = "/scripts/restworklist.py"
ENV ORTHANC__WORKLISTS__ENABLE = true
ENV ORTHANC__WORKLISTS__DATABASE = "/var/lib/orthanc/worklist"
ENV ORTHANC__WORKLISTS__FILTER_ISSUER_AET = false
ENV ORTHANC__WORKLISTS__CLEANUP_INTERVAL = 600

ENV ORTHANC__GDT_GENERATOR__ENABLE = true
ENV ORTHANC__GDT_GENERATOR__INCOMING_DIR = "/var/lib/orthanc/GdtIncoming"
ENV ORTHANC__GDT_GENERATOR__TRANSMITTED_STUDIES_DATABASE = "/var/lib/orthanc/worklist/gdt-transmitted.db"

ADD ./restworklist.py /scripts/restworklist.py