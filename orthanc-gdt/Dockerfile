FROM jodogne/orthanc

MAINTAINER Julian Hartig <julian@whisper-net.de>
LABEL Description="Docker image of Orthanc, free DICOM server, with plugins and configuration for GDT interfacing with AIS (Arztinformationssystemen)" Vendor="Julian Hartig"

ADD ./download-plugins.sh ./download-plugins.sh
RUN bash ./download-plugins.sh

RUN rm ./download-plugins.sh

RUN apt-get -y clean && apt-get -y update
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install python3.7 libpython3.7 python3-pip && /usr/bin/pip3 install pydicom pillow && \
    apt-get -y autoremove && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -snf /usr/share/zoneinfo/Europe/Berlin /etc/localtime && echo "Europe/Berlin" > /etc/timezone
    
ADD ./download-python.sh ./download-python.sh
RUN bash ./download-python.sh

RUN rm ./download-python.sh

VOLUME [ "/var/lib/orthanc/db", "/var/lib/orthanc/worklist", "/var/lib/orthanc/GdtIncoming" ]
EXPOSE 4242
EXPOSE 8042

ENTRYPOINT [ "Orthanc" ]
CMD [ "/etc/orthanc/" ]

ADD ./patchConfig.py ./patchConfig.py
RUN /usr/bin/python3.7 ./patchConfig.py /etc/orthanc/orthanc.json
RUN rm ./patchConfig.py

ADD ./restworklist.py ./restworklist.py
RUN mv ./restworklist.py /usr/local/share/orthanc/plugins/

# https://groups.google.com/d/msg/orthanc-users/qWqxpvCPv8g/Z8huoA5FDAAJ
ENV MALLOC_ARENA_MAX 5
