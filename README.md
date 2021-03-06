# orthanc-gdt

Orthanc PACS server docker image with GDT interface

## What's it for?

[Orthanc](https://www.orthanc-server.com) is a very versatile and fast PACS (Picture Archive and Communications System) server e.g. for medical
applications to store images from medical imaging devices like CT scanners, MRI or Ultrasound.

This image adds a very important glue part for application in German doctor's offices, as most of the AIS (Arztinformationssysteme) are not capable of
using the DICOM protocol to query PACS servers, but most of them implement the GDT interface for communication with other applications or devices.

While GDT doesn't allow for transmitting images, it allows for transmitting test data which then can be used to run a DICOM viewer opening up a study submitted
to Orthanc or to add Ultrasound measurements sent to Orthanc as DICOM Structured Reports to the patient's file, which allows to monitor their progression with time
or using it in letters generated by the AIS et-cetera.

This Docker image contains a python plugin for Orthanc which creates GDT files if a new study is received and if a new supported Structured Report has been sent
to the PACS. Currently supported are Structured Reports for generic Ultrasound measurements as sent by Sonoscape devices (DCIM 'SONO10000') and Cardiac ultrasound (DCIM '5200').

The file created upon new studies contains all information necessary to let the AIS invoke a DICOM viewer like Weasis displaying the correct study (namely, patient's ID, the study 
date and time). Additionally, the study modality and study description is provided as GDT comment lines so that the AIS can display a meaningful line like 'PACS-Datensatz: US: Abdomen' in the
patient's file to click on. For each study, the file is only created once to prevent double entries in the AIS patient's file.

![Screenshot of patient's file showing the generated entries](/readme-resources/scr-file.png?raw=true)

The file create upon Structured Report retrieval contains the measurements supplied as separate test values so that the AIS can import them like it would import results from
e.g. an external laboratory.

![Screenshot of patient's file showing the generated entries](/readme-resources/scr-labsheet.png?raw=true)

## Compatibility

While GDT is a standardized interface, each AIS may have its own specialities causing incompatibility that isn't accounted for currently, so real-world samples are needed to
further improve this interface. Extensive tests have been done with Indamed's Medical Office so far, as it's the AIS we use in my office.

All Structured Report tests have been performed with Sonoscape devices so far. If sample Structured Reports from other manufacturers are supplied, they can be supported as well 
(if they aren't already with the stuff in place for Sonoscape devices, as at last the DCIM '5200' for Cardiology is a standardized one).

## Installation

Pre-built images are available at [Docker Hub](https://hub.docker.com/r/crispinus/orthanc-gdt). While I usually test them on my linux server, they should also run in Docker
Desktop for Windows.

The default configuration runs the Orthanc DICOM service on Port 4242 and the web interface on port 8042. By default, the Modality Worklist plugin and the GDT Generator for incoming files
is enabled. Storage requests are enabled from any Station AET, so no special configuration should be necessary to have your imaging device post its imaging to the PACS. Only DICOM Q/R
would require to modify the configuration to include the Station's AET and its IP and port settings.

The Orthanc web interface allows accessing and querying all stored DICOM instances sorted by patients, studies and series. The Stone of Orthanc (advanced Orthanc web viewer) is also part of this 
distribution and might meet basic needs of reviewing the stored image data.

**CAUTION**: The default configuration of this image would be very insecure on unprotected networks, as Orthanc is run with remote access enabled and authentication DISABLED. This configuration has been
deliberately chosen as it greatly simplifies accessing and using Orthanc, and most available AIS are very insecure network-wise, too, so that they should never be used on unprotected networks as well.
If you plan to run this image on an unprotected network, you should change the configuration to include at least a basic form of authentication to prevent unauthorized access to or modification of the
stored data.

### Running on Linux

I like to use Docker Compose for running this image. A sample configuration as well as a systemd service file for auto-starting the image is supplied in this repository's `utils`-folder.

### Running on Windows

I recommend to use [Docker Desktop](https://www.docker.com/products/docker-desktop) for running this image on Windows. After installation, download [this](/utils/docker-compose.yml) and [this](/utils/runorthanc.bat) file and put them together in a new folder.
You can then double-click on the batch file to run the orthanc container. It will map the internal DICOM port to 105 and the web interface to 8090. This may be changed by editing the `docker-compose.yml` file with any text editor. If required, you can also
change the paths that are used as mapping paths for the internal volumes in this file. 

## Usage

If everything is up and running, you can

* access stored data via the Orthanc web interface running at the configured port
* store imaging data from DICOM-compatible devices by configuring the machine's IP and chosen port for DICOM communication in the device's
  DICOM storage configuration
* use the Orthanc REST API to interface it with your own scripts and utilities
  * especially the path `/worklist/add` to add worklist items from your chosen AIS. A call could look like 
    `http://<server-ip>:<web-port>/worklist/add?id=12345&lastname=Doe&firstname=John&birthdate=01.01.1900&sex=1&modality=US&scheduledStation=US01&procedure=Abdomen&physician=Mustermann^Max`
  * all supported Query parameters: (values have to be supplied UTF8 encoded!)
    * id: Patient id the patient is referenced as in the AIS (this id is used for field 3000 (patient's id) in the generated GDT files)
    * lastname: Patient's last name
    * firstname: Patient's first name
    * birthdate: Patient's birthdate in format dd.mm.yyyy
    * sex: Patient's sex, 0 and 3 are translated to 'O' (Other), 1 to 'M' (Male), 2 to 'F' (Female); this follows Medical Office's convention of enumerating the possible sexes
    * modality: requested DICOM modality (defaulting to 'US' for ultrasound, other possible values include 'MR', 'CT' and a lot of others according to the DICOM standard)
    * scheduledStation: the DICOM AET of the station this worklist entry is scheduled for (defaulting to 'US01') - this must match the AET configured in the Ultrasound's worklist configuration
    * procedure: Requested procedure - this field is stored in the DICOM `RequestedProcedureDescription`-tag. Ultrasound devices often use this one to fill the `StudyDescription` tag of commited
      instances
    * physician: Performing physian - following the DICOM convention of specifying names as Lastname^Firstname (caret instead of space for separation)
  * The REST call returns a GDT file upon success, which could be used to link to a suitable DICOM viewer for viewing the study's images from your AIS
  * as Orthanc doesn't implement a DICOM MPPS service as of now to allow the imaging device to notify the Modality Worklist provider of completing a Procedure Step, the python plugin keeps the worklist
    directory tidy by regularly removing worklist files that
    * have a creation date before today or
    * a study with a matching Accession Id has been received for. The Accession Id is auto-generated by the python plugin.
    * by default, the cleanup script runs in intervals of 600 seconds (10 minutes); the cleanup interval can be configured in Orthanc's configuration file (`Worklists.CleanupInterval`), if interval is set to `null` or
      the key is not specified in the configuration file, cleanup functionality is disabled
* Import the GDT files created by the python plugin into your AIS of choice
  * GDT files generated upon new studies use a test id (GDT field `8410`) defaulting to `EXTPACS` and a test description (GDT field `8411`) defaulting to `PACS-Datensatz`. The id and description can be changed by configuring
    `GdtGenerator.TestId` and `GdtGenerator.TestDescription` in Orthanc's configuration.

### Usage with Indamed's Medical Office

As we are using Medical Office in my office, I can give you detailed instructions on how to setup the interface best with it. Screenshots follow. As Medical Office is a German software and only available in German language,
this section is also written in German to make it more clear.
 
#### Worklist-Funktion konfigurieren

Für jeden gewünschten Untersuchungstyp sollte ein passender Auftrag im Datenpflegesystem angelegt werden. Dieser muss wie folgt konfiguriert werden:

* Schlüssel: frei wählbar, z.B. "SONOABDOMEN"
* Beschreibung: kann ebenfalls frei gewählt werden
* alle Tarife aktivieren
* 'Geräteanbindung', 'ohne Bestätigung' und 'keine Dokumentation im Auftragsblatt' in den Auftragsoptionen anhaken, alles andere abhaken
* auf der Seite 'Geräteanbindung' als Schnittstelle 'GDT' wählen, Zeichensatz 'Windows', die Inhalte von Testident und Verf.spez. Kennfeld sind nicht wichtig
* nur 'Ergebnis abwarten' anhaken
* Pfad für Exportdatei festlegen, z.B. `C:\GDT\export.gdt`. Das angegebene Verzeichnis muss existieren und für den Benutzer schreibbar sein. Die Datei wird zwar vom Skript nicht verwendet, aber wenn das Feld
  leerbleibt, wird das Skript von Medical Office nicht ausgeführt.
* Datenaufnahmeprogramm: hier wird ein PHP-Skript verwendet, da Medical Office PHP-Skripte in dieser Zeile unterstützt. Das Skript nutzt hier zur Verfügung
  stehende Briefschreibungsvariablen, um die Worklist-Felder zu befüllen. [Hier](/utils/CallWorklist-oneline.php?raw=true) kann das notwendige Skript direkt als
  Einzeiler abgerufen werden
  * angepasst werden muss noch der Inhalt von `$HOST` (Server-IP ersetzen) sowie von `$PORT`, `$PROCEDURE` kann auf den gewünschten Prozedurennamen gesetzt werden (z.B. 'Abdomen')
  * das Skript macht keine Angaben zu `scheduledStation` oder `modality`, hier werden also die Standardwerte des Plugins (`US01` und `US`) übernommen

Dieser Auftrag kann nun z.B. über einen Schalter in der Schalterleiste ausgeführt werden und setzt den gerade aktiven Patienten dann auf die Worklist.

#### Generierte GDT-Dateien verarbeiten

Hierfür muss an einem beliebigen Arbeitsplatz als Importverzeichnis das mit dem `/var/lib/orthanc/GdtIncoming` verknüpfte Verzeichnis angegeben werden. Das kann z.B. auch ein Netzlaufwerk oder ein UNC-Pfad sein,
es muss sich also nicht zwangsläufig um einen Medical Office-Arbeitsplatz auf dem Rechner handeln, wo der Docker-Container ausgeführt wird.
Die erzeugten GDT-Dateien werden nach dem Muster `<Accession Id>.gdt` bzw. `<Accession Id>-sr.gdt` für Structured Reports benannt. Sobald das Medical Office-Hauptfenster den Fokus hat, importiert es vorliegende
GDT-Dateien und generiert die entsprechenden Karteikarteneinträge. D.h., der Import funktioniert NICHT, wenn der entsprechende Rechner nicht läuft und MO dort nicht gestartet oder im Vordergrund ist.
Da die Dateien aber nicht verloren gehen, können sie einfach zu einem späteren Zeitpunkt importiert werden, wenn Medical Office auf dem Arbeitsplatz wieder im Vordergrund ist.
Die in den Structured Report-GDT-Dateien enthaltenen Testwerte werden so importiert, dass sie anschließend unter `Alle Werte` im Auftragsblatt erscheinen. Von dort aus kann man sie dann der gewünschten Auftragsblattseite zuordnen.

#### DICOM-Viewer aufrufen

Wir verwenden in meiner Praxis den Open Source-DICOM-Viewer [Weasis](https://nroduit.github.io/en/) zur Anzeige der gespeicherten Bilder. Dieser verwendet JAVA und läuft deshalb unter allen gängigen Betriebssystemen. Da er sehr gute Kommandozeilenoptionen bietet, um die angezeigten Studien vorauszuwählen, eignet er sich perfekt für diesen Zweck.
Eine Installation kann auf jedem Rechner lokal erfolgen, es ist aber auch möglich, ein Webarchiv auf einen in der Praxis verfügbaren Webserver zu legen, von dem aus dann jeder Rechner immer die aktuellste Version
lädt.

Zunächst ist hier auch wieder ein passender Auftrag anzulegen:

* Schlüssel: muss dem eingestellten Schlüssel für die automatisch generierten GDT-Dateien entsprechen, Standard ist `EXTPACS`
* Beschreibung: kann frei gewählt werden
* alle Tarife aktivieren
* Auftragsoptionen: nur `Geräteanbindung`, `Dokumentation im Krankenblatt`, `ohne Bestätigung` und `keine Dokumentation im Auftragsblatt` anhaken
* Seite `Geräteanbindung`: Schnittstelle 'GDT', Zeichensatz 'Windows', Testident und Verf.spez. Kennfeld auf `EXTPACS` setzen
* nur 'Ergebnisse speichern' anhaken
* Pfad für Exportdatei festlegen, z.B. `C:\GDT\export.gdt`. Das angegebene Verzeichnis muss existieren und für den Benutzer schreibbar sein.
* Auswertungsprogramm: hier wird ein PHP-Skript verwendet, welches die GDT-Datei einliest und eine entsprechende `weasis://`-URL erstellt, mit der Weasis dann aufgerufen wird.
  [Hier](/utils/CallWeasis-oneline.php?raw=true) kann das notwendige Skript direkt als Einzeiler abgerufen werden.
  * angepasst werden muss noch `$HOST` und `$PORT` auf die benötigten Werte, `$gdtpath` muss auf den angegebenen Pfad zur Exportdatei gesetzt werden. Achtung: Backslashes (`\`)
    müssen verdoppelt werden, also z.B.: `C:\\GDT\\export.gdt`
  * Die notwendigen Informationen, um die Studie aufzufinden (Patienten-ID, Datum und Zeit) werden aus der GDT-Datei entnommen. Leider unterstützt Medical Office (noch) nicht die im
    GDT-Standard mittlerweile vorgesehene Übergabe einer eindeutigen Untersuchungs-ID; das wäre natürlich ein eleganterer Weg, um die passende Studie zu öffnen.
* Um die Beschränkung zu umgehen, dass PHP nur Dateien ausführen kann, die unterhalb des eigenen Arbeitsverzeichnes liegen (welches dem Medical-Office-Verzeichnis auf dem lokalen Rechner entspricht) wird
  eine Batch-Datei vom Skript aufgerufen. Diese kann [hier](/utils/runweasis.bat?raw=true) abgerufen werden und muss auf jedem Rechner im Medical-Office-Verzeichnis (meist `C:\MEDOFF`) gespeichert werden.

Wenn alles geklappt hat, kann bei den durch den automatischen Import der bei neuen Studien erzeugten GDT-Dateien angelegten Karteikarteneinträgen durch `Enter` nun der Viewer gestartet werden
(alternativ ist auch Doppelklick -> Klick auf `Externe Auswertung` möglich). Aus Weasis heraus kann man dann z.B. Ausdrucke machen oder auch CDs brennen bzw. USB-Sticks erzeugen, die dem Patienten 
dann mitgegeben werden können.

## Advanced Configuration

### Get the currently used configuration and change it
Using the guide available at [Orthanc's Homepage](https://book.orthanc-server.com/users/docker.html#fine-tuning-the-configuration) you can access the currently used configuration,
modify it and start the container with your individual configuration to implement necessary changes to fit your local setup.

### WorklistEntryAdded hook
By adding `Worklists.UrlOnWorklistEntryAdded` to Orthanc's configuration, you can make the plugin call the given URL if a worklist entry has been created.
We use this in my office to dim the light and close the window's shutters automatically (my office is equipped with KNX ;)).

### GdtWritten hook
By adding `GdtGenerator.UrlOnGdtWritten` to Orthanc's configuration, you can make the plugin call the given URL as soon as a GDT file has been created in reaction
to a new study.
Our ultrasound device is set up to send its images as soon as `End Exam` is selected on its keyboard, so we can use this to open the shutters and turn up the light again
when the examination has finished.
