#!/bin/bash

set -e
cd

URL=http://lsb.orthanc-server.com/

VERSION_AUTHORIZATION=mainline
VERSION_DICOM_WEB=mainline
VERSION_GDCM=mainline-gdcm3
VERSION_MYSQL=mainline
VERSION_POSTGRESQL=mainline
VERSION_TRANSFERS=mainline
VERSION_WEB_VIEWER=mainline
VERSION_WSI=mainline
VERSION_STONE=mainline

# Download binaries compiled with Linux Standard Base

# 2020-01-24: The DICOMweb and Web viewer plugins have no unit test
# anymore, as they are now built using the Holy Build Box because of
# incompatibility between GDCM 3.0 and LSB compilers

#wget ${URL}/plugin-dicom-web/${VERSION_DICOM_WEB}/UnitTests -O - > UnitTests-DicomWeb
wget ${URL}/plugin-dicom-web/${VERSION_DICOM_WEB}/libOrthancDicomWeb.so

#wget ${URL}/plugin-webviewer/${VERSION_WEB_VIEWER}/UnitTests -O - > UnitTests-WebViewer
wget ${URL}/plugin-webviewer/${VERSION_WEB_VIEWER}/libOrthancWebViewer.so

wget ${URL}/plugin-authorization/${VERSION_AUTHORIZATION}/libOrthancAuthorization.so

wget ${URL}/plugin-gdcm/${VERSION_GDCM}/libOrthancGdcm.so

wget ${URL}/stone-webviewer/${VERSION_STONE}/libStoneWebViewer.so

# Move the binaries to their final location
mv ./libOrthancDicomWeb.so             /usr/local/share/orthanc/plugins/
mv ./libOrthancWebViewer.so            /usr/local/share/orthanc/plugins/
mv ./libOrthancAuthorization.so        /usr/local/share/orthanc/plugins/
mv ./libOrthancGdcm.so                 /usr/local/share/orthanc/plugins/
mv ./libStoneWebViewer.so              /usr/local/share/orthanc/plugins/
